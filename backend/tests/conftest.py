from collections.abc import AsyncGenerator, Generator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, insert
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from src.accounts.models import UserGroup, UserGroupEnum
from src.config.settings import get_settings
from src.database.base import Base
from src.database.session import get_db
from src.main import app

settings = get_settings()

TEST_DATABASE_URL = settings.database_url.set(database=f"{settings.POSTGRES_DB}_test")

# NullPool: every connection is opened in the current test's event loop
# and closed afterwards, so connections never leak between loops.
test_engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)


@pytest.fixture(scope="session")
def create_schema() -> Generator[None]:
    """Create tables and seed user groups once per test session."""
    sync_engine = create_engine(TEST_DATABASE_URL)
    Base.metadata.drop_all(sync_engine)
    Base.metadata.create_all(sync_engine)
    with sync_engine.begin() as connection:
        connection.execute(
            insert(UserGroup), [{"name": group} for group in UserGroupEnum]
        )

    yield

    Base.metadata.drop_all(sync_engine)
    sync_engine.dispose()


@pytest.fixture
async def db_session(create_schema: None) -> AsyncGenerator[AsyncSession]:
    """Session whose changes are rolled back after each test.

    `commit()` inside the code under test only releases a savepoint;
    the outer transaction is rolled back at teardown.
    """
    async with test_engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(
            bind=connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )

        yield session

        await session.close()
        await transaction.rollback()


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient]:
    async def override_get_db() -> AsyncGenerator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()
