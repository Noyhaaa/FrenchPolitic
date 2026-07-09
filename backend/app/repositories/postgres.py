"""Implémentation PostgreSQL du repository (Phase 1).

Sert les scrutins ingérés depuis l'open data. Implémente le même protocole que
la version in-memory : l'API ne voit pas la différence (choix via la config).
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import ScrutinRow
from app.repositories.base import ScrutinRepository
from app.schemas import ResultatGlobal, Scrutin, ScrutinListItem
from app.utils.text import fold


def _to_list_item(row: ScrutinRow) -> ScrutinListItem:
    return ScrutinListItem(
        id=row.id,
        date=row.date,
        titre_clair=row.titre_clair,
        accroche=row.accroche,
        statut=row.statut,  # type: ignore[arg-type]  (str -> enum coercé)
        theme=row.theme,
        temps_lecture_sec=row.temps_lecture_sec,
        resultat=ResultatGlobal.model_validate(row.resultat),
    )


class PostgresScrutinRepository(ScrutinRepository):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sf = session_factory

    async def list(self, limit: int = 20, offset: int = 0) -> list[ScrutinListItem]:
        stmt = (
            select(ScrutinRow)
            .order_by(ScrutinRow.date.desc(), ScrutinRow.id.desc())
            .limit(limit)
            .offset(offset)
        )
        async with self._sf() as session:
            rows = (await session.execute(stmt)).scalars().all()
        return [_to_list_item(r) for r in rows]

    async def get(self, scrutin_id: str) -> Scrutin | None:
        async with self._sf() as session:
            row = await session.get(ScrutinRow, scrutin_id)
        return Scrutin.model_validate(row.payload) if row else None

    async def search(self, query: str, limit: int = 20) -> list[ScrutinListItem]:
        folded = fold(query.strip())
        stmt = select(ScrutinRow).order_by(
            ScrutinRow.date.desc(), ScrutinRow.id.desc()
        )
        if folded:
            like = f"%{folded}%"
            stmt = stmt.where(ScrutinRow.search_index.like(like))
        stmt = stmt.limit(limit)
        async with self._sf() as session:
            rows = (await session.execute(stmt)).scalars().all()
        return [_to_list_item(r) for r in rows]
