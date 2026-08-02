from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

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


def _admin_conninfo(dbname: str = "postgres", *, use_socket: bool = False) -> str:
    parts = [
        f"dbname={dbname}",
        f"user={PGUSER}",
    ]
    if use_socket:
        # Ubuntu peer auth via local socket (works when OS user == PGUSER, e.g. postgres)
        sock = Path("/var/run/postgresql")
        if sock.is_dir():
            parts.append(f"host={sock}")
    else:
        parts.extend([f"host={PGHOST}", f"port={PGPORT}"])
        if PGPASSWORD:
            parts.append(f"password={PGPASSWORD}")
    return " ".join(parts)


def _sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _psql_as_postgres(sql: str) -> str:
    """Run SQL as OS user postgres (peer auth). Returns stdout."""
    sudo = shutil.which("sudo")
    if not sudo:
        raise RuntimeError("sudo not found; set PGPASSWORD in .env for TCP auth")
    cmd = [
        sudo,
        "-u",
        "postgres",
        "psql",
        "-v",
        "ON_ERROR_STOP=1",
        "-tAc",
        sql,
    ]
    proc = subprocess.run(cmd, check=True, capture_output=True, text=True)
    return (proc.stdout or "").strip()


def _ensure_via_psycopg(*, use_socket: bool) -> None:
    mode = "unix socket" if use_socket else f"{PGHOST}:{PGPORT}"
    print(f"Connecting to PostgreSQL via {mode} as {PGUSER}…")
    with psycopg.connect(_admin_conninfo(use_socket=use_socket), autocommit=True) as conn:
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

    with psycopg.connect(
        _admin_conninfo(WIKI_DB, use_socket=use_socket), autocommit=True
    ) as conn:
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
            cur.execute(
                f'ALTER ROLE "{WIKI_DB_USER}" SET search_path TO "{WIKI_DB_SCHEMA}", public'
            )


def _ensure_via_sudo_postgres() -> None:
    """Ubuntu/Debian default: peer auth as OS user postgres, no password."""
    print("Connecting via sudo -u postgres psql (peer auth)…")
    pwd = _sql_literal(WIKI_DB_PASS)

    exists = _psql_as_postgres(
        f"SELECT 1 FROM pg_roles WHERE rolname = {_sql_literal(WIKI_DB_USER)}"
    )
    if exists != "1":
        _psql_as_postgres(
            f'CREATE ROLE "{WIKI_DB_USER}" LOGIN PASSWORD {pwd}'
        )
        print(f"Created role {WIKI_DB_USER}")
    else:
        _psql_as_postgres(
            f'ALTER ROLE "{WIKI_DB_USER}" WITH LOGIN PASSWORD {pwd}'
        )
        print(f"Role {WIKI_DB_USER} already exists (password refreshed)")

    exists = _psql_as_postgres(
        f"SELECT 1 FROM pg_database WHERE datname = {_sql_literal(WIKI_DB)}"
    )
    if exists != "1":
        _psql_as_postgres(
            f'CREATE DATABASE "{WIKI_DB}" OWNER "{WIKI_DB_USER}" '
            f"ENCODING 'UTF8' TEMPLATE template0"
        )
        print(f"Created database {WIKI_DB}")
    else:
        print(f"Database {WIKI_DB} already exists")

    exists = _psql_as_postgres(
        f"SELECT 1 FROM information_schema.schemata WHERE schema_name = {_sql_literal(WIKI_DB_SCHEMA)}"
    )
    # information_schema query must run against the wiki DB
    cmd_schema_check = [
        "sudo",
        "-u",
        "postgres",
        "psql",
        "-d",
        WIKI_DB,
        "-v",
        "ON_ERROR_STOP=1",
        "-tAc",
        f"SELECT 1 FROM information_schema.schemata WHERE schema_name = {_sql_literal(WIKI_DB_SCHEMA)}",
    ]
    proc = subprocess.run(cmd_schema_check, check=True, capture_output=True, text=True)
    if proc.stdout.strip() != "1":
        subprocess.run(
            [
                "sudo",
                "-u",
                "postgres",
                "psql",
                "-d",
                WIKI_DB,
                "-v",
                "ON_ERROR_STOP=1",
                "-c",
                f'CREATE SCHEMA "{WIKI_DB_SCHEMA}" AUTHORIZATION "{WIKI_DB_USER}"',
            ],
            check=True,
        )
        print(f"Created schema {WIKI_DB_SCHEMA}")
    else:
        print(f"Schema {WIKI_DB_SCHEMA} already exists")

    for sql in (
        f'GRANT ALL ON SCHEMA "{WIKI_DB_SCHEMA}" TO "{WIKI_DB_USER}"',
        f'GRANT ALL ON DATABASE "{WIKI_DB}" TO "{WIKI_DB_USER}"',
        f'ALTER ROLE "{WIKI_DB_USER}" SET search_path TO "{WIKI_DB_SCHEMA}", public',
    ):
        subprocess.run(
            [
                "sudo",
                "-u",
                "postgres",
                "psql",
                "-d",
                WIKI_DB,
                "-v",
                "ON_ERROR_STOP=1",
                "-c",
                sql,
            ],
            check=True,
        )


def ensure_database() -> None:
    """Create wiki role, database and schema if missing (idempotent)."""
    errors: list[str] = []

    # 1) TCP with password from .env
    if PGPASSWORD:
        try:
            _ensure_via_psycopg(use_socket=False)
            print("PostgreSQL ready.")
            return
        except psycopg.Error as e:
            errors.append(f"TCP+password: {e}")

    # 2) TCP without password (rare; trust auth)
    try:
        _ensure_via_psycopg(use_socket=False)
        print("PostgreSQL ready.")
        return
    except psycopg.Error as e:
        errors.append(f"TCP: {e}")

    # 3) Ubuntu default: sudo -u postgres peer
    try:
        _ensure_via_sudo_postgres()
        print("PostgreSQL ready.")
        return
    except (RuntimeError, subprocess.CalledProcessError, FileNotFoundError) as e:
        errors.append(f"sudo -u postgres: {e}")

    hint = (
        "Could not connect to PostgreSQL.\n"
        "On Ubuntu, either:\n"
        "  sudo apt install -y postgresql postgresql-contrib\n"
        "  sudo systemctl enable --now postgresql\n"
        "and re-run (script will use sudo -u postgres),\n"
        "or set PGPASSWORD in .env for the postgres superuser.\n"
        "Details:\n  - " + "\n  - ".join(errors)
    )
    raise SystemExit(hint)


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if argv and argv[0] in ("-h", "--help"):
        print("Usage: python -m tools db\nCreate wiki PostgreSQL role/database/schema.")
        return 0
    try:
        ensure_database()
    except SystemExit as e:
        if e.code and e.code != 0:
            print(e.args[0] if e.args else e, file=sys.stderr)
            return int(e.code) if isinstance(e.code, int) else 1
        raise
    except psycopg.Error as e:
        print(f"PostgreSQL error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
