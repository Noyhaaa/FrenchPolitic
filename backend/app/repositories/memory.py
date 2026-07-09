"""Implémentation in-memory du repository (V0).

Alimentée par les données seed (`app.data.seed`), qui reprennent les mocks du
frontend. Sera remplacée par une implémentation PostgreSQL en Phase 1 —
l'API n'en verra rien (elle dépend du protocole `ScrutinRepository`).
"""
from __future__ import annotations

from app.repositories.base import ScrutinRepository
from app.schemas import Scrutin, ScrutinListItem
from app.utils.text import fold as _fold


def _sort_key(s: Scrutin) -> str:
    return s.date


class InMemoryScrutinRepository(ScrutinRepository):
    def __init__(self, scrutins: list[Scrutin]) -> None:
        # Index par id + liste triée du plus récent au plus ancien.
        ordered = sorted(scrutins, key=_sort_key, reverse=True)
        self._ordered = ordered
        self._by_id = {s.id: s for s in ordered}

    async def list(self, limit: int = 20, offset: int = 0) -> list[ScrutinListItem]:
        window = self._ordered[offset : offset + limit]
        return [ScrutinListItem.from_scrutin(s) for s in window]

    async def get(self, scrutin_id: str) -> Scrutin | None:
        return self._by_id.get(scrutin_id)

    async def search(self, query: str, limit: int = 20) -> list[ScrutinListItem]:
        q = _fold(query.strip())
        if not q:
            return await self.list(limit=limit)
        results = [
            s
            for s in self._ordered
            if q in _fold(f"{s.titre_clair} {s.titre_officiel} {s.theme}")
        ]
        return [ScrutinListItem.from_scrutin(s) for s in results[:limit]]
