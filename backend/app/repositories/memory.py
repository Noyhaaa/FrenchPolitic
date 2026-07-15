"""Implémentation in-memory du repository.

Alimentée par les données seed (`app.data.seed`). Sert de backend par défaut
(données de démonstration) ; l'API n'en voit rien (elle dépend du protocole
`DossierRepository`).
"""
from __future__ import annotations

from app.repositories.base import DossierRepository
from app.schemas import Dossier, DossierListItem, Scrutin
from app.utils.text import fold as _fold


def _sort_key(d: Dossier) -> str:
    return d.date_dernier_scrutin


class InMemoryDossierRepository(DossierRepository):
    def __init__(self, dossiers: list[Dossier], scrutins: list[Scrutin]) -> None:
        # Index par id + liste triée du plus récent au plus ancien.
        ordered = sorted(dossiers, key=_sort_key, reverse=True)
        self._ordered = ordered
        self._by_id = {d.id: d for d in ordered}
        self._scrutins = {s.id: s for s in scrutins}

    async def list(self, limit: int = 20, offset: int = 0) -> list[DossierListItem]:
        window = self._ordered[offset : offset + limit]
        return [DossierListItem.from_dossier(d) for d in window]

    async def get(self, dossier_id: str) -> Dossier | None:
        return self._by_id.get(dossier_id)

    async def get_scrutin(self, scrutin_id: str) -> Scrutin | None:
        return self._scrutins.get(scrutin_id)

    async def search(self, query: str, limit: int = 20) -> list[DossierListItem]:
        q = _fold(query.strip())
        if not q:
            return await self.list(limit=limit)
        results = [
            d
            for d in self._ordered
            if q in _fold(f"{d.titre_clair} {d.titre_officiel} {d.accroche} {d.theme}")
        ]
        return [DossierListItem.from_dossier(d) for d in results[:limit]]
