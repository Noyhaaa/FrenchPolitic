"""Job de synchronisation open data → PostgreSQL (§5.2, §6).

Enchaîne : organes (groupes) → scrutins publics → parsing → contrôles de
cohérence → upsert. Idempotent (upsert par id), relançable plusieurs fois par
jour. Journalise chaque exécution (table sync_run) pour l'observabilité (§8).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import GroupeRow, ScrutinRow, SyncRunRow
from app.ingestion.assemblee import AssembleeOpenDataClient, parse_scrutin
from app.ingestion.organes import GroupResolver, build_resolver_from_organes
from app.schemas import Scrutin
from app.utils.text import fold


@dataclass
class SyncReport:
    started_at: datetime
    scrutins_vus: int = 0
    scrutins_upserts: int = 0
    groupes: int = 0
    anomalies: list[str] = field(default_factory=list)
    finished_at: datetime | None = None


def controles_coherence(scrutin: Scrutin) -> list[str]:
    """Contrôles simples et non bloquants (fiabilité API non garantie, §5.2).

    Les décomptes par groupe devraient sommer au résultat global.
    """
    anomalies: list[str] = []
    groupes = scrutin.positions_groupes
    if not groupes:
        return anomalies
    for champ in ("pour", "contre", "abstention"):
        somme = sum(getattr(g, champ) for g in groupes)
        total = getattr(scrutin.resultat, champ)
        if somme != total:
            anomalies.append(
                f"{scrutin.id}: somme {champ} groupes={somme} ≠ global={total}"
            )
    return anomalies


def _scrutin_row_values(scrutin: Scrutin) -> dict:
    return {
        "id": scrutin.id,
        "date": scrutin.date,
        "statut": scrutin.statut.value,
        "theme": scrutin.theme,
        "titre_clair": scrutin.titre_clair,
        "titre_officiel": scrutin.titre_officiel,
        "accroche": scrutin.accroche,
        "scrutin_public": scrutin.scrutin_public,
        "temps_lecture_sec": scrutin.temps_lecture_sec,
        "resultat": scrutin.resultat.model_dump(mode="json"),
        "payload": scrutin.model_dump(mode="json", by_alias=True),
        "search_index": fold(
            f"{scrutin.titre_clair} {scrutin.titre_officiel} "
            f"{scrutin.accroche} {scrutin.theme}"
        ),
    }


async def _upsert_scrutin(session: AsyncSession, scrutin: Scrutin) -> None:
    values = _scrutin_row_values(scrutin)
    stmt = insert(ScrutinRow).values(**values)
    update = {k: v for k, v in values.items() if k != "id"}
    await session.execute(
        stmt.on_conflict_do_update(index_elements=["id"], set_=update)
    )


async def _upsert_groupes(session: AsyncSession, resolver: GroupResolver) -> int:
    count = 0
    for g in resolver.all():
        values = {"id": g.id, "nom": g.nom, "abrev": g.abrev, "couleur": g.couleur}
        stmt = insert(GroupeRow).values(**values)
        update = {k: v for k, v in values.items() if k != "id"}
        await session.execute(
            stmt.on_conflict_do_update(index_elements=["id"], set_=update)
        )
        count += 1
    return count


class SyncJob:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        client: AssembleeOpenDataClient | None = None,
    ) -> None:
        self._sf = session_factory
        self._client = client or AssembleeOpenDataClient()

    async def run(self, limit: int | None = None) -> SyncReport:
        report = SyncReport(started_at=datetime.now(timezone.utc))

        # 1) Référentiel des groupes.
        organes = await self._client.download_organes()
        resolver = build_resolver_from_organes(organes)
        async with self._sf() as session:
            report.groupes = await _upsert_groupes(session, resolver)
            await session.commit()

        # 2) Scrutins.
        bruts = await self._client.download_scrutins(limit=limit)
        report.scrutins_vus = len(bruts)
        async with self._sf() as session:
            for brut in bruts:
                try:
                    scrutin = parse_scrutin(brut, resolver)
                except (KeyError, TypeError) as exc:
                    report.anomalies.append(f"parsing échoué: {exc}")
                    continue
                report.anomalies.extend(controles_coherence(scrutin))
                await _upsert_scrutin(session, scrutin)
                report.scrutins_upserts += 1
            await session.commit()

        # 3) Journal.
        report.finished_at = datetime.now(timezone.utc)
        async with self._sf() as session:
            session.add(
                SyncRunRow(
                    legislature=self._client.legislature,
                    started_at=report.started_at,
                    finished_at=report.finished_at,
                    scrutins_vus=report.scrutins_vus,
                    scrutins_upserts=report.scrutins_upserts,
                    anomalies=report.anomalies[:200],
                )
            )
            await session.commit()
        return report
