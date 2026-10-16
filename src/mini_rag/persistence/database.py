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
