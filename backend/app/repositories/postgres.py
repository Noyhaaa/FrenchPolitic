"""Implémentation PostgreSQL du repository.

Sert les dossiers ingérés depuis l'open data. Implémente le même protocole que
la version in-memory : l'API ne voit pas la différence (choix via la config).
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import DossierRow, ScrutinRow
from app.repositories.base import DossierRepository
from app.schemas import Dossier, DossierListItem, MiseAJourDossier, Scrutin
from app.utils.text import fold


def _to_list_item(row: DossierRow) -> DossierListItem:
    return DossierListItem(
        id=row.id,
        date=row.date,
        titre_clair=row.titre_clair,
        accroche=row.accroche,
        statut=row.statut,  # type: ignore[arg-type]  (str -> enum coercé)
        theme=row.theme,
        temps_lecture_sec=row.temps_lecture_sec,
        nombre_scrutins=row.nombre_scrutins,
        mise_a_jour=(
            MiseAJourDossier.model_validate(row.mise_a_jour)
            if row.mise_a_jour
            else None
        ),
    )


class PostgresDossierRepository(DossierRepository):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sf = session_factory

    async def list(self, limit: int = 20, offset: int = 0) -> list[DossierListItem]:
        stmt = (
            select(DossierRow)
            .order_by(DossierRow.date.desc(), DossierRow.id.desc())
            .limit(limit)
            .offset(offset)
        )
        async with self._sf() as session:
            rows = (await session.execute(stmt)).scalars().all()
        return [_to_list_item(r) for r in rows]

    async def get(self, dossier_id: str) -> Dossier | None:
        async with self._sf() as session:
            row = await session.get(DossierRow, dossier_id)
        return Dossier.model_validate(row.payload) if row else None

    async def get_scrutin(self, scrutin_id: str) -> Scrutin | None:
        async with self._sf() as session:
            row = await session.get(ScrutinRow, scrutin_id)
        return Scrutin.model_validate(row.payload) if row else None

    async def search(self, query: str, limit: int = 20) -> list[DossierListItem]:
        folded = fold(query.strip())
        stmt = select(DossierRow).order_by(
            DossierRow.date.desc(), DossierRow.id.desc()
        )
        if folded:
            like = f"%{folded}%"
            stmt = stmt.where(DossierRow.search_index.like(like))
        stmt = stmt.limit(limit)
        async with self._sf() as session:
            rows = (await session.execute(stmt)).scalars().all()
        return [_to_list_item(r) for r in rows]
