"""Implémentation in-memory du repository.

Alimentée par les données seed (`app.data.seed`). Sert de backend par défaut
(données de démonstration) ; l'API n'en voit rien (elle dépend du protocole
`DossierRepository`).
"""
from __future__ import annotations

from collections import Counter
from datetime import date, timedelta

from app.domain.division import division
from app.domain.enums import PositionVote
from app.domain.recherche import ChampsRecherche, index_recherche, score, termes
from app.repositories.base import (
    FENETRE_DISPUTES_JOURS,
    FENETRE_PORTRAIT_JOURS,
    MAX_DISPUTES,
    MAX_DISPUTES_PAR_DOSSIER,
    DossierRepository,
    construire_portrait,
    limiter_par_dossier,
    ordonner_sections,
)
from app.schemas import (
    Accueil,
    Depute,
    DeputeDetail,
    DeputeListItem,
    Dossier,
    DossierListItem,
    GroupeListItem,
    PortraitVote,
    RecapMensuel,
    Scrutin,
    SectionTheme,
    ThemeListItem,
    VoteDepute,
    VoteDisputeItem,
)
from app.utils.text import fold as _fold


def _champs(d: Dossier) -> ChampsRecherche:
    """Mêmes champs de pertinence qu'en Postgres, l'index recalculé à la
    volée (le seed n'a pas de colonne `search_index`)."""
    return ChampsRecherche(
        titre_clair=d.titre_clair,
        titre_officiel=d.titre_officiel,
        accroche=d.accroche,
        theme=d.theme,
        index=index_recherche(d),
    )


def _sort_key(d: Dossier) -> str:
    return d.date_dernier_scrutin


