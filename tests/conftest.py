import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from distriq.api.app import app
from distriq.database import get_db
from distriq.models.database import Base
from distriq.config import settings


# Use TEST_DATABASE_URL if set, otherwise append _test to the main URL
test_db_url = settings.test_database_url or settings.database_url.replace("/distriq", "/distriq_test")
test_engine = create_async_engine(test_db_url, pool_size=5, max_overflow=0)
test_session_factory = async_sessionmaker(test_engine, expire_on_commit=False)


@pytest.fixture
async def client():
    """HTTP test client with isolated test database."""
    # Create all tables in the test database
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    # Override the get_db dependency to use test database
    async def override_get_db():
        async with test_session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    # Cleanup
    app.dependency_overrides.clear()
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()
