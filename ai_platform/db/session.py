"""Database session management with support for PostgreSQL and SQLite in-memory testing."""

import os
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from ai_platform.db.models import Base

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///:memory:"
)

# Convert postgres:// to postgresql:// if needed for SQLAlchemy 2.0
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

if DATABASE_URL.startswith("postgresql://"):
    try:
        import psycopg2  # noqa: F401
    except ImportError:
        try:
            import psycopg  # noqa: F401
        except ImportError:
            # Fall back to sqlite if no postgres driver is installed in local dev
            DATABASE_URL = "sqlite:///:memory:"

from sqlalchemy.pool import StaticPool

is_sqlite = DATABASE_URL.startswith("sqlite")
connect_args = {"check_same_thread": False} if is_sqlite else {}
engine_kwargs = {"connect_args": connect_args, "echo": False}
if is_sqlite and (":memory:" in DATABASE_URL or DATABASE_URL == "sqlite://"):
    engine_kwargs["poolclass"] = StaticPool

engine = create_engine(DATABASE_URL, **engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Initialize database tables for non-Alembic test environments."""
    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency for yielding database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
