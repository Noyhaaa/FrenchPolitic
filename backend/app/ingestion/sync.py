"""Job de synchronisation open data → PostgreSQL (§5.2, §6).

Enchaîne : organes (groupes) → scrutins publics → parsing → contrôles de
cohérence → **regroupement par dossier** → upsert. Idempotent (upsert par id de
dossier), relançable plusieurs fois par jour. Lorsqu'un nouveau scrutin se
rattache à un dossier déjà connu, le dossier est marqué « mis à jour » (§7.7).
Journalise chaque exécution (table sync_run) pour l'observabilité (§8).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import DossierRow, GroupeRow, ScrutinRow, SyncRunRow
from app.ingestion.assemblee import (
    AssembleeOpenDataClient,
    ScrutinParse,
    dossier_source,
    parse_scrutin,
)
from app.ingestion.organes import (
    GroupResolver,
    build_acteurs_from_amo,
    build_resolver_from_organes,
)
from app.schemas import (
    Dossier,
    MiseAJourDossier,
    ResumeScrutin,
    Scrutin,
    ScrutinResume,
    SourceOfficielle,
)
from app.utils.text import fold


@dataclass
class SyncReport:
    started_at: datetime
    scrutins_vus: int = 0
    dossiers_upserts: int = 0
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


def _dedupe_sources(sources: list[SourceOfficielle]) -> list[SourceOfficielle]:
    seen: set[str] = set()
    out: list[SourceOfficielle] = []
    for s in sources:
        if s.url not in seen:
            seen.add(s.url)
            out.append(s)
    return out


def _empty_resume(titre_clair: str) -> ResumeScrutin:
    """Résumé non comblé (§2.5) — la génération IA viendra en Phase 2."""
    return ResumeScrutin(
        titre_clair=titre_clair,
        resume=[],
        public_concerne=[],
        confiance="faible",
        relu_par_humain=False,
        champs_non_documentes=["resume", "contexte", "objectif", "public_concerne"],
    )


def build_dossier(parses: list[ScrutinParse]) -> Dossier:
    """Agrège les scrutins d'un même dossier (ordre : du plus récent au plus ancien).

    Le dossier n'embarque que des `ScrutinResume` (liste compacte) : le détail
    complet de chaque vote (groupes, nominatif) vit dans la table `scrutin`.
    """
    scrutins = sorted((p.scrutin for p in parses), key=lambda s: s.date, reverse=True)
    ref = parses[0]  # métadonnées de dossier partagées
    titre_clair = ref.dossier_titre[:90].rstrip()

    sources: list[SourceOfficielle] = []
    if ref.dossier_ref:
        sources.append(dossier_source(ref.legislature, ref.dossier_ref))
    for s in scrutins:
        sources.extend(s.sources)

    return Dossier(
        id=ref.dossier_id,
        titre_officiel=ref.dossier_titre,
        titre_clair=titre_clair,
        accroche=ref.dossier_titre,
        # Statut du dossier = résultat du scrutin le plus récent (défensif).
        statut=scrutins[0].statut,
        phase=None,
        theme=ref.theme,
        temps_lecture_sec=30,
        date_dernier_scrutin=scrutins[0].date,
        mise_a_jour=None,
        scrutins=[ScrutinResume.from_scrutin(s) for s in scrutins],
        amendements=[],  # nécessite les données de dossier (Phase 2)
        sources=_dedupe_sources(sources),
        resume=_empty_resume(titre_clair),
    )


def _merge_avec_existant(prev: Dossier, incoming: Dossier) -> Dossier:
    """Fusionne un dossier fraîchement construit avec sa version en base.

    Conserve les scrutins déjà connus, ajoute les nouveaux, et pose le badge
    « mis à jour » (§7.7) si de nouveaux scrutins sont apparus.
    """
    prev_ids = {s.id for s in prev.scrutins}
    by_id = {s.id: s for s in prev.scrutins}
    for s in incoming.scrutins:
        by_id[s.id] = s  # les données fraîches priment pour un même scrutin
    scrutins = sorted(by_id.values(), key=lambda s: s.date, reverse=True)

    nouveaux = [s for s in scrutins if s.id not in prev_ids]

    incoming.scrutins = scrutins
    incoming.date_dernier_scrutin = scrutins[0].date
    incoming.statut = scrutins[0].statut
    incoming.sources = _dedupe_sources(prev.sources + incoming.sources)
    # Conserve un résumé déjà généré (Phase 2) plutôt que l'écraser par un vide.
    if prev.resume.resume:
        incoming.resume = prev.resume

    if nouveaux:
        plus_recent = nouveaux[0]  # scrutins triés desc → le plus récent d'abord
        incoming.mise_a_jour = MiseAJourDossier(
            date=plus_recent.date, label="Nouveau vote"
        )
    else:
        incoming.mise_a_jour = prev.mise_a_jour  # conserve un éventuel badge
    return incoming


def _dossier_row_values(dossier: Dossier) -> dict:
    return {
        "id": dossier.id,
        "date": dossier.date_dernier_scrutin,
        "statut": dossier.statut.value,
        "theme": dossier.theme,
        "titre_clair": dossier.titre_clair,
        "titre_officiel": dossier.titre_officiel,
        "accroche": dossier.accroche,
        "temps_lecture_sec": dossier.temps_lecture_sec,
        "nombre_scrutins": len(dossier.scrutins),
        "mise_a_jour": (
            dossier.mise_a_jour.model_dump(mode="json", by_alias=True)
            if dossier.mise_a_jour
            else None
        ),
        "payload": dossier.model_dump(mode="json", by_alias=True),
        "search_index": fold(
            f"{dossier.titre_clair} {dossier.titre_officiel} "
            f"{dossier.accroche} {dossier.theme}"
        ),
    }


async def _upsert_dossier(session: AsyncSession, dossier: Dossier) -> None:
    existing = await session.get(DossierRow, dossier.id)
    if existing is not None:
        prev = Dossier.model_validate(existing.payload)
        dossier = _merge_avec_existant(prev, dossier)
    values = _dossier_row_values(dossier)
    stmt = insert(DossierRow).values(**values)
    update = {k: v for k, v in values.items() if k != "id"}
    await session.execute(
        stmt.on_conflict_do_update(index_elements=["id"], set_=update)
    )


async def _upsert_scrutin(session: AsyncSession, scrutin: Scrutin) -> None:
    """Détail complet d'un vote (dont nominatif) — servi par GET /scrutins/{id}."""
    values = {
        "id": scrutin.id,
        "dossier_id": scrutin.dossier_id,
        "date": scrutin.date,
        "payload": scrutin.model_dump(mode="json", by_alias=True),
    }
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

        # 1) Référentiels AMO : groupes + annuaire des députés (nominatif).
        organes, acteurs_bruts = await self._client.download_amo()
        resolver = build_resolver_from_organes(organes)
        acteurs = build_acteurs_from_amo(acteurs_bruts)
        async with self._sf() as session:
            report.groupes = await _upsert_groupes(session, resolver)
            await session.commit()

        # 2) Scrutins → parsing (avec nominatif) → regroupement par dossier.
        bruts = await self._client.download_scrutins(limit=limit)
        report.scrutins_vus = len(bruts)
        par_dossier: dict[str, list[ScrutinParse]] = {}
        for brut in bruts:
            try:
                parse = parse_scrutin(brut, resolver, acteurs)
            except (KeyError, TypeError) as exc:
                report.anomalies.append(f"parsing échoué: {exc}")
                continue
            report.anomalies.extend(controles_coherence(parse.scrutin))
            par_dossier.setdefault(parse.dossier_id, []).append(parse)

        # 3) Upsert des dossiers (fusion avec l'existant → badge « mis à jour »)
        #    et du détail de chaque vote (table scrutin).
        async with self._sf() as session:
            for parses in par_dossier.values():
                dossier = build_dossier(parses)
                await _upsert_dossier(session, dossier)
                for p in parses:
                    await _upsert_scrutin(session, p.scrutin)
                report.dossiers_upserts += 1
            await session.commit()

        # 4) Journal.
        report.finished_at = datetime.now(timezone.utc)
        async with self._sf() as session:
            session.add(
                SyncRunRow(
                    legislature=self._client.legislature,
                    started_at=report.started_at,
                    finished_at=report.finished_at,
                    scrutins_vus=report.scrutins_vus,
                    dossiers_upserts=report.dossiers_upserts,
                    anomalies=report.anomalies[:200],
                )
            )
            await session.commit()
        return report
