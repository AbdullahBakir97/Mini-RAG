import anyio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def create_engine(url: str) -> AsyncEngine:
    # pool_pre_ping replaces connections the database has closed (e.g. after
    # a restart) instead of failing the next request.
    return create_async_engine(url, pool_pre_ping=True)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    # expire_on_commit=False keeps loaded objects usable after commit, which
    # async code needs because it cannot lazily reload attributes.
    return async_sessionmaker(engine, expire_on_commit=False)


async def is_database_available(engine: AsyncEngine, timeout_seconds: float = 3.0) -> bool:
    """Whether the database answers a trivial query within the timeout."""
    try:
        with anyio.fail_after(timeout_seconds):
            async with engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
    except Exception:
        return False
    return True
