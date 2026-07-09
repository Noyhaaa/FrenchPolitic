"""Moteur et sessions SQLAlchemy async."""
from __future__ import annotations

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import settings


def make_engine(database_url: str | None = None) -> AsyncEngine:
    url = database_url or settings.database_url
    if not url:
        raise RuntimeError(
            "DATABASE_URL non configurée : impossible de créer le moteur Postgres."
        )
    return create_async_engine(url, pool_pre_ping=True)


def make_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


async def init_models(engine: AsyncEngine) -> None:
    """Crée les tables si absentes (dev). En prod, préférer des migrations."""
    from app.db.base import Base
    import app.db.models  # noqa: F401  (enregistre les tables)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
