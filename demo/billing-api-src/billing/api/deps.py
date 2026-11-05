"""Request-scoped database connection."""
from billing import db


def get_conn():
    conn = db.connect()
    try:
        yield conn
    finally:
        conn.close()
