"""Implémentation PostgreSQL du repository.

Sert les dossiers ingérés depuis l'open data. Implémente le même protocole que
la version in-memory : l'API ne voit pas la différence (choix via la config).
"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from datetime import date, timedelta

from app.db.models import DeputeRow, DossierRow, GroupeRow, ScrutinRow, VoteDeputeRow
from app.domain.division import division
from app.domain.enums import Chambre, ObjetVote, PositionVote
from app.domain.recherche import ChampsRecherche, score, termes
from app.ingestion.normalize import nature_texte, type_objet_vote
from app.repositories.base import (
    MAX_DISPUTES_PAR_DOSSIER,
    DossierRepository,
    construire_portrait,
    limiter_par_dossier,
    ordonner_sections,
)
from app.schemas import (
    Accueil,
    DeputeDetail,
    DeputeListItem,
    Dossier,
    DossierListItem,
    GroupeListItem,
    MiseAJourDossier,
    PortraitVote,
    RecapMensuel,
    Scrutin,
    ScrutinResume,
    SectionTheme,
    ThemeListItem,
    VoteDepute,
    VoteDisputeItem,
)
from app.utils.text import fold

# Fenêtre des statistiques de la fiche député (§5.2) : les 12 derniers mois.
FENETRE_PORTRAIT_JOURS = 365

# Fenêtre de la rangée « Les votes les plus disputés », comptée depuis le dernier
# scrutin en base (et non depuis aujourd'hui : en intersession, une fenêtre
# calendaire viderait la rangée alors que les votes existent). 90 jours couvrent
# une session de travail parlementaire complète tout en laissant la rangée
# évoluer à chaque ingestion — un classement « de tous les temps » serait figé.
FENETRE_DISPUTES_JOURS = 90

# Nombre de votes de la rangée. Au-delà, c'est une liste, plus une sélection.
_MAX_DISPUTES = 10

# Candidats ramenés avant classement. Le préfiltre `LIKE` a déjà réduit
# l'ensemble ; ce plafond borne le coût du tri en Python même sur un terme très
# fréquent, sans jamais tronquer une recherche réaliste.
_MAX_CANDIDATS = 200


def _champs(row: DossierRow) -> ChampsRecherche:
    """Les champs de pertinence, tous en colonnes : marquer un résultat ne
    demande jamais d'ouvrir le payload."""
    return ChampsRecherche(
        titre_clair=row.titre_clair,
        titre_officiel=row.titre_officiel,
        accroche=row.accroche or None,
        theme=row.theme,
        index=row.search_index,
    )

# Positions effectivement exprimées (le non-votant ne compte ni dans les votes
# ni dans la cohésion).
_EXPRIMEES = (
    PositionVote.pour.value,
    PositionVote.contre.value,
    PositionVote.abstention.value,
)


def _to_depute_item(row: DeputeRow) -> DeputeListItem:
    return DeputeListItem(
        id=row.id,
        nom=row.nom,
        chambre=row.chambre,  # type: ignore[arg-type]  (str -> enum coercé)
        groupe_nom=row.groupe_nom,
        groupe_couleur=row.groupe_couleur,
        circonscription=row.circonscription,
        portrait_url=row.portrait_url,
    )


