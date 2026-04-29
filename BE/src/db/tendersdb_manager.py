"""
Database Manager for Autofill Transaction Tracking (Supabase PostgreSQL)
────────────────────────────────────────────────────────────────────────
Handles all PostgreSQL operations for logging and querying autofill transactions.

Design choices
• Singleton – only ONE instance & ONE connection per process.
• UPSERT (INSERT … ON CONFLICT … DO UPDATE) – preserves the original row-id
  and created_at timestamp while updating changed fields.
• NOT NULL on the UNIQUE-key columns so the constraint actually fires.
• Column-name validation – rejects anything that isn't [a-zA-Z0-9_].
• Same public interface as the original SQLite version so main.py
  and all callers work without changes.
"""

import os
import re
from decimal import Decimal
from datetime import datetime

try:
    import psycopg2
    import psycopg2.extras  # for RealDictCursor
except ModuleNotFoundError:
    psycopg2 = None

_DB_ERROR = psycopg2.Error if psycopg2 else Exception

try:
    from dotenv import load_dotenv
    from pathlib import Path

    # Search for .env from this file's location up to the project root
    _this_dir = Path(__file__).resolve().parent
    for _parent in (_this_dir, _this_dir.parent, _this_dir.parents[1], _this_dir.parents[2]):
        _env_path = _parent / ".env"
        if _env_path.exists():
            load_dotenv(_env_path)
            break
    else:
        load_dotenv()  # fallback: search from cwd
except ImportError:
    pass  # dotenv not installed — rely on env vars being set

_SAFE_COL = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _validate_column_name(name: str) -> str:
    """Raise ValueError if *name* isn't a safe SQL identifier."""
    if not _SAFE_COL.match(name):
        raise ValueError(
            f"Invalid column name '{name}' – only letters, digits, "
            f"and underscores are allowed."
        )
    return name


def _load_casheet_tenders() -> dict:
    try:
        from ..cash_sheet_filler.config import CASHEET_TENDERS
    except ImportError:
        try:
            from BE.src.cash_sheet_filler.config import CASHEET_TENDERS
        except ImportError:
            from cash_sheet_filler.config import CASHEET_TENDERS
    return CASHEET_TENDERS


def _quote_col(name: str) -> str:
    """Quote column names that contain uppercase or are reserved words."""
    return f'"{name}"'


