import pytest
from sqlalchemy import text

from mini_rag.persistence.database import create_engine, create_session_factory

pytestmark = pytest.mark.anyio


async def test_session_factory_connects_to_postgres(database_url):
    engine = create_engine(database_url)
    try:
        async with create_session_factory(engine)() as session:
            version = await session.scalar(text("SHOW server_version"))
    finally:
        await engine.dispose()

    assert int(version.split(".")[0]) >= 16


def test_app_lifespan_opens_and_closes_the_pool(client):
    engine = client.app.state.engine

    assert engine.url.render_as_string(hide_password=True).startswith("postgresql+asyncpg://")


def test_database_url_must_be_async_postgres(monkeypatch):
    from pydantic import ValidationError

    from mini_rag.core.config import Settings

    monkeypatch.setenv("DATABASE_URL", "sqlite:///db.sqlite")

    with pytest.raises(ValidationError):
        Settings()
