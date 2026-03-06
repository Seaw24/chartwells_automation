"""
Database Manager for Autofill Transaction Tracking
──────────────────────────────────────────────────
Handles all SQLite operations for logging and querying autofill transactions.

Design choices
• Singleton – only ONE instance & ONE connection per process.
• WAL journal – set once; persistent across connections.
• UPSERT (INSERT … ON CONFLICT … DO UPDATE) – preserves the original row-id
  and created_at timestamp while updating changed fields.
• NOT NULL on the UNIQUE-key columns so the constraint actually fires.
• Column-name validation – rejects anything that isn't [a-zA-Z0-9_].
"""

import re
import sqlite3
from datetime import datetime
from pathlib import Path

try:
    from ..path_helper import get_app_dir
except ImportError:
    try:
        from BE.src.path_helper import get_app_dir
    except ImportError:
        from path_helper import get_app_dir

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
        from BE.src.cash_sheet_filler.config import CASHEET_TENDERS
    return CASHEET_TENDERS


class TendersDBManager:
    """Singleton DB manager – reuses one connection for the process lifetime."""

    _instance: "TendersDBManager | None" = None
    _conn: sqlite3.Connection | None = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return  # already set up
        self._initialized = True

        root_dir = get_app_dir()
        db_dir = root_dir / "DB"
        db_dir.mkdir(parents=True, exist_ok=True)

        self.db_path = str(db_dir / "tenders_archive.db")
        self._tender_keys: list[str] | None = None  # cached tender column list
        self._connect()
        self._initialize_database()

    # ── connection management ─────────────────────────────────────
    def _connect(self):
        """Open a persistent connection with performance pragmas."""
        self._conn = sqlite3.connect(
            self.db_path, timeout=10, check_same_thread=False,
        )
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")  # safe with WAL
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.row_factory = sqlite3.Row  # dict-like rows

    @property
    def conn(self) -> sqlite3.Connection:
        """Return the live connection, re-opening if it was closed."""
        if self._conn is None:
            self._connect()
        return self._conn

    def close(self):
        """Explicitly close the connection (e.g. on app shutdown)."""
        if self._conn:
            self._conn.close()
            self._conn = None

    # ── schema / migration ────────────────────────────────────────
    def _get_tender_keys(self) -> list[str]:
        """Load and cache the tender column names from config."""
        if self._tender_keys is None:
            self._tender_keys = [
                _validate_column_name(k)
                for k in _load_casheet_tenders().keys()
            ]
        return self._tender_keys

    def reload_tender_keys(self):
        """Force-refresh cached tender keys (call after config save)."""
        self._tender_keys = None
        self._initialize_database()

    _SCHEMA_VERSION = 3  # bump when changing the table structure
    _VALID_SOURCES = frozenset({"infor", "tavlo", "grubhub", "manual", "seed"})

    def _initialize_database(self):
        tender_keys = self._get_tender_keys()
        conn = self.conn

        # ── check current schema version ──────────────────────────
        conn.execute(
            "CREATE TABLE IF NOT EXISTS _schema_meta "
            "(key TEXT PRIMARY KEY, value TEXT)"
        )
        row = conn.execute(
            "SELECT value FROM _schema_meta WHERE key='version'"
        ).fetchone()
        current_version = int(row[0]) if row else 0

        # ── build the ideal CREATE TABLE statement ────────────────
        tender_cols = "\n".join(
            f"    {k} REAL DEFAULT 0.0," for k in tender_keys
        )
        ideal_create = f"""
        CREATE TABLE IF NOT EXISTS tender_records (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            report_date DATE    NOT NULL,
            location    TEXT    NOT NULL,
            source      TEXT    NOT NULL DEFAULT 'infor',
            total_sales REAL    DEFAULT 0.0,
            tax         REAL    DEFAULT 0.0,
            meal_count  INTEGER DEFAULT 0,
        {tender_cols}
            created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(report_date, location, source)
        )
        """

        # ── full migration: rebuild table if schema version is old ─
        if current_version < self._SCHEMA_VERSION:
            table_exists = conn.execute(
                "SELECT 1 FROM sqlite_master "
                "WHERE type='table' AND name='tender_records'"
            ).fetchone()

            if table_exists:
                # Migrate: copy data to temp → drop → recreate → copy back
                conn.execute(
                    "ALTER TABLE tender_records RENAME TO _tender_old"
                )
                conn.execute(ideal_create)

                # find columns that exist in both old and new tables
                old_cols = {
                    r[1] for r in
                    conn.execute("PRAGMA table_info(_tender_old)").fetchall()
                }
                new_cols = {
                    r[1] for r in
                    conn.execute(
                        "PRAGMA table_info(tender_records)").fetchall()
                }
                shared = sorted(old_cols & new_cols - {"id"})

                if shared:
                    col_list = ", ".join(shared)
                    # map old 'timestamp' → new 'created_at' if applicable
                    src_cols = []
                    for c in shared:
                        if c == "created_at" and "created_at" not in old_cols and "timestamp" in old_cols:
                            src_cols.append("timestamp")
                        else:
                            src_cols.append(c)
                    src_list = ", ".join(src_cols)
                    conn.execute(
                        f"INSERT OR IGNORE INTO tender_records ({col_list}) "
                        f"SELECT {src_list} FROM _tender_old"
                    )

                conn.execute("DROP TABLE _tender_old")
            else:
                conn.execute(ideal_create)

            # stamp the version
            conn.execute(
                "INSERT OR REPLACE INTO _schema_meta (key, value) "
                "VALUES ('version', ?)",
                (str(self._SCHEMA_VERSION),),
            )
            conn.commit()
            return  # migration done, no need for incremental patches

        # ── table exists at current version — just add any new tender cols ─
        conn.execute(ideal_create)
        existing = {
            row[1] for row in conn.execute(
                "PRAGMA table_info(tender_records)"
            ).fetchall()
        }

        for k in tender_keys:
            if k not in existing:
                conn.execute(
                    f"ALTER TABLE tender_records "
                    f"ADD COLUMN {k} REAL DEFAULT 0.0"
                )

        conn.commit()

    # ── write operations ──────────────────────────────────────────
    def insert_record(self, data_dict=None, **kwargs) -> bool:
        """
        Upsert a tender record.

        On duplicate (date + location + source), updates the data
        columns while preserving the original id and created_at.
        Different sources (infor / tavlo / grubhub) are stored as
        separate rows so they never overwrite each other.

        Accepts ``source`` in *data_dict* or as a keyword argument.
        Valid sources: infor, tavlo, grubhub, manual, seed.
        Defaults to 'infor' if omitted.

        Returns True on success, False on failure.
        """
        if data_dict is None:
            data_dict = {}
        if kwargs:
            data_dict = {**data_dict, **kwargs}

        tender_keys = self._get_tender_keys()

        # ── normalise date ────────────────────────────────────────
        raw_date = data_dict.get("report_date", "")
        try:
            formatted_date = datetime.strptime(
                raw_date, "%m/%d/%Y"
            ).strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            formatted_date = raw_date  # already ISO or unknown format

        location = data_dict.get("location")
        source = data_dict.get("source", "infor").lower()
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

        columns = ["report_date", "location", "source",
                   "total_sales", "tax", "meal_count"] + tender_keys
        placeholders = ", ".join(["?"] * len(columns))
        col_list = ", ".join(columns)

        # ON CONFLICT → update everything except id, created_at, key cols
        update_set = ", ".join(
            f"{c} = excluded.{c}"
            for c in columns
            if c not in ("report_date", "location", "source")
        )
        update_set += ", updated_at = CURRENT_TIMESTAMP"

        values = [formatted_date, location, source,
                  total_sales, tax, meal_count]
        for k in tender_keys:
            values.append(float(tenders.get(k, 0.0)))

        sql = f"""
            INSERT INTO tender_records ({col_list})
            VALUES ({placeholders})
            ON CONFLICT(report_date, location, source) DO UPDATE SET
                {update_set}
        """

        try:
            self.conn.execute(sql, values)
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"[DB] Error inserting record: {e}")
            return False

    def insert_many(self, records: list[dict]) -> int:
        """
        Batch-upsert a list of record dicts.
        Returns the count of successfully inserted/updated rows.
        Much faster than calling insert_record() in a loop
        because it wraps everything in a single transaction.
        """
        ok = 0
        try:
            with self.conn:
                for rec in records:
                    if self.insert_record(rec):
                        ok += 1
        except sqlite3.Error as e:
            print(f"[DB] Batch insert error: {e}")
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
        Returns a list of dicts.
        """
        clauses: list[str] = []
        params: list = []

        if location:
            clauses.append("location = ?")
            params.append(location)
        if date_from:
            clauses.append("report_date >= ?")
            params.append(date_from)
        if date_to:
            clauses.append("report_date <= ?")
            params.append(date_to)

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = (
            f"SELECT * FROM tender_records {where} "
            f"ORDER BY report_date DESC, location "
            f"LIMIT ?"
        )
        params.append(limit)

        rows = self.conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def record_exists(
        self,
        report_date: str,
        location: str,
        source: str | None = None,
    ) -> bool:
        """Check whether a record exists for date + location (+ source)."""
        if source:
            row = self.conn.execute(
                "SELECT 1 FROM tender_records "
                "WHERE report_date = ? AND location = ? "
                "AND source = ? LIMIT 1",
                (report_date, location, source),
            ).fetchone()
        else:
            row = self.conn.execute(
                "SELECT 1 FROM tender_records "
                "WHERE report_date = ? AND location = ? LIMIT 1",
                (report_date, location),
            ).fetchone()
        return row is not None

    def get_locations(self) -> list[str]:
        """Return all distinct location values."""
        self._fresh_read()
        rows = self.conn.execute(
            "SELECT DISTINCT location FROM tender_records ORDER BY location"
        ).fetchall()
        return [r[0] for r in rows]

    def row_count(self) -> int:
        """Total number of records."""
        return self.conn.execute(
            "SELECT COUNT(*) FROM tender_records"
        ).fetchone()[0]

    # ── aggregate / analytics queries ─────────────────────────────
    def _fresh_read(self):
        """Ensure the connection sees the latest committed data (WAL mode)."""
        self.conn.commit()          # close any implicit read-txn snapshot

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
        self._fresh_read()
        tender_keys = self._get_tender_keys()
        tender_sums = ", ".join(
            f"COALESCE(SUM({k}), 0) AS {k}" for k in tender_keys)

        clauses: list[str] = []
        params: list = []
        if locations:
            placeholders = ", ".join("?" * len(locations))
            clauses.append(f"location IN ({placeholders})")
            params.extend(locations)
        if date_from:
            clauses.append("report_date >= ?")
            params.append(date_from)
        if date_to:
            clauses.append("report_date <= ?")
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
        row = self.conn.execute(sql, params).fetchone()
        return dict(row) if row else {}

    def get_daily_totals(
        self,
        locations: list[str] | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> list[dict]:
        """
        Return one row per date with summed totals (for line/bar charts).
        Each dict has report_date, total_sales, tax, meal_count, plus tenders.
        """
        self._fresh_read()
        tender_keys = self._get_tender_keys()
        tender_sums = ", ".join(
            f"COALESCE(SUM({k}), 0) AS {k}" for k in tender_keys)

        clauses: list[str] = []
        params: list = []
        if locations:
            placeholders = ", ".join("?" * len(locations))
            clauses.append(f"location IN ({placeholders})")
            params.extend(locations)
        if date_from:
            clauses.append("report_date >= ?")
            params.append(date_from)
        if date_to:
            clauses.append("report_date <= ?")
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
        rows = self.conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def get_location_totals(
        self,
        locations: list[str] | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> list[dict]:
        """
        Return one row per location with summed totals (for pie/bar charts).
        """
        self._fresh_read()
        tender_keys = self._get_tender_keys()
        tender_sums = ", ".join(
            f"COALESCE(SUM({k}), 0) AS {k}" for k in tender_keys)

        clauses: list[str] = []
        params: list = []
        if locations:
            placeholders = ", ".join("?" * len(locations))
            clauses.append(f"location IN ({placeholders})")
            params.extend(locations)
        if date_from:
            clauses.append("report_date >= ?")
            params.append(date_from)
        if date_to:
            clauses.append("report_date <= ?")
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
        rows = self.conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def get_date_range(self) -> tuple[str | None, str | None]:
        """Return (min_date, max_date) across all records, or (None, None)."""
        self._fresh_read()
        row = self.conn.execute(
            "SELECT MIN(report_date), MAX(report_date) FROM tender_records"
        ).fetchone()
        if row:
            return row[0], row[1]
        return None, None
