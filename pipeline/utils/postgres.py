import os
import psycopg2
import psycopg2.extras
from contextlib import contextmanager
from pipeline.utils.logger import get_logger

logger = get_logger(__name__)


def get_dsn() -> str:
    dsn = os.getenv("POSTGRES_DSN")
    if not dsn:
        raise EnvironmentError("POSTGRES_DSN environment variable is not set")
    return dsn


@contextmanager
def get_connection():
    """Yield a psycopg2 connection. Commits on clean exit, rolls back on error."""
    conn = psycopg2.connect(get_dsn())
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@contextmanager
def get_cursor(row_factory=psycopg2.extras.RealDictCursor):
    """Yield a cursor with dict-style row access by default."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=row_factory) as cur:
            yield cur


def execute(sql: str, params=None) -> None:
    with get_cursor() as cur:
        cur.execute(sql, params)


def fetchall(sql: str, params=None) -> list[dict]:
    with get_cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def fetchone(sql: str, params=None) -> dict | None:
    with get_cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchone()
