"""Implémentation in-memory du repository.

Alimentée par les données seed (`app.data.seed`). Sert de backend par défaut
(données de démonstration) ; l'API n'en voit rien (elle dépend du protocole
`DossierRepository`).
"""
from __future__ import annotations

from datetime import date, timedelta

from app.repositories.base import DossierRepository, ordonner_sections
from app.schemas import (
    Accueil,
    Dossier,
    DossierListItem,
    RecapMensuel,
    Scrutin,
    SectionTheme,
)
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

    async def accueil(self, par_section: int = 10) -> Accueil:
        items = [DossierListItem.from_dossier(d) for d in self._ordered]
        a_la_une = items[0] if items else None
        reste = items[1:]  # la une n'est pas répétée dans Aujourd'hui / Hier

        aujourdhui_str = date.today().isoformat()
        hier_str = (date.today() - timedelta(days=1)).isoformat()

        par_theme: dict[str, list[DossierListItem]] = {}
        for it in items:
            par_theme.setdefault(it.theme, []).append(it)

        return Accueil(
            a_la_une=a_la_une,
            aujourdhui=[d for d in reste if d.date[:10] == aujourdhui_str],
            hier=[d for d in reste if d.date[:10] == hier_str],
            sections=ordonner_sections(
                [
                    SectionTheme(theme=t, dossiers=liste[:par_section])
                    for t, liste in par_theme.items()
                ]
            ),
        )

    async def recap_mensuel(self) -> RecapMensuel | None:
        dates = [s for s in self._scrutins.values() if s.date]
        if not dates:
            return None
        # Dernier mois calendaire ayant connu au moins un vote (clé « AAAA-MM »).
        mois_max = max(s.date[:7] for s in dates)
        du_mois = [s for s in dates if s.date[:7] == mois_max]
        return RecapMensuel(
            annee=int(mois_max[:4]),
            mois=int(mois_max[5:7]),
            votes=len(du_mois),
            adoptes=sum(1 for s in du_mois if s.statut.value == "adopte"),
            rejetes=sum(1 for s in du_mois if s.statut.value == "rejete"),
            textes=len({s.dossier_id for s in du_mois}),
        )