def _to_list_item(row: DossierRow) -> DossierListItem:
    # Le payload (déjà chargé avec la ligne) porte les scrutins : on en tire le
    # résultat du dernier vote nominatif pour la barre de la carte (§5.2, §2.5).
    scrutins = [
        ScrutinResume.model_validate(s) for s in row.payload.get("scrutins", [])
    ]
    return DossierListItem(
        id=row.id,
        date=row.date,
        titre_clair=row.titre_clair,
        # Colonne NOT NULL : la chaîne vide signifie « pas d'accroche » (§2.5).
        accroche=row.accroche or None,
        nature_texte=nature_texte(row.titre_officiel),
        statut=row.statut,  # type: ignore[arg-type]  (str -> enum coercé)
        theme=row.theme,
        temps_lecture_sec=row.temps_lecture_sec,
        nombre_scrutins=row.nombre_scrutins,
        mise_a_jour=(
            MiseAJourDossier.model_validate(row.mise_a_jour)
            if row.mise_a_jour
            else None
        ),
        chambres=DossierListItem._chambres(scrutins),
        resultat_dernier_scrutin=DossierListItem._resultat_dernier(scrutins),
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

    async def search(
        self, query: str, limit: int = 20, theme: str | None = None
    ) -> list[DossierListItem]:
        """Recherche multi-termes classée par pertinence (§3.3).

        Le `LIKE` par terme sert de **préfiltre** (l'index B-tree de
        `search_index` reste exploité) ; le classement, lui, se fait avec la
        fonction pure `score`, la même que le backend `memory` — c'est ce qui
        rend les tests représentatifs.
        """
        mots = termes(query)
        stmt = select(DossierRow).order_by(
            DossierRow.date.desc(), DossierRow.id.desc()
        )
        if theme:
            stmt = stmt.where(DossierRow.theme == theme)
        for mot in mots:
            stmt = stmt.where(DossierRow.search_index.like(f"%{mot}%"))
        if not mots:
            # Requête vide : le fil récent, éventuellement borné au thème.
            stmt = stmt.limit(limit)
            async with self._sf() as session:
                rows = (await session.execute(stmt)).scalars().all()
            return [_to_list_item(r) for r in rows]

        stmt = stmt.limit(_MAX_CANDIDATS)
        async with self._sf() as session:
            rows = (await session.execute(stmt)).scalars().all()
        # Les lignes arrivent déjà triées par date : un tri stable par score
        # décroissant conserve donc la date comme départage (§3.3).
        classes = sorted(
            rows, key=lambda r: score(_champs(r), mots, query), reverse=True
        )
        return [_to_list_item(r) for r in classes[:limit]]

    async def list_themes(self) -> list[ThemeListItem]:
        stmt = (
            select(DossierRow.theme, func.count())
            .group_by(DossierRow.theme)
            .order_by(DossierRow.theme)
        )
        async with self._sf() as session:
            rows = (await session.execute(stmt)).all()
        return [ThemeListItem(nom=nom, nombre=nombre) for nom, nombre in rows]

    async def accueil(self, par_section: int = 10) -> Accueil:
        jour_expr = func.substr(DossierRow.date, 1, 10)
        recents = (
            select(DossierRow)
            .order_by(DossierRow.date.desc(), DossierRow.id.desc())
        )
        aujourdhui_str = date.today().isoformat()
        hier_str = (date.today() - timedelta(days=1)).isoformat()

        async with self._sf() as session:
            a_la_une_row = (
                (await session.execute(recents.limit(1))).scalars().first()
            )
            a_la_une = _to_list_item(a_la_une_row) if a_la_une_row else None

            async def _du_jour(jour: str) -> list[DossierListItem]:
                rows = (
                    (await session.execute(recents.where(jour_expr == jour)))
                    .scalars()
                    .all()
                )
                # La une n'est pas répétée dans Aujourd'hui / Hier.
                return [
                    _to_list_item(r)
                    for r in rows
                    if a_la_une is None or r.id != a_la_une.id
                ]

            aujourdhui = await _du_jour(aujourdhui_str)
            hier = await _du_jour(hier_str)
            votes_disputes = await self._votes_disputes(session)

            # Une requête ciblée par thème (jamais tous les payloads d'un coup).
            themes = (
                (await session.execute(select(DossierRow.theme).distinct()))
                .scalars()
                .all()
            )
            sections: list[SectionTheme] = []
            for theme in themes:
                rows = (
                    (
                        await session.execute(
                            recents.where(DossierRow.theme == theme).limit(
                                par_section
                            )
                        )
                    )
                    .scalars()
                    .all()
                )
                sections.append(
                    SectionTheme(
                        theme=theme, dossiers=[_to_list_item(r) for r in rows]
                    )
                )

        return Accueil(
            a_la_une=a_la_une,
            aujourdhui=aujourdhui,
            hier=hier,
            votes_disputes=votes_disputes,
            sections=ordonner_sections(sections),
        )

    async def _votes_disputes(self, session) -> list[VoteDisputeItem]:
        """Les votes récents les plus disputés, du plus divisé au moins divisé.

        « Disputé » = arithmétique du scrutin (`app/domain/division.py`), jamais
        un jugement sur la mesure (§4.3). La fenêtre est comptée depuis le
        dernier scrutin en base pour que la rangée survive à l'intersession.
        """
        dernier = (
            await session.execute(
                select(func.max(ScrutinRow.date)).where(
                    ScrutinRow.indice_division.is_not(None)
                )
            )
        ).scalar()
        if not dernier:
            return []
        try:
            depuis = (
                date.fromisoformat(dernier[:10])
                - timedelta(days=FENETRE_DISPUTES_JOURS)
            ).isoformat()
        except ValueError:
            return []

        lignes = (
            await session.execute(
                select(ScrutinRow, DossierRow.titre_clair)
                .join(DossierRow, DossierRow.id == ScrutinRow.dossier_id)
                .where(
                    ScrutinRow.indice_division.is_not(None),
                    ScrutinRow.date >= depuis,
                )
                .order_by(ScrutinRow.indice_division.desc(), ScrutinRow.id.desc())
                # Large : le plafond par dossier écarte ensuite les doublons de
                # texte, il faut donc de quoi remplir la rangée après coupe.
                .limit(_MAX_DISPUTES * 5)
            )
        ).all()

        items: list[VoteDisputeItem] = []
        for row, titre_dossier in lignes:
            scrutin = Scrutin.model_validate(row.payload)
            # Recalculé plutôt que stocké : la colonne ne porte que l'indice de
            # tri, les chiffres affichés viennent toujours du scrutin lui-même.
            mesure = division(
                scrutin.resultat,
                scrutin.positions_groupes,
                scrutin.chambre,
                objet=scrutin.objet,
                scrutin_public=scrutin.scrutin_public,
            )
            if mesure is None:
                continue
            items.append(
                VoteDisputeItem(
                    scrutin_id=scrutin.id,
                    dossier_id=scrutin.dossier_id,
                    dossier_titre=titre_dossier,
                    objet=scrutin.objet,
                    date=scrutin.date,
                    chambre=scrutin.chambre,
                    statut=scrutin.statut,
                    resultat=scrutin.resultat,
                    ecart=mesure.ecart,
                    camps=mesure.camps,
                    groupes_disperses=mesure.groupes_disperses,
                )
            )
        return limiter_par_dossier(items, MAX_DISPUTES_PAR_DOSSIER)[:_MAX_DISPUTES]

    async def recap_mensuel(self) -> RecapMensuel | None:
        # Clé « AAAA-MM » sur la date ISO du scrutin ; comptes SQL (exacts,
        # indépendants de la pagination du fil).
        mois_expr = func.substr(ScrutinRow.date, 1, 7)
        statut = ScrutinRow.payload["statut"].astext
        async with self._sf() as session:
            mois_max = (
                await session.execute(
                    select(func.max(mois_expr)).where(ScrutinRow.date != "")
                )
            ).scalar()
            if not mois_max:
                return None
            votes, adoptes, rejetes, textes = (
                await session.execute(
                    select(
                        func.count(),
                        func.count().filter(statut == "adopte"),
                        func.count().filter(statut == "rejete"),
                        func.count(func.distinct(ScrutinRow.dossier_id)),
                    ).where(mois_expr == mois_max)
                )
            ).one()
        return RecapMensuel(
            annee=int(mois_max[:4]),
            mois=int(mois_max[5:7]),
            votes=votes,
            adoptes=adoptes,
            rejetes=rejetes,
            textes=textes,
        )

    # --- Parlementaires (§5.2) --------------------------------------------

    async def list_deputes(
        self,
        q: str = "",
        groupe_id: str | None = None,
        limit: int = 600,
        chambre: str | None = None,
    ) -> list[DeputeListItem]:
        stmt = select(DeputeRow).order_by(DeputeRow.nom, DeputeRow.id)
        folded = fold(q.strip())
        if folded:
            stmt = stmt.where(DeputeRow.search_index.like(f"%{folded}%"))
        if groupe_id:
            stmt = stmt.where(DeputeRow.groupe_id == groupe_id)
        if chambre:
            stmt = stmt.where(DeputeRow.chambre == chambre)
        stmt = stmt.limit(limit)
        async with self._sf() as session:
            rows = (await session.execute(stmt)).scalars().all()
        return [_to_depute_item(r) for r in rows]

    async def get_depute(
        self, depute_id: str, limit: int = 30, offset: int = 0
    ) -> DeputeDetail | None:
        async with self._sf() as session:
            row = await session.get(DeputeRow, depute_id)
            if row is None:
                return None
            portrait = await self._portrait(session, depute_id)
            historique = await self._votes(session, depute_id, limit, offset)
        return DeputeDetail(
            id=row.id,
            nom=row.nom,
            chambre=row.chambre,  # type: ignore[arg-type]  (str -> enum coercé)
            groupe_id=row.groupe_id,
            groupe_nom=row.groupe_nom,
            groupe_couleur=row.groupe_couleur,
            circonscription=row.circonscription,
            depuis=row.depuis,
            portrait_url=row.portrait_url,
            commission=row.commission,
            portrait=portrait,
            historique=historique,
        )

    async def votes_depute(
        self, depute_id: str, limit: int = 30, offset: int = 0
    ) -> list[VoteDepute]:
        async with self._sf() as session:
            return await self._votes(session, depute_id, limit, offset)

    async def list_groupes(self, chambre: str | None = None) -> list[GroupeListItem]:
        stmt = select(GroupeRow).order_by(GroupeRow.chambre, GroupeRow.nom)
        if chambre:
            stmt = stmt.where(GroupeRow.chambre == chambre)
        async with self._sf() as session:
            rows = (await session.execute(stmt)).scalars().all()
        return [
            GroupeListItem(
                id=r.id,
                nom=r.nom,
                abrev=r.abrev,
                couleur=r.couleur,
                chambre=r.chambre,  # type: ignore[arg-type]  (str -> enum coercé)
            )
            for r in rows
        ]

    async def _votes(
        self, session: AsyncSession, depute_id: str, limit: int, offset: int
    ) -> list[VoteDepute]:
        """Historique paginé — jointures faites en SQL (jamais un parcours de
        toute la table de votes côté Python)."""
        stmt = (
            select(
                VoteDeputeRow.scrutin_id,
                VoteDeputeRow.date,
                VoteDeputeRow.position,
                VoteDeputeRow.contre_son_groupe,
                ScrutinRow.dossier_id,
                ScrutinRow.payload["objet"].astext,
                DossierRow.titre_clair,
            )
            .join(ScrutinRow, ScrutinRow.id == VoteDeputeRow.scrutin_id)
            .outerjoin(DossierRow, DossierRow.id == ScrutinRow.dossier_id)
            .where(VoteDeputeRow.acteur_ref == depute_id)
            .order_by(VoteDeputeRow.date.desc(), VoteDeputeRow.scrutin_id.desc())
            .limit(limit)
            .offset(offset)
        )
        lignes = (await session.execute(stmt)).all()
        votes: list[VoteDepute] = []
        for scrutin_id, date_vote, position, contre, dossier_id, objet, titre in lignes:
            objet = objet or ""
            objet_type = type_objet_vote(objet)
            # Vote sur le texte → titre clair du dossier ; vote d'amendement →
            # son objet officiel, tel quel (§2.5 : rien n'est reformulé).
            libelle = objet
            if objet_type is ObjetVote.dossier and titre:
                libelle = titre
            votes.append(
                VoteDepute(
                    scrutin_id=scrutin_id,
                    date=date_vote,
                    objet_type=objet_type,
                    titre=libelle,
                    # Pas de dossier en base → pas de lien proposé (§2.5).
                    dossier_id=dossier_id if titre is not None else None,
                    position=position,  # type: ignore[arg-type]  (str -> enum coercé)
                    contre_son_groupe=contre,
                )
            )
        return votes

    async def _portrait(
        self, session: AsyncSession, depute_id: str
    ) -> PortraitVote:
        """Statistiques des 12 derniers mois, agrégées en SQL."""
        depuis = (
            date.today() - timedelta(days=FENETRE_PORTRAIT_JOURS)
        ).isoformat()
        periode = (
            VoteDeputeRow.acteur_ref == depute_id,
            VoteDeputeRow.date >= depuis,
        )
        comptes = dict(
            (
                await session.execute(
                    select(VoteDeputeRow.position, func.count())
                    .where(*periode)
                    .group_by(VoteDeputeRow.position)
                )
            ).all()
        )
        # Cohésion : parmi les votes exprimés dont le groupe avait une position
        # majoritaire documentée (`contre_son_groupe` non NULL), ceux qui la
        # suivaient. Dénominateur nul → ratio absent (§2.5).
        alignes, avec_majorite = (
            await session.execute(
                select(
                    func.count().filter(VoteDeputeRow.contre_son_groupe.is_(False)),
                    func.count(VoteDeputeRow.contre_son_groupe),
                ).where(*periode, VoteDeputeRow.position.in_(_EXPRIMEES))
            )
        ).one()
        return construire_portrait(
            pour=comptes.get(PositionVote.pour.value, 0),
            contre=comptes.get(PositionVote.contre.value, 0),
            abstention=comptes.get(PositionVote.abstention.value, 0),
            alignes=alignes or 0,
            avec_majorite=avec_majorite or 0,
        )
