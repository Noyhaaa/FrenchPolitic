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
from app.ingestion.dossiers_legislatifs import construire_reconciliation
from app.ingestion.textes_an import (
    construire_expose,
    construire_index_textes,
    url_page_texte,
)
from app.ingestion.normalize import (
    auteur_amendement,
    est_amendement,
    est_sous_amendement,
    numero_amendement,
    numero_amendement_parent,
)
from app.ingestion.organes import (
    GroupResolver,
    build_acteurs_from_amo,
    build_resolver_from_organes,
)
from app.ai.faits import construire_faits
from app.ai.generation import generer_resume
from app.schemas import (
    Amendement,
    Dossier,
    MiseAJourDossier,
    Scrutin,
    ScrutinResume,
    SourceOfficielle,
)
from app.utils.text import fold

# Nombre max de textes déposés essayés par dossier pour récupérer l'exposé des
# motifs (dépôt initial d'abord). Borne les requêtes réseau par dossier.
_MAX_TENTATIVES_EXPOSE = 3


@dataclass
class SyncReport:
    started_at: datetime
    scrutins_vus: int = 0
    dossiers_upserts: int = 0
    exposes_recuperes: int = 0
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


def _amendement_from_scrutin(scrutin: Scrutin) -> Amendement:
    """Un vote d'amendement → entrée d'amendement (liée à son scrutin public).

    Numéro et auteur sont extraits de l'objet officiel quand ils sont sans
    ambiguïté ; sinon absents (§2.5 : on n'invente pas).
    """
    return Amendement(
        id=scrutin.id,
        numero=numero_amendement(scrutin.objet),
        objet=scrutin.objet,
        auteur=auteur_amendement(scrutin.objet),
        sort="adopte" if scrutin.statut.value == "adopte" else "rejete",
        scrutin_id=scrutin.id,
    )


def _structurer_amendements(votes: list[Scrutin]) -> list[Amendement]:
    """Structure les votes d'amendement d'un dossier.

    Les sous-amendements sont rattachés à leur amendement parent (identifié par
    « … à l'amendement n° X ») ; un sous-amendement sans parent identifiable
    reste au niveau du dossier (factuel, rien n'est déduit).
    """
    amendements = [
        _amendement_from_scrutin(s) for s in votes if not est_sous_amendement(s.objet)
    ]
    par_numero = {a.numero: a for a in amendements if a.numero}
    for s in votes:
        if not est_sous_amendement(s.objet):
            continue
        sous = _amendement_from_scrutin(s)
        parent = par_numero.get(numero_amendement_parent(s.objet) or "")
        if parent is not None:
            parent.sous_amendements.append(sous)
        else:
            amendements.append(sous)
    return amendements


def build_dossier(parses: list[ScrutinParse]) -> Dossier:
    """Agrège les scrutins d'un même dossier (ordre : du plus récent au plus ancien).

    Les votes sur le **texte** (ensemble, articles, motions) peuplent la liste
    compacte `scrutins` ; les votes d'**amendement** peuplent `amendements` (avec
    un lien vers leur scrutin) — ils n'apparaissent donc pas deux fois. Le détail
    complet de chaque vote (groupes, nominatif) vit dans la table `scrutin`.
    """
    tous = sorted((p.scrutin for p in parses), key=lambda s: s.date, reverse=True)
    ref = parses[0]  # métadonnées de dossier partagées
    titre_clair = ref.dossier_titre[:90].rstrip()

    votes_texte = [s for s in tous if not est_amendement(s.objet)]
    votes_amendement = [s for s in tous if est_amendement(s.objet)]

    # Sources de NIVEAU DOSSIER uniquement : la page du dossier législatif.
    # Chaque vote (texte, amendement, sous-amendement) garde sa source sur sa
    # propre fiche (§7.5 s'applique écran par écran) — les répéter ici ne
    # ferait que dupliquer. Sans référence de dossier, repli factuel sur les
    # sources des votes.
    if ref.dossier_ref:
        sources = [dossier_source(ref.legislature, ref.dossier_ref)]
    else:
        sources = [src for s in (votes_texte or tous) for src in s.sources]

    return Dossier(
        id=ref.dossier_id,
        titre_officiel=ref.dossier_titre,
        titre_clair=titre_clair,
        accroche=ref.dossier_titre,
        # Statut / date du dossier = scrutin le plus récent, amendements compris.
        statut=tous[0].statut,
        phase=None,
        theme=ref.theme,
        temps_lecture_sec=30,
        date_dernier_scrutin=tous[0].date,
        mise_a_jour=None,
        scrutins=[ScrutinResume.from_scrutin(s) for s in votes_texte],
        amendements=_structurer_amendements(votes_amendement),
        sources=_dedupe_sources(sources),
        # Résumé neutre par gabarit, ancré sur les faits des scrutins (§4.1).
        resume=generer_resume(
            construire_faits(
                titre_clair=titre_clair,
                titre_officiel=ref.dossier_titre,
                theme=ref.theme,
                votes_texte=votes_texte,
                votes_amendement=votes_amendement,
            )
        ),
    )


