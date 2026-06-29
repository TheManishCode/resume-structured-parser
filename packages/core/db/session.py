"""
packages/core/db/session.py

Async SQLAlchemy engine + session factory.
Connection string read from DATABASE_URL env var.

Security:
  - pool_size / max_overflow prevent connection-exhaustion under load
  - pool_recycle prevents stale connections on long-lived deployments
  - SSL enforced when DATABASE_SSL_MODE=require (set this in production)
  - pool_pre_ping validates connections before use (no silent reconnect failures)
"""
from __future__ import annotations

import os

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/talent_platform",
)

_POOL_SIZE     = int(os.getenv("DB_POOL_SIZE",     "10"))
_MAX_OVERFLOW  = int(os.getenv("DB_MAX_OVERFLOW",  "20"))
_POOL_TIMEOUT  = int(os.getenv("DB_POOL_TIMEOUT",  "30"))
_POOL_RECYCLE  = int(os.getenv("DB_POOL_RECYCLE",  "1800"))

# SSL: set DATABASE_SSL_MODE=require in production to enforce TLS
_SSL_MODE = os.getenv("DATABASE_SSL_MODE", "")
_connect_args: dict = {}
if _SSL_MODE == "require":
    _connect_args["ssl"] = "require"

engine = create_async_engine(
    DATABASE_URL,
    echo=bool(os.getenv("DB_ECHO", "")),
    pool_pre_ping=True,
    pool_size=_POOL_SIZE,
    max_overflow=_MAX_OVERFLOW,
    pool_timeout=_POOL_TIMEOUT,
    pool_recycle=_POOL_RECYCLE,
    connect_args=_connect_args,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncSession:
    """FastAPI dependency — yields an async session and commits/rolls back."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
