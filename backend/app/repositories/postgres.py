"""Implémentation PostgreSQL du repository.

Sert les dossiers ingérés depuis l'open data. Implémente le même protocole que
la version in-memory : l'API ne voit pas la différence (choix via la config).
"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from datetime import date, timedelta

from app.db.models import DossierRow, ScrutinRow
from app.repositories.base import DossierRepository, ordonner_sections
from app.schemas import (
    Accueil,
    Dossier,
    DossierListItem,
    MiseAJourDossier,
    RecapMensuel,
    Scrutin,
    ScrutinResume,
    SectionTheme,
)
from app.utils.text import fold


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
            sections=ordonner_sections(sections),
        )

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
