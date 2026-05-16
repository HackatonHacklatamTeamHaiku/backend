from __future__ import annotations

import os
from pathlib import Path

import psycopg2
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"


def main() -> None:
    load_dotenv(ENV_PATH)
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set in backend/backend/.env")

    conn = psycopg2.connect(database_url)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "select current_database(), current_user, current_schema()"
            )
            database, user, schema = cur.fetchone()
            print(f"database={database}")
            print(f"user={user}")
            print(f"schema={schema}")

            cur.execute(
                """
                select table_name
                from information_schema.tables
                where table_schema = 'public'
                order by table_name
                """
            )
            tables = [row[0] for row in cur.fetchall()]
            print(f"public_tables={len(tables)}")
            for table_name in tables:
                print(f" - {table_name}")

            cur.execute(
                """
                select typname
                from pg_type
                where typnamespace = 'public'::regnamespace
                and typtype = 'e'
                order by typname
                """
            )
            enums = [row[0] for row in cur.fetchall()]
            print(f"public_enums={len(enums)}")
            for enum_name in enums:
                print(f" - {enum_name}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
