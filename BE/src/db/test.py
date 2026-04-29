import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    load_dotenv = None

try:
    import psycopg2
except ModuleNotFoundError:
    print(
        "[DB TEST] psycopg2 is not installed. "
        "Run 'pip install -r requirements.txt' first."
    )
    raise SystemExit(1)


def _load_env() -> None:
    if load_dotenv is None:
        return

    for parent in Path(__file__).resolve().parents:
        env_path = parent / ".env"
        if env_path.exists():
            load_dotenv(env_path)
            return

    load_dotenv()


def main() -> int:
    _load_env()
    database_url = os.environ.get("DATABASE_URL")

    if not database_url:
        print(
            "[DB TEST] DATABASE_URL is not set. Add it to your environment "
            "or to a .env file before testing the database connection."
        )
        return 1

    try:
        conn = psycopg2.connect(database_url)
    except psycopg2.Error as exc:
        print(f"[DB TEST] Connection failed: {exc}")
        return 1

    print("[DB TEST] Connected!")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