def _merge_avec_existant(prev: Dossier, incoming: Dossier) -> Dossier:
    """Fusionne un dossier fraîchement construit avec sa version en base.

    Conserve les votes (texte et amendement) déjà connus, ajoute les nouveaux, et
    pose le badge « mis à jour » (§7.7) si un nouveau scrutin est apparu.
    """
    def _ids(liste: list[Amendement]) -> set[str]:
        return {a.id for a in liste} | {sa.id for a in liste for sa in a.sous_amendements}

    # Le build frais fait autorité sur la CLASSIFICATION (texte vs amendement) :
    # un id qu'il classe amendement ne doit pas rester dans les votes sur le
    # texte, et inversement. Sans ce garde-fou, un vote ingéré sous une ancienne
    # version (ou reclassé après un changement d'heuristique) resterait dupliqué
    # dans les deux listes — chaque id doit vivre dans exactement une liste.
    am_ids_frais = _ids(incoming.amendements)
    texte_ids_frais = {s.id for s in incoming.scrutins}

    # Votes sur le texte (liste compacte) : union (les fraîches priment), en
    # retirant tout id désormais classé amendement.
    by_id = {s.id: s for s in prev.scrutins}
    for s in incoming.scrutins:
        by_id[s.id] = s
    scrutins = sorted(
        (s for s in by_id.values() if s.id not in am_ids_frais),
        key=lambda s: s.date,
        reverse=True,
    )

    # Amendements (sous-amendements compris) : union, en retirant tout id
    # désormais classé vote sur le texte (au premier niveau comme en sous).
    am_by_id = {a.id: a for a in prev.amendements}
    for a in incoming.amendements:
        connu = am_by_id.get(a.id)
        if connu is not None:
            # Union des sous-amendements (les données fraîches priment).
            sa_by_id = {sa.id: sa for sa in connu.sous_amendements}
            for sa in a.sous_amendements:
                sa_by_id[sa.id] = sa
            a.sous_amendements = list(sa_by_id.values())
        am_by_id[a.id] = a
    amendements: list[Amendement] = []
    for a in am_by_id.values():
        if a.id in texte_ids_frais:
            continue
        a.sous_amendements = [
            sa for sa in a.sous_amendements if sa.id not in texte_ids_frais
        ]
        amendements.append(a)

    # « mis à jour » (§7.7) : un vote vu ce run et inconnu jusqu'ici (dans l'une
    # ou l'autre liste). Une simple reclassification n'est pas un nouveau vote.
    prev_ids = {s.id for s in prev.scrutins} | _ids(prev.amendements)
    nouveaux = bool((texte_ids_frais | am_ids_frais) - prev_ids)

    incoming.scrutins = scrutins
    incoming.amendements = amendements
    # Date / statut : le plus récent entre l'existant et l'arrivant (le build a
    # calculé l'arrivant sur tous ses votes, amendements compris).
    if prev.date_dernier_scrutin > incoming.date_dernier_scrutin:
        incoming.date_dernier_scrutin = prev.date_dernier_scrutin
        incoming.statut = prev.statut
    # Sources : niveau dossier uniquement. La page du dossier législatif
    # (type « texte ») est stable inter-runs → la version fraîche suffit (et
    # purge d'anciennes sources par-scrutin) ; en repli (pas de page dossier),
    # union pour ne pas perdre les sources des runs passés.
    if any(s.type == "texte" for s in incoming.sources):
        incoming.sources = _dedupe_sources(incoming.sources)
    else:
        incoming.sources = _dedupe_sources(incoming.sources + prev.sources)
    # Résumé : le gabarit est déterministe et reflète les faits à jour, donc on
    # garde la version fraîche. On ne préserve QUE le résumé relu/édité par un
    # humain (le travail éditorial ne doit pas être écrasé par une régénération).
    if prev.resume.relu_par_humain:
        incoming.resume = prev.resume
    # Exposé des motifs : stable (texte déposé). Si ce run n'a pas pu le
    # récupérer (réseau, PDF momentanément absent), on garde celui déjà en base
    # plutôt que de le perdre.
    if incoming.expose_motifs is None and prev.expose_motifs is not None:
        incoming.expose_motifs = prev.expose_motifs

    if nouveaux:
        incoming.mise_a_jour = MiseAJourDossier(
            date=incoming.date_dernier_scrutin, label="Nouveau vote"
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


async def _upsert_dossier(session: AsyncSession, dossier: Dossier) -> Dossier:
    """Upsert du dossier ; renvoie la version effectivement écrite (fusionnée)."""
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
    return dossier


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

    async def _enrichir_expose(
        self,
        dossier: Dossier,
        dossier_ref: str | None,
        index_textes: dict[str, list[str]],
        report: SyncReport,
    ) -> None:
        """Attache l'exposé des motifs du texte (PDF officiel) au dossier.

        Essaie les textes déposés candidats **du dépôt initial au plus récent**
        (l'exposé n'est que dans le dépôt initial ; les versions de navette ne
        l'ont pas), borné à `_MAX_TENTATIVES_EXPOSE`. Best-effort et silencieux
        en cas d'échec (§2.5) : sans exposé récupérable, le dossier n'en porte pas.
        """
        uids = index_textes.get(dossier_ref or "")
        if not uids:
            return
        for uid in uids[:_MAX_TENTATIVES_EXPOSE]:
            url_page = url_page_texte(uid)
            if not url_page:
                continue
            pdf = await self._client.download_texte_pdf(url_page + ".pdf")
            if not pdf:
                continue
            expose = construire_expose(uid, pdf)
            if expose is not None:
                dossier.expose_motifs = expose
                report.exposes_recuperes += 1
                return

    async def run(self, limit: int | None = None) -> SyncReport:
        report = SyncReport(started_at=datetime.now(timezone.utc))

        # 1) Référentiels AMO : groupes + annuaire des députés (nominatif).
        organes, acteurs_bruts = await self._client.download_amo()
        resolver = build_resolver_from_organes(organes)
        acteurs = build_acteurs_from_amo(acteurs_bruts)
        async with self._sf() as session:
            report.groupes = await _upsert_groupes(session, resolver)
            await session.commit()

        # 1bis) Dossiers législatifs : titres officiels + réconciliation des
        #       scrutins sans dossierRef vers leur vrai dossier (§5.1).
        documents = await self._client.download_dossiers()
        reconciliation = construire_reconciliation(
            documents, self._client.legislature
        )
        # Index dossierRef → texte AN déposé, pour récupérer l'exposé des motifs
        # (PDF officiel) au niveau du dossier — bloc attribué, option (a).
        index_textes = construire_index_textes(documents, self._client.legislature)

        # 2) Scrutins → parsing (avec nominatif) → regroupement par dossier.
        bruts = await self._client.download_scrutins(limit=limit)
        report.scrutins_vus = len(bruts)
        par_dossier: dict[str, list[ScrutinParse]] = {}
        for brut in bruts:
            try:
                parse = parse_scrutin(brut, resolver, acteurs, reconciliation)
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
                await self._enrichir_expose(
                    dossier, parses[0].dossier_ref, index_textes, report
                )
                dossier = await _upsert_dossier(session, dossier)
                # Le scrutin d'un amendement embarque ses sous-amendements :
                # la fiche vote de l'amendement les liste (dossier fusionné =
                # rattachements connus, runs précédents compris).
                sous_par_scrutin = {
                    a.scrutin_id: a.sous_amendements
                    for a in dossier.amendements
                    if a.scrutin_id and a.sous_amendements
                }
                for p in parses:
                    if p.scrutin.id in sous_par_scrutin:
                        p.scrutin.sous_amendements = sous_par_scrutin[p.scrutin.id]
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
