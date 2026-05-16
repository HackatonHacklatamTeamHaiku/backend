"""
Database connection layer for Supabase PostgreSQL.

Provides a thin connection-pool wrapper using psycopg2.
All queries should go through get_connection() context manager.

Usage:
    from services.database import get_connection

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            result = cur.fetchone()
"""

from __future__ import annotations

import logging
from contextlib import contextmanager

import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)

# Module-level connection pool, lazily initialized
_pool: pool.ThreadedConnectionPool | None = None


def init_pool(database_url: str, minconn: int = 1, maxconn: int = 5) -> None:
    """Initialize the connection pool. Call once during app startup."""
    global _pool
    if _pool is not None:
        logger.warning("Database pool already initialized — skipping.")
        return

    if not database_url:
        logger.warning(
            "DATABASE_URL is not set. Database features will be unavailable."
        )
        return

    try:
        _pool = pool.ThreadedConnectionPool(
            minconn,
            maxconn,
            database_url,
        )
        logger.info("Database connection pool initialized (min=%d, max=%d)", minconn, maxconn)
    except psycopg2.Error:
        logger.exception("Failed to initialize database pool")
        raise


def close_pool() -> None:
    """Close all connections in the pool. Call during app teardown."""
    global _pool
    if _pool is not None:
        _pool.closeall()
        _pool = None
        logger.info("Database connection pool closed.")


@contextmanager
def get_connection():
    """
    Context manager that yields a psycopg2 connection from the pool.
    Commits on success, rolls back on error, always returns connection to pool.
    """
    if _pool is None:
        raise RuntimeError(
            "Database pool not initialized. "
            "Ensure DATABASE_URL is set and init_pool() was called."
        )

    conn = _pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        _pool.putconn(conn)


@contextmanager
def get_dict_cursor():
    """
    Convenience context manager that yields a RealDictCursor.
    Handles connection lifecycle automatically.
    """
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            yield cur


def check_connection() -> bool:
    """Quick connectivity check. Returns True if the DB is reachable."""
    if _pool is None:
        return False
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                return cur.fetchone()[0] == 1
    except Exception:
        logger.exception("Database health check failed")
        return False