class InMemoryDossierRepository(DossierRepository):
    def __init__(
        self,
        dossiers: list[Dossier],
        scrutins: list[Scrutin],
        deputes: list[Depute] | None = None,
        votes_deputes: dict[str, list[VoteDepute]] | None = None,
        groupes: list[GroupeListItem] | None = None,
    ) -> None:
        # Index par id + liste triée du plus récent au plus ancien.
        ordered = sorted(dossiers, key=_sort_key, reverse=True)
        self._ordered = ordered
        self._by_id = {d.id: d for d in ordered}
        self._scrutins = {s.id: s for s in scrutins}
        # Députés : annuaire trié alphabétiquement + historique par député
        # (déjà du plus récent au plus ancien dans le seed).
        self._deputes = sorted(deputes or [], key=lambda d: d.nom)
        self._deputes_by_id = {d.id: d for d in self._deputes}
        self._votes_deputes = votes_deputes or {}
        self._groupes = list(groupes or [])

    async def list(self, limit: int = 20, offset: int = 0) -> list[DossierListItem]:
        window = self._ordered[offset : offset + limit]
        return [DossierListItem.from_dossier(d) for d in window]

    async def get(self, dossier_id: str) -> Dossier | None:
        return self._by_id.get(dossier_id)

    async def get_scrutin(self, scrutin_id: str) -> Scrutin | None:
        return self._scrutins.get(scrutin_id)

    async def search(
        self, query: str, limit: int = 20, theme: str | None = None
    ) -> list[DossierListItem]:
        """Même contrat, mêmes fonctions pures et donc même classement que le
        backend Postgres (§3.3) : les tests tournent ici, ils doivent prouver le
        comportement servi en production."""
        candidats = [d for d in self._ordered if not theme or d.theme == theme]
        mots = termes(query)
        if not mots:
            return [DossierListItem.from_dossier(d) for d in candidats[:limit]]
        pertinents = [
            (score(_champs(d), mots, query), d) for d in candidats
        ]
        # `_ordered` est déjà trié par date : le tri stable par score conserve
        # la date comme départage.
        classes = sorted(
            (p for p in pertinents if p[0] > 0), key=lambda p: p[0], reverse=True
        )
        return [DossierListItem.from_dossier(d) for _, d in classes[:limit]]

    async def list_themes(self) -> list[ThemeListItem]:
        comptes = Counter(d.theme for d in self._ordered)
        return [
            ThemeListItem(nom=nom, nombre=comptes[nom]) for nom in sorted(comptes)
        ]

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
            votes_disputes=self._votes_disputes(),
            sections=ordonner_sections(
                [
                    SectionTheme(theme=t, dossiers=liste[:par_section])
                    for t, liste in par_theme.items()
                ]
            ),
        )

    def _votes_disputes(self) -> list[VoteDisputeItem]:
        """Mêmes règles qu'en Postgres, calculées à la volée sur le seed."""
        classes: list[tuple[float, VoteDisputeItem]] = []
        dates = [s.date for s in self._scrutins.values() if s.date]
        if not dates:
            return []
        try:
            depuis = (
                date.fromisoformat(max(dates)[:10])
                - timedelta(days=FENETRE_DISPUTES_JOURS)
            ).isoformat()
        except ValueError:
            return []

        for scrutin in self._scrutins.values():
            if not scrutin.date or scrutin.date < depuis:
                continue
            dossier = self._by_id.get(scrutin.dossier_id)
            if dossier is None:
                continue  # un vote sans son texte ne peut pas être situé (§2.5)
            mesure = division(
                scrutin.resultat,
                scrutin.positions_groupes,
                scrutin.chambre,
                objet=scrutin.objet,
                scrutin_public=scrutin.scrutin_public,
                type_vote=scrutin.type_vote,
            )
            if mesure is None:
                continue
            classes.append(
                (
                    mesure.indice,
                    VoteDisputeItem(
                        scrutin_id=scrutin.id,
                        dossier_id=scrutin.dossier_id,
                        dossier_titre=dossier.titre_clair,
                        objet=scrutin.objet,
                        date=scrutin.date,
                        chambre=scrutin.chambre,
                        statut=scrutin.statut,
                        type_motion=scrutin.type_motion,
                        resultat=scrutin.resultat,
                        ecart=mesure.ecart,
                        camps=mesure.camps,
                        groupes_disperses=mesure.groupes_disperses,
                    ),
                )
            )
        classes.sort(key=lambda c: (c[0], c[1].scrutin_id), reverse=True)
        retenus = limiter_par_dossier(
            [item for _, item in classes], MAX_DISPUTES_PAR_DOSSIER
        )
        return retenus[:MAX_DISPUTES]

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

    # --- Parlementaires (§5.2) --------------------------------------------

    async def list_deputes(
        self,
        q: str = "",
        groupe_id: str | None = None,
        limit: int = 600,
        chambre: str | None = None,
    ) -> list[DeputeListItem]:
        terme = _fold(q.strip())
        resultats = [
            d
            for d in self._deputes
            if (not groupe_id or d.groupe_id == groupe_id)
            and (not chambre or d.chambre.value == chambre)
            and (
                not terme
                or terme in _fold(f"{d.nom} {d.groupe_nom} {d.circonscription}")
            )
        ]
        return [DeputeListItem.from_depute(d) for d in resultats[:limit]]

    async def get_depute(
        self, depute_id: str, limit: int = 30, offset: int = 0
    ) -> DeputeDetail | None:
        depute = self._deputes_by_id.get(depute_id)
        if depute is None:
            return None
        return DeputeDetail(
            **depute.model_dump(),
            portrait=self._portrait(depute_id),
            historique=await self.votes_depute(depute_id, limit=limit, offset=offset),
        )

    async def votes_depute(
        self, depute_id: str, limit: int = 30, offset: int = 0
    ) -> list[VoteDepute]:
        votes = self._votes_deputes.get(depute_id, [])
        return votes[offset : offset + limit]

    async def list_groupes(self, chambre: str | None = None) -> list[GroupeListItem]:
        groupes = [
            g for g in self._groupes if not chambre or g.chambre.value == chambre
        ]
        return sorted(groupes, key=lambda g: (g.chambre.value, g.nom))

    def _portrait(self, depute_id: str) -> PortraitVote:
        """Mêmes règles que le repository Postgres : 12 mois glissants, ratios
        absents quand le dénominateur est nul (§2.5)."""
        depuis = (
            date.today() - timedelta(days=FENETRE_PORTRAIT_JOURS)
        ).isoformat()
        votes = [
            v for v in self._votes_deputes.get(depute_id, []) if v.date >= depuis
        ]
        comptes = {
            p: sum(1 for v in votes if v.position is p) for p in PositionVote
        }
        exprimes = [v for v in votes if v.position is not PositionVote.non_votant]
        avec_majorite = [v for v in exprimes if v.contre_son_groupe is not None]
        return construire_portrait(
            pour=comptes[PositionVote.pour],
            contre=comptes[PositionVote.contre],
            abstention=comptes[PositionVote.abstention],
            alignes=sum(1 for v in avec_majorite if not v.contre_son_groupe),
            avec_majorite=len(avec_majorite),
        )
