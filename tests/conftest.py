"""
tests/conftest.py

Shared pytest fixtures for the AI Talent Platform test suite.

Uses NullPool so every request gets a fresh connection — no stale
asyncpg connections between tests. Tables are truncated before each test.
"""
import os

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

TEST_DB_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/talent_platform",
)


def _make_engine():
    return create_async_engine(TEST_DB_URL, poolclass=NullPool)


@pytest_asyncio.fixture
async def _clean_tables():
    """Truncate all app tables before each test."""
    from packages.core.db.models import Base

    engine = _make_engine()
    async with engine.begin() as conn:
        for tname in [t.name for t in reversed(Base.metadata.sorted_tables)]:
            await conn.execute(text(f'TRUNCATE TABLE "{tname}" CASCADE'))
    await engine.dispose()


@pytest_asyncio.fixture
async def client(_clean_tables):
    """HTTPX async client wired to the FastAPI app with an isolated session per request."""
    from packages.api.deps import get_db
    from packages.api.main import app

    request_engine = _make_engine()
    _Session = async_sessionmaker(request_engine, class_=AsyncSession, expire_on_commit=False)

    async def _get_test_db():
        async with _Session() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = _get_test_db
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
    app.dependency_overrides.pop(get_db, None)
    await request_engine.dispose()


@pytest_asyncio.fixture
async def session(_clean_tables):
    """Raw async DB session for tests that query the DB directly."""
    engine = _make_engine()
    _Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with _Session() as sess:
        yield sess
    await engine.dispose()