class TendersDBManager:
    """Singleton DB manager — reuses one connection for the process lifetime."""

    _instance: "TendersDBManager | None" = None
    _conn = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        self._database_url = os.environ.get("DATABASE_URL", "")
        if not self._database_url:
            print("[DB] WARNING: DATABASE_URL not set. DB operations will fail.")
        else:
            # Debug: show host portion only (mask password)
            try:
                from urllib.parse import urlparse
                parsed = urlparse(self._database_url)
                print(
                    f"[DB] Connecting to host: {parsed.hostname}:{parsed.port}")
            except Exception:
                pass

        self._tender_keys: list[str] | None = None
        self._table_columns: set[str] | None = None
        self._connect()

    # ── connection management ─────────────────────────────────────
    def _connect(self):
        """Open a persistent connection to Supabase PostgreSQL."""
        if not self._database_url:
            return
        if psycopg2 is None:
            print(
                "[DB] psycopg2 is not installed — run "
                "'pip install -r requirements.txt' to enable DB operations."
            )
            return
        try:
            self._conn = psycopg2.connect(
                self._database_url,
                cursor_factory=psycopg2.extras.RealDictCursor,
            )
            self._conn.autocommit = False
            self._table_columns = None
            print("[DB] Connected to Supabase PostgreSQL")
        except _DB_ERROR as e:
            print(f"[DB] Connection failed: {e}")
            self._conn = None

    @property
    def conn(self):
        """Return the live connection, re-opening if it was closed."""
        if self._conn is None or self._conn.closed:
            self._connect()
        return self._conn

    def close(self):
        """Explicitly close the connection (e.g. on app shutdown)."""
        if self._conn and not self._conn.closed:
            self._conn.close()
            self._conn = None

    # ── schema helpers ────────────────────────────────────────────
    def _get_table_columns(self) -> set[str]:
        """Return the live column set for tender_records."""
        if self._table_columns is not None:
            return self._table_columns

        if self.conn is None:
            self._table_columns = set()
            return self._table_columns

        try:
            with self.conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = 'tender_records'
                    """
                )
                rows = cur.fetchall()
            self._table_columns = {row["column_name"] for row in rows}
        except _DB_ERROR as e:
            print(f"[DB] Error loading schema info: {e}")
            self.conn.rollback()
            self._table_columns = set()

        return self._table_columns

    def _get_tender_keys(self) -> list[str]:
        """Load and cache the tender column names from config."""
        if self._tender_keys is None:
            configured_keys = [
                _validate_column_name(k)
                for k in _load_casheet_tenders().keys()
            ]
            table_columns = self._get_table_columns()
            if table_columns:
                self._tender_keys = [
                    key for key in configured_keys if key in table_columns
                ]
            else:
                self._tender_keys = configured_keys
        return self._tender_keys

    def reload_tender_keys(self):
        """Force-refresh cached tender keys (call after config save)."""
        self._tender_keys = None
        self._table_columns = None

    def _normalize_value(self, value):
        """Convert PostgreSQL-native values into UI-friendly Python values."""
        if isinstance(value, Decimal):
            return float(value)
        if hasattr(value, "isoformat"):
            return value.isoformat()
        return value

    def _normalize_row(self, row: dict | None) -> dict:
        if not row:
            return {}
        return {key: self._normalize_value(value) for key, value in row.items()}

    def _normalize_rows(self, rows: list[dict]) -> list[dict]:
        return [self._normalize_row(dict(row)) for row in rows]

    _VALID_SOURCES = frozenset({"infor", "tavlo", "grubhub", "manual", "seed"})

    # ── write operations ──────────────────────────────────────────
    def insert_record(
        self,
        source: str,
        raw_location: str,
        location: str,
        report_date: str,
        data_dict: dict | None = None,
        **kwargs,
    ) -> bool:
        """
        Upsert a tender record.

        On duplicate (date + raw_location + location + source), updates the
        data columns while preserving the original id and created_at.

        Returns True on success, False on failure.
        """
        if self.conn is None:
            print("[DB] No connection — skipping insert")
            return False

        if data_dict is None:
            data_dict = {}
        if kwargs:
            data_dict = {**data_dict, **kwargs}

        tender_keys = self._get_tender_keys()

        # ── normalise date ────────────────────────────────────────
        try:
            formatted_date = datetime.strptime(
                report_date, "%m/%d/%Y"
            ).strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            formatted_date = report_date  # already ISO or unknown format

        if source not in self._VALID_SOURCES:
            print(f"[DB] Invalid source '{source}' – "
                  f"expected one of {sorted(self._VALID_SOURCES)}")
            return False

        if not formatted_date or not location:
            print(f"[DB] Skipped insert – missing date or location: "
                  f"date={formatted_date!r}, loc={location!r}")
            return False

        total_sales = float(data_dict.get("total_sales", 0.0))
        tax = float(data_dict.get("tax", 0.0))
        meal_count = int(data_dict.get("meal_count", 0))
        tenders = data_dict.get("tenders", {})

        # Build column lists with proper quoting for mixed-case columns
        table_columns = self._get_table_columns()
        columns = ["report_date", "raw_location", "location", "source",
                   "total_sales", "tax", "meal_count"] + tender_keys
        if table_columns:
            columns = [column for column in columns if column in table_columns]

        quoted_cols = [_quote_col(c) for c in columns]
        placeholders = ", ".join(["%s"] * len(columns))
        col_list = ", ".join(quoted_cols)

        # ON CONFLICT → update everything except id, created_at, key cols
        conflict_keys = ["report_date", "raw_location", "location", "source"]
        update_cols = [c for c in columns if c not in conflict_keys]
        update_set = ", ".join(
            f"{_quote_col(c)} = EXCLUDED.{_quote_col(c)}"
            for c in update_cols
        )
        if not update_set:
            print("[DB] No writable columns available for insert")
            return False
        if not table_columns or "updated_at" in table_columns:
            update_set += ', "updated_at" = now()'

        conflict_quoted = ", ".join(_quote_col(c) for c in conflict_keys)

        values = [formatted_date, raw_location, location, source,
                  total_sales, tax, meal_count]
        for k in tender_keys:
            values.append(float(tenders.get(k, 0.0)))

        sql = f"""
            INSERT INTO tender_records ({col_list})
            VALUES ({placeholders})
            ON CONFLICT ({conflict_quoted}) DO UPDATE SET
                {update_set}
        """

        try:
            with self.conn.cursor() as cur:
                cur.execute(sql, values)
            self.conn.commit()
            return True
        except _DB_ERROR as e:
            print(f"[DB] Error inserting record: {e}")
            self.conn.rollback()
            return False

    def insert_many(self, records: list[dict]) -> int:
        """
        Batch-upsert a list of record dicts.
        Returns the count of successfully inserted/updated rows.
        """
        ok = 0
        for rec in records:
            source = rec.get("source", "infor")
            raw_location = rec.get("raw_location", "")
            location = rec.get("location", "")
            report_date = rec.get("report_date", "")
            if self.insert_record(
                source=source,
                raw_location=raw_location,
                location=location,
                report_date=report_date,
                data_dict=rec,
            ):
                ok += 1
        return ok

    # ── read operations ───────────────────────────────────────────
    def get_records(
        self,
        location: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        limit: int = 500,
    ) -> list[dict]:
        """
        Query records with optional filters.
        Dates should be ISO format (YYYY-MM-DD).
        """
        if self.conn is None:
            return []

        clauses: list[str] = []
        params: list = []

        if location:
            clauses.append("location = %s")
            params.append(location)
        if date_from:
            clauses.append("report_date >= %s")
            params.append(date_from)
        if date_to:
            clauses.append("report_date <= %s")
            params.append(date_to)

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = (
            f"SELECT * FROM tender_records {where} "
            f"ORDER BY report_date DESC, location "
            f"LIMIT %s"
        )
        params.append(limit)

        try:
            with self.conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()
            return self._normalize_rows(rows)
        except _DB_ERROR as e:
            print(f"[DB] Error fetching records: {e}")
            self.conn.rollback()
            return []

    def record_exists(
        self,
        report_date: str,
        location: str,
        source: str | None = None,
        raw_location: str | None = None,
    ) -> bool:
        """Check whether a record exists for date + location (+ source)."""
        if self.conn is None:
            return False

        clauses = ["report_date = %s", "location = %s"]
        params: list = [report_date, location]

        if source:
            clauses.append("source = %s")
            params.append(source)
        if raw_location:
            clauses.append("raw_location = %s")
            params.append(raw_location)

        where = " AND ".join(clauses)
        sql = f"SELECT 1 FROM tender_records WHERE {where} LIMIT 1"

        try:
            with self.conn.cursor() as cur:
                cur.execute(sql, params)
                row = cur.fetchone()
            return row is not None
        except _DB_ERROR as e:
            print(f"[DB] Error checking record existence: {e}")
            self.conn.rollback()
            return False

    def get_locations(self) -> list[str]:
        """Return all distinct location values."""
        if self.conn is None:
            return []
        try:
            with self.conn.cursor() as cur:
                cur.execute(
                    "SELECT DISTINCT location FROM tender_records ORDER BY location"
                )
                rows = cur.fetchall()
            return [r["location"] for r in rows if r.get("location")]
        except _DB_ERROR as e:
            print(f"[DB] Error fetching locations: {e}")
            self.conn.rollback()
            return []

    def row_count(self) -> int:
        """Total number of records."""
        if self.conn is None:
            return 0
        try:
            with self.conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) AS cnt FROM tender_records")
                row = cur.fetchone()
            return row["cnt"] if row else 0
        except _DB_ERROR as e:
            print(f"[DB] Error counting rows: {e}")
            self.conn.rollback()
            return 0

    # ── aggregate / analytics queries ─────────────────────────────
    def get_summary(
        self,
        locations: list[str] | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> dict:
        """
        Return an aggregate summary dict for the given filters.
        Keys: total_sales, tax, meal_count, record_count,
              plus every tender key with its sum.
        """
        if self.conn is None:
            return {}

        tender_keys = self._get_tender_keys()
        tender_sums = ", ".join(
            f'COALESCE(SUM({_quote_col(k)}), 0) AS {_quote_col(k)}'
            for k in tender_keys
        )

        clauses: list[str] = []
        params: list = []
        if locations:
            placeholders = ", ".join(["%s"] * len(locations))
            clauses.append(f"location IN ({placeholders})")
            params.extend(locations)
        if date_from:
            clauses.append("report_date >= %s")
            params.append(date_from)
        if date_to:
            clauses.append("report_date <= %s")
            params.append(date_to)

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = f"""
            SELECT
                COUNT(*)                       AS record_count,
                COALESCE(SUM(total_sales), 0)  AS total_sales,
                COALESCE(SUM(tax), 0)          AS tax,
                COALESCE(SUM(meal_count), 0)   AS meal_count,
                {tender_sums}
            FROM tender_records {where}
        """

        try:
            with self.conn.cursor() as cur:
                cur.execute(sql, params)
                row = cur.fetchone()
            return self._normalize_row(dict(row) if row else {})
        except _DB_ERROR as e:
            print(f"[DB] Error fetching summary: {e}")
            self.conn.rollback()
            return {}

    def get_daily_totals(
        self,
        locations: list[str] | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> list[dict]:
        """
        Return one row per date with summed totals (for line/bar charts).
        """
        if self.conn is None:
            return []

        tender_keys = self._get_tender_keys()
        tender_sums = ", ".join(
            f'COALESCE(SUM({_quote_col(k)}), 0) AS {_quote_col(k)}'
            for k in tender_keys
        )

        clauses: list[str] = []
        params: list = []
        if locations:
            placeholders = ", ".join(["%s"] * len(locations))
            clauses.append(f"location IN ({placeholders})")
            params.extend(locations)
        if date_from:
            clauses.append("report_date >= %s")
            params.append(date_from)
        if date_to:
            clauses.append("report_date <= %s")
            params.append(date_to)

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = f"""
            SELECT
                report_date,
                COALESCE(SUM(total_sales), 0) AS total_sales,
                COALESCE(SUM(tax), 0)         AS tax,
                COALESCE(SUM(meal_count), 0)  AS meal_count,
                {tender_sums}
            FROM tender_records {where}
            GROUP BY report_date
            ORDER BY report_date
        """

        try:
            with self.conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()
            return self._normalize_rows(rows)
        except _DB_ERROR as e:
            print(f"[DB] Error fetching daily totals: {e}")
            self.conn.rollback()
            return []

    def get_location_totals(
        self,
        locations: list[str] | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> list[dict]:
        """
        Return one row per location with summed totals (for pie/bar charts).
        """
        if self.conn is None:
            return []

        tender_keys = self._get_tender_keys()
        tender_sums = ", ".join(
            f'COALESCE(SUM({_quote_col(k)}), 0) AS {_quote_col(k)}'
            for k in tender_keys
        )

        clauses: list[str] = []
        params: list = []
        if locations:
            placeholders = ", ".join(["%s"] * len(locations))
            clauses.append(f"location IN ({placeholders})")
            params.extend(locations)
        if date_from:
            clauses.append("report_date >= %s")
            params.append(date_from)
        if date_to:
            clauses.append("report_date <= %s")
            params.append(date_to)

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = f"""
            SELECT
                location,
                COALESCE(SUM(total_sales), 0) AS total_sales,
                COALESCE(SUM(tax), 0)         AS tax,
                COALESCE(SUM(meal_count), 0)  AS meal_count,
                {tender_sums}
            FROM tender_records {where}
            GROUP BY location
            ORDER BY total_sales DESC
        """

        try:
            with self.conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()
            return self._normalize_rows(rows)
        except _DB_ERROR as e:
            print(f"[DB] Error fetching location totals: {e}")
            self.conn.rollback()
            return []

    def get_date_range(self) -> tuple[str | None, str | None]:
        """Return (min_date, max_date) across all records, or (None, None)."""
        if self.conn is None:
            return None, None
        try:
            with self.conn.cursor() as cur:
                cur.execute(
                    "SELECT MIN(report_date) AS min_d, MAX(report_date) AS max_d "
                    "FROM tender_records"
                )
                row = cur.fetchone()
            if row:
                # Convert date objects to ISO strings for consistency
                min_d = str(row["min_d"]) if row["min_d"] else None
                max_d = str(row["max_d"]) if row["max_d"] else None
                return min_d, max_d
            return None, None
        except _DB_ERROR as e:
            print(f"[DB] Error fetching date range: {e}")
            self.conn.rollback()
            return None, None
