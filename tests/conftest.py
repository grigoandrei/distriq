import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from distriq.api.app import app
from distriq.database import get_db
from distriq.models.database import Base
from distriq.config import settings


@pytest.fixture
async def client():
    """HTTP test client with a fresh database for each test."""
    # Create a fresh engine per test to avoid connection state issues
    engine = create_async_engine(settings.database_url, pool_size=5, max_overflow=0)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    # Override the get_db dependency
    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    # Provide the test client
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    # Cleanup
    app.dependency_overrides.clear()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
