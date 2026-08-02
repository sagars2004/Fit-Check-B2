from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from fastapi import Request
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import Settings, StorageMode, get_settings
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

    async def pull_backup(self, storage: Any) -> None:
        """Sync SQLite state from storage when running in stateless serverless environments."""
        if self.settings.storage_mode is not StorageMode.B2:
            return
        try:
            from app.services.storage import sha256_bytes

            url = make_url(self.settings.database_url)
            if (
                not url.drivername.startswith("sqlite")
                or not url.database
                or url.database == ":memory:"
            ):
                return
            db_path = Path(url.database).expanduser()
            key = f"{self.settings.b2_prefix}/db/fit_check.db"
            head = await storage.head(key)
            remote_sha = getattr(head, "sha256", None) or (
                head.metadata.get("sha256") if hasattr(head, "metadata") else None
            )
            local_sha = sha256_bytes(db_path.read_bytes()) if db_path.exists() else ""
            if (
                not db_path.exists()
                or (remote_sha and local_sha != remote_sha)
                or db_path.stat().st_size != head.size
            ):
                content = await storage.get_bytes(key)
                db_path.parent.mkdir(parents=True, exist_ok=True)
                db_path.write_bytes(content)
                await self.engine.dispose()
        except Exception:
            pass

    async def push_backup(self, storage: Any) -> None:
        """Persist SQLite state to storage when running in stateless serverless environments."""
        if self.settings.storage_mode is not StorageMode.B2:
            return
        try:
            url = make_url(self.settings.database_url)
            if (
                not url.drivername.startswith("sqlite")
                or not url.database
                or url.database == ":memory:"
            ):
                return
            db_path = Path(url.database).expanduser()
            if db_path.exists() and db_path.stat().st_size > 0:
                key = f"{self.settings.b2_prefix}/db/fit_check.db"
                content = db_path.read_bytes()
                await storage.put_bytes(key, content, content_type="application/x-sqlite3")
        except Exception:
            pass


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    database: Database | None = getattr(request.app.state, "database", None)
    if database is None:
        settings = getattr(request.app.state, "settings", None) or get_settings()
        database = Database(settings)
        request.app.state.database = database

    storage = getattr(request.app.state, "storage", None)
    if storage is not None:
        await database.pull_backup(storage)

    if not database._initialized and database.settings.auto_create_schema:
        await database.initialize()

    async with database.session() as session:
        yield session

    if storage is not None and request.method in ("POST", "PUT", "PATCH", "DELETE"):
        await database.push_backup(storage)


def _ensure_sqlite_parent_directory(database_url: str) -> None:
    """Make the default local SQLite URL work from any API working directory."""
    try:
        url = make_url(database_url)
        if (
            not url.drivername.startswith("sqlite")
            or not url.database
            or url.database == ":memory:"
        ):
            return
        Path(url.database).expanduser().parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
