from __future__ import annotations

import sys

import psycopg

from tools.config import (
    PGHOST,
    PGPASSWORD,
    PGPORT,
    PGUSER,
    WIKI_DB,
    WIKI_DB_PASS,
    WIKI_DB_SCHEMA,
    WIKI_DB_USER,
)


def _admin_conninfo(dbname: str = "postgres") -> str:
    parts = [
        f"host={PGHOST}",
        f"port={PGPORT}",
        f"dbname={dbname}",
        f"user={PGUSER}",
    ]
    if PGPASSWORD:
        parts.append(f"password={PGPASSWORD}")
    return " ".join(parts)


def ensure_database() -> None:
    """Create wiki role, database and schema if missing (idempotent)."""
    print(f"Connecting to PostgreSQL at {PGHOST}:{PGPORT} as {PGUSER}…")
    with psycopg.connect(_admin_conninfo(), autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (WIKI_DB_USER,))
            if cur.fetchone() is None:
                cur.execute(
                    f'CREATE ROLE "{WIKI_DB_USER}" LOGIN PASSWORD %s',
                    (WIKI_DB_PASS,),
                )
                print(f"Created role {WIKI_DB_USER}")
            else:
                cur.execute(
                    f'ALTER ROLE "{WIKI_DB_USER}" WITH LOGIN PASSWORD %s',
                    (WIKI_DB_PASS,),
                )
                print(f"Role {WIKI_DB_USER} already exists (password refreshed)")

            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (WIKI_DB,))
            if cur.fetchone() is None:
                cur.execute(
                    f'CREATE DATABASE "{WIKI_DB}" OWNER "{WIKI_DB_USER}" '
                    f"ENCODING 'UTF8' TEMPLATE template0"
                )
                print(f"Created database {WIKI_DB}")
            else:
                print(f"Database {WIKI_DB} already exists")

    with psycopg.connect(_admin_conninfo(WIKI_DB), autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM information_schema.schemata WHERE schema_name = %s",
                (WIKI_DB_SCHEMA,),
            )
            if cur.fetchone() is None:
                cur.execute(
                    f'CREATE SCHEMA "{WIKI_DB_SCHEMA}" AUTHORIZATION "{WIKI_DB_USER}"'
                )
                print(f"Created schema {WIKI_DB_SCHEMA}")
            else:
                print(f"Schema {WIKI_DB_SCHEMA} already exists")

            cur.execute(f'GRANT ALL ON SCHEMA "{WIKI_DB_SCHEMA}" TO "{WIKI_DB_USER}"')
            cur.execute(f'GRANT ALL ON DATABASE "{WIKI_DB}" TO "{WIKI_DB_USER}"')
            # MediaWiki expects search_path including its schema
            cur.execute(
                f'ALTER ROLE "{WIKI_DB_USER}" SET search_path TO "{WIKI_DB_SCHEMA}", public'
            )
    print("PostgreSQL ready.")


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if argv and argv[0] in ("-h", "--help"):
        print("Usage: python -m tools db\nCreate wiki PostgreSQL role/database/schema.")
        return 0
    try:
        ensure_database()
    except psycopg.Error as e:
        print(f"PostgreSQL error: {e}", file=sys.stderr)
        print(
            "Check PGHOST/PGPORT/PGUSER/PGPASSWORD in .env and that PostgreSQL is running.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
