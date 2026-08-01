from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

from fastapi import Request
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import Settings, get_settings
from app.db.models import Base


class Database:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        _ensure_sqlite_parent_directory(settings.database_url)
        self.engine: AsyncEngine = create_async_engine(settings.database_url, pool_pre_ping=True)
        self.session_factory = async_sessionmaker(self.engine, expire_on_commit=False)
        self._initialized = False

    async def initialize(self) -> None:
        if not self._initialized:
            _ensure_sqlite_parent_directory(self.settings.database_url)
            async with self.engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            self._initialized = True

    async def dispose(self) -> None:
        await self.engine.dispose()

    def session(self) -> AsyncSession:
        return self.session_factory()


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    database: Database | None = getattr(request.app.state, "database", None)
    if database is None:
        settings = getattr(request.app.state, "settings", None) or get_settings()
        database = Database(settings)
        request.app.state.database = database

    if not database._initialized and database.settings.auto_create_schema:
        await database.initialize()

    async with database.session() as session:
        yield session


def _ensure_sqlite_parent_directory(database_url: str) -> None:
    """Make the default local SQLite URL work from any API working directory."""
    try:
        url = make_url(database_url)
        if not url.drivername.startswith("sqlite") or not url.database or url.database == ":memory:":
            return
        Path(url.database).expanduser().parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
