"""SQLite connection and schema setup."""
import os
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def db_path():
    return os.environ.get("BILLING_DB", str(ROOT / "billing.db"))


def connect(path=None):
    conn = sqlite3.connect(path or db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn):
    """Apply migrations in order, then load rate data."""
    for sql_file in sorted((ROOT / "migrations").glob("*.sql")):
        conn.executescript(sql_file.read_text())
    conn.executescript((ROOT / "db" / "rates.sql").read_text())
    conn.commit()
