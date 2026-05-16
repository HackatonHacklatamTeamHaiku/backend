from __future__ import annotations

import os
from pathlib import Path

import psycopg2
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"
MIGRATIONS_DIR = ROOT / "migrations"


def main() -> None:
    load_dotenv(ENV_PATH)
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set in backend/backend/.env")

    migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    if not migration_files:
        print("No migration files found.")
        return

    conn = psycopg2.connect(database_url)
    try:
        with conn:
            with conn.cursor() as cur:
                for migration_path in migration_files:
                    print(f"Applying {migration_path.name} ...")
                    sql = migration_path.read_text(encoding="utf-8")
                    cur.execute(sql)
        print("All migrations applied successfully.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
