"""Job de synchronisation open data → PostgreSQL (§5.2, §6).

Enchaîne : organes (groupes) → scrutins publics → parsing → contrôles de
cohérence → **regroupement par dossier** → upsert. Idempotent (upsert par id de
dossier), relançable plusieurs fois par jour. Lorsqu'un nouveau scrutin se
rattache à un dossier déjà connu, le dossier est marqué « mis à jour » (§7.7).
Journalise chaque exécution (table sync_run) pour l'observabilité (§8).
"""
from __future__ import annotations

import re
import zipfile
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime, timezone

import httpx
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import DossierRow, GroupeRow, ScrutinRow, SyncRunRow
from app.ingestion.assemblee import (
    AssembleeOpenDataClient,
    ScrutinParse,
    dossier_source,
    parse_scrutin,
)
from app.ingestion.amendements import AmendementEnrichi, enrichir as enrichir_amendement
from app.ingestion.deputes import (
    attacher_portraits,
    build_deputes_from_amo,
    remplacer_votes_du_scrutin,
    upsert_deputes,
    votes_du_scrutin,
)
from app.domain.recherche import index_recherche
from app.ingestion.debats import IndexDebats, url_compte_rendu
from app.ingestion.dossiers_legislatifs import construire_reconciliation
from app.ingestion.textes_an import (
    construire_dispositif,
    construire_expose,
    construire_index_numeros,
    construire_index_textes,
    lire_pdf,
    url_page_texte,
)
from app.ingestion.textes_senat import (
    construire_dispositif_senat,
    construire_expose_senat,
    reference_senat,
    urls_pdf_senat,
)
from app.ingestion.normalize import (
    THEMES,
    auteur_amendement,
    est_amendement,
    est_sous_amendement,
    est_texte_procedural,
    numero_amendement,
    numero_amendement_parent,
    titre_court,
)
from app.ingestion.organes import (
    GroupInfo,
    GroupResolver,
    build_acteurs_from_amo,
    build_resolver_from_organes,
)
from app.ai.faits import construire_faits
from app.ai.generation import generer_resume
from app.ai.llm import LLMClient
from app.ai.questions import (
    accroche_depuis_q1,
    generer_desaccord,
    generer_questions,
    generer_questions_amendement,
)
from app.ai.publics import classifier_publics
from app.ai.theme import classifier_theme
from app.schemas import (
    Amendement,
    ArgumentGroupe,
    DispositifTexte,
    Dossier,
    ExposeMotifs,
    MiseAJourDossier,
    PositionGroupe,
    QuestionsAmendement,
    QuestionsCitoyennes,
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
    # Sous-ensemble des exposés récupérés via senat.fr (textes d'origine Sénat).
    exposes_senat: int = 0
    # Dispositifs (articles du texte déposé) extraits du même PDF que l'exposé —
    # source de la Q4 factuelle. Les textes trop longs (budget) n'en ont pas.
    dispositifs_recuperes: int = 0
    themes_reclasses: int = 0
    questions_generees: int = 0
    # Dossiers dont la Q4 vient du dispositif officiel (fait) et non de l'exposé
    # (parole de l'auteur) — mesure la bascule visée par ce chantier.
    changements_factuels: int = 0
    # Dossiers dont « Qui est concerné ? » a été renseigné ce run (liste fermée).
    publics_classes: int = 0
    # Votes d'amendement dont une question LLM (pourquoi/changement) a été
    # générée ce run (le résultat, déterministe, n'est pas compté).
    questions_amendements_generees: int = 0
    desaccords_generes: int = 0
    # Votes d'amendement enrichis d'un contenu (dispositif ou exposé sommaire).
    amendements_enrichis: int = 0
    # Dossiers supprimés car vidés de leurs scrutins (ex. TXT- migrés vers un
    # dossier officiel après amélioration de la réconciliation).
    dossiers_orphelins_supprimes: int = 0
    groupes: int = 0
    # Référentiel des députés (AMO) et lignes de vote nominatif écrites (§5.2).
    deputes: int = 0
    portraits: int = 0
    votes_deputes: int = 0
    # LLM configuré mais injoignable au démarrage → run sans LLM (visible).
    llm_indisponible: bool = False
    # Appels LLM en échec définitif malgré les retries (sinon un échec réseau
    # est indistinguable d'une réponse rejetée — vécu : 48 dossiers sans Q2).
    llm_echecs: int = 0
    # Abréviations de groupe vues au CR (explications de vote) mais non résolues
    # par l'annuaire AMO → le groupe est silencieusement retiré du désaccord
    # (asymétrie §7.4). On les collecte pour compléter `_ALIAS_ABBREV` sur preuve,
    # sans jamais deviner d'alias (§2.5).
    abrevs_non_resolues: set[str] = field(default_factory=set)
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


# Un texte mono-article se vote « article unique » : ce vote EST le vote sur le
# texte, il n'y a pas de vote sur l'ensemble derrière.
_RE_ARTICLE_UNIQUE = re.compile(r"^l'article unique\b")
# Le texte cité directement, sans « l'ensemble de » : c'est le cas des
# résolutions (art. 34-1) et de quelques projets d'approbation d'accord.
_RE_TEXTE_DIRECT = re.compile(r"^l[ae] (?:proposition|projet) de (?:loi|resolution)\b")
# Motions qui closent l'examen d'un texte (rejet préalable, référendaire,
# ajournement) : leur débat est un vrai moment de positions de groupe.
_RE_MOTION = re.compile(r"^la motion\b")


def _vote_conclusif(votes_texte: list[Scrutin]) -> Scrutin | None:
    """Le vote qui **conclut** l'examen du texte, ancre du désaccord (Q2).

    C'est ce vote-là que précèdent les explications de vote, et c'est de LUI que
    viennent les positions de groupe affichées. Ordre de priorité — le premier
    critère satisfait gagne :

    1. le vote sur l'**ensemble** ;
    2. le vote sur l'**article unique** (texte mono-article) ;
    3. le vote sur le **texte cité directement** (résolution, approbation d'accord) ;
    4. le vote **procédural** (motion de censure, déclaration de politique générale) ;
    5. la **motion** de rejet préalable / référendaire / d'ajournement.

    Jamais un vote d'article numéroté : le débat sur l'article 27 du budget n'est
    pas une prise de position sur le texte. Un dossier qui n'a que de tels votes
    (ou que des amendements, déjà filtrés en amont) n'a donc pas d'ancre et
    restera sans désaccord (§2.5 : on ne fabrique rien).
    """
    criteres = (
        lambda o: "ensemble" in o,
        lambda o: _RE_ARTICLE_UNIQUE.match(o) is not None,
        lambda o: _RE_TEXTE_DIRECT.match(o) is not None,
        lambda o: est_texte_procedural(o),
        lambda o: _RE_MOTION.match(o) is not None,
    )
    plies = [(s, fold(s.objet)) for s in votes_texte]
    for critere in criteres:
        for scrutin, objet in plies:
            if critere(objet):
                return scrutin
    return None


def _position_documentee(position: PositionGroupe) -> bool:
    """Le groupe a-t-il un vote **exprimé** sur ce scrutin ?

    ⚠️ Sur une **motion de censure**, la Constitution (art. 49) ne fait recenser
    que les votes FAVORABLES : l'open data porte alors `positionMajoritaire =
    « pour »` pour TOUS les groupes, y compris ceux dont aucun député n'a voté
    (décompte 0/0/0). S'y fier reviendrait à afficher « Pour » en face de groupes
    qui combattaient la motion — c'est le cas réel qui a motivé ce contrôle.

    On ne retient donc une position que si la source la documente par au moins
    une voix (§2.5). Un groupe sans vote exprimé est simplement absent du
    désaccord, comme un groupe dont la paraphrase a été rejetée.
    """
    return (position.pour + position.contre + position.abstention) > 0


def _positions_documentees(
    arguments: list[ArgumentGroupe], ancre: Scrutin
) -> list[ArgumentGroupe]:
    """Réaligne les `sens` d'un désaccord sur le scrutin d'ancrage courant.

    Le sens est une **donnée du scrutin**, jamais une sortie de modèle : on le
    recompose à chaque run (comme Q3) plutôt que de faire confiance à ce qui est
    en base — un désaccord stocké avant ce contrôle porte des positions que la
    source ne documente pas. Groupe sans vote exprimé → argument retiré (§2.5).
    """
    par_nom = {
        p.groupe_nom: p for p in ancre.positions_groupes if _position_documentee(p)
    }
    retenus: list[ArgumentGroupe] = []
    for a in arguments:
        pos = par_nom.get(a.groupe)
        if pos is None:
            continue
        retenus.append(
            ArgumentGroupe(
                groupe=a.groupe,
                sens=pos.position_majoritaire,
                argument=a.argument,
            )
        )
    return retenus


def _dedupe_sources(sources: list[SourceOfficielle]) -> list[SourceOfficielle]:
    seen: set[str] = set()
    out: list[SourceOfficielle] = []
    for s in sources:
        if s.url not in seen:
            seen.add(s.url)
            out.append(s)
    return out


IndexAmendements = dict[tuple[str, str], list[AmendementEnrichi]]


def _amendement_from_scrutin(
    scrutin: Scrutin, index: IndexAmendements | None = None
) -> Amendement:
    """Un vote d'amendement → entrée d'amendement (liée à son scrutin public).

    Numéro et auteur sont extraits de l'objet officiel quand ils sont sans
    ambiguïté ; sinon absents (§2.5 : on n'invente pas). Quand l'archive des
    amendements est disponible, on attache le **contenu** (dispositif), l'exposé
    sommaire (côté auteur, attribué) et l'article visé.
    """
    numero = numero_amendement(scrutin.objet)
    cible = dispositif = expose = None
    if index is not None:
        try:
            date_vote = date.fromisoformat(scrutin.date[:10])
        except ValueError:
            date_vote = None
        enrichi = enrichir_amendement(index, scrutin.dossier_id, numero, date_vote)
        if enrichi is not None:
            cible = enrichi.cible
            dispositif = enrichi.dispositif
            expose = enrichi.expose_sommaire
    return Amendement(
        id=scrutin.id,
        numero=numero,
        objet=scrutin.objet,
        auteur=auteur_amendement(scrutin.objet),
        sort="adopte" if scrutin.statut.value == "adopte" else "rejete",
        cible=cible,
        dispositif=dispositif,
        expose_sommaire=expose,
        scrutin_id=scrutin.id,
    )


def _structurer_amendements(
    votes: list[Scrutin], index: IndexAmendements | None = None
) -> list[Amendement]:
    """Structure les votes d'amendement d'un dossier.

    Les sous-amendements sont rattachés à leur amendement parent (identifié par
    « … à l'amendement n° X ») ; un sous-amendement sans parent identifiable
    reste au niveau du dossier (factuel, rien n'est déduit).
    """
    amendements = [
        _amendement_from_scrutin(s, index)
        for s in votes
        if not est_sous_amendement(s.objet)
    ]
    par_numero = {a.numero: a for a in amendements if a.numero}
    for s in votes:
        if not est_sous_amendement(s.objet):
            continue
        sous = _amendement_from_scrutin(s, index)
        parent = par_numero.get(numero_amendement_parent(s.objet) or "")
        if parent is not None:
            parent.sous_amendements.append(sous)
        else:
            amendements.append(sous)
    return amendements


def build_dossier(
    parses: list[ScrutinParse], index_amendements: IndexAmendements | None = None
) -> Dossier:
    """Agrège les scrutins d'un même dossier (ordre : du plus récent au plus ancien).

    Les votes sur le **texte** (ensemble, articles, motions) peuplent la liste
    compacte `scrutins` ; les votes d'**amendement** peuplent `amendements` (avec
    un lien vers leur scrutin) — ils n'apparaissent donc pas deux fois. Le détail
    complet de chaque vote (groupes, nominatif) vit dans la table `scrutin`.
    """
    tous = sorted((p.scrutin for p in parses), key=lambda s: s.date, reverse=True)
    ref = parses[0]  # métadonnées de dossier partagées
    # Titre d'affichage : sans la nature (rendue en label à part), sans troncature
    # en plein mot — l'app clampe elle-même sur 2 lignes (§8).
    titre_clair = titre_court(ref.dossier_titre)

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
        # Posée plus tard dans le run, une fois la Q1 disponible
        # (`SyncJob._composer_accroche`) — sinon rien (§2.5).
        accroche=None,
        # Statut / date du dossier = scrutin le plus récent, amendements compris.
        statut=tous[0].statut,
        phase=None,
        theme=ref.theme,
        temps_lecture_sec=30,
        date_dernier_scrutin=tous[0].date,
        mise_a_jour=None,
        scrutins=[ScrutinResume.from_scrutin(s) for s in votes_texte],
        amendements=_structurer_amendements(votes_amendement, index_amendements),
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
            # Enrichissement (contenu/exposé/cible) : best-effort. Si l'archive
            # des amendements n'a pas été téléchargée ce run, le build frais
            # arrive sans contenu → on préserve celui déjà en base plutôt que de
            # l'effacer.
            if a.dispositif is None and a.expose_sommaire is None and a.cible is None:
                a.cible = connu.cible
                a.dispositif = connu.dispositif
                a.expose_sommaire = connu.expose_sommaire
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
        # L'accroche est dérivée de la Q1 : elle suit le résumé retenu.
        incoming.accroche = accroche_depuis_q1(
            prev.resume.questions.pourquoi if prev.resume.questions else None
        )
    # Exposé des motifs : stable (texte déposé). Si ce run n'a pas pu le
    # récupérer (réseau, PDF momentanément absent), on garde celui déjà en base
    # plutôt que de le perdre.
    if incoming.expose_motifs is None and prev.expose_motifs is not None:
        incoming.expose_motifs = prev.expose_motifs
    # Dispositif : même raisonnement (extrait du même PDF, tout aussi stable).
    if incoming.dispositif is None and prev.dispositif is not None:
        incoming.dispositif = prev.dispositif
    # Publics concernés : acquis d'un run avec LLM, préservés sur un run sans.
    if not incoming.resume.public_concerne and prev.resume.public_concerne:
        incoming.resume.public_concerne = prev.resume.public_concerne
        incoming.resume.champs_non_documentes = [
            c for c in incoming.resume.champs_non_documentes if c != "public_concerne"
        ]
    # Thème : ne pas régresser un thème déjà affiné vers « Autre » si ce run a
    # tourné sans LLM (ou si le LLM n'a rien renvoyé de valide).
    if incoming.theme == "Autre" and prev.theme != "Autre":
        incoming.theme = prev.theme

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
        # La colonne est NOT NULL : pas d'accroche → chaîne vide, reconvertie en
        # None à la lecture (`postgres._to_list_item`).
        "accroche": dossier.accroche or "",
        "temps_lecture_sec": dossier.temps_lecture_sec,
        "nombre_scrutins": len(dossier.scrutins),
        "mise_a_jour": (
            dossier.mise_a_jour.model_dump(mode="json", by_alias=True)
            if dossier.mise_a_jour
            else None
        ),
        "payload": dossier.model_dump(mode="json", by_alias=True),
        "search_index": index_recherche(dossier),
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
        llm: LLMClient | None = None,
        on_progress: Callable[[int, int, str], None] | None = None,
    ) -> None:
        self._sf = session_factory
        self._client = client or AssembleeOpenDataClient()
        # Appelé après chaque dossier committé (index 1-based, total, titre) —
        # observabilité pendant un run long (des heures) sans autre signal
        # avant le rapport final. Optionnel : None (défaut) ne change rien.
        self._on_progress = on_progress
        # LLM optionnel : classification de thème + questions citoyennes (dont le
        # « désaccord » depuis les débats). None (défaut) → replis (heuristique,
        # « information non disponible ») et pas de téléchargement des débats.
        self._llm = llm
        # Renseignés en début de run() : index des débats + carte abréviation de
        # groupe → groupe (pour joindre explication de vote et position de vote).
        self._index_debats: IndexDebats | None = None
        # dossierRef → numéros de distribution AN de ses documents (liaison
        # certaine débat ↔ dossier, à travers la navette).
        self._numeros_par_ref: dict[str, set[int]] = {}
        # (dossierRef, numéro) → contenu d'amendement (dispositif, exposé sommaire,
        # article visé). Vide si l'archive (~300 Mo) n'a pas pu être téléchargée
        # ce run (best-effort : l'enrichissement déjà en base est préservé).
        self._index_amendements: IndexAmendements = {}
        self._groupes_par_abbrev: dict[str, GroupInfo] = {}
        # acteurRef (« PA… ») → (groupe_id, groupe_nom) du député, depuis l'annuaire
        # AMO : résout l'orateur d'une intervention en discussion générale vers son
        # groupe (le CR n'y écrit pas l'abréviation, cf. debats.py).
        self._groupe_par_acteur: dict[str, tuple[str, str]] = {}

    # Abréviations de groupe divergentes entre le compte rendu et l'annuaire AMO
    # (fold appliqué de part et d'autre). À compléter si de nouveaux cas surgissent.
    _ALIAS_ABBREV = {"udr": "uddplr"}

    def _indexer_groupes(self, resolver: GroupResolver) -> None:
        self._groupes_par_abbrev = {
            fold(g.abrev): g for g in resolver.all() if g.abrev and g.abrev != "?"
        }

    def _groupe_par_abbrev(self, abbrev: str) -> GroupInfo | None:
        cle = fold(abbrev)
        cle = self._ALIAS_ABBREV.get(cle, cle)
        return self._groupes_par_abbrev.get(cle)

    async def _texte_en_base(
        self, session: AsyncSession, dossier_id: str
    ) -> tuple[ExposeMotifs | None, DispositifTexte | None]:
        """L'exposé des motifs et le dispositif déjà persistés pour ce dossier."""
        row = await session.get(DossierRow, dossier_id)
        if row is None:
            return None, None
        payload = row.payload or {}
        brut_expose = payload.get("exposeMotifs")
        brut_dispositif = payload.get("dispositif")
        return (
            ExposeMotifs.model_validate(brut_expose) if brut_expose else None,
            DispositifTexte.model_validate(brut_dispositif) if brut_dispositif else None,
        )

    async def _enrichir_texte_depose(
        self,
        session: AsyncSession,
        dossier: Dossier,
        dossier_ref: str | None,
        index_textes: dict[str, list[str]],
        report: SyncReport,
    ) -> None:
        """Attache l'exposé des motifs ET le dispositif du texte (PDF officiel).

        Les deux sortent du **même PDF**, en un seul téléchargement : l'exposé
        est le « pourquoi » de l'auteur (non neutre §4.3), le dispositif est ce
        que le texte écrit (fait, source de la Q4 factuelle).

        Un texte déposé ne change pas : si les deux sont déjà en base, on les
        réutilise **sans réseau**. Sinon on essaie les textes déposés candidats
        **du dépôt initial au plus récent** (l'exposé n'est que dans le dépôt
        initial), borné à `_MAX_TENTATIVES_EXPOSE`. Quand le texte AN n'est
        qu'une **transmission du Sénat**, l'exposé est cherché sur senat.fr
        (§5.1). Best-effort et silencieux en cas d'échec (§2.5).

        Un texte dont le dispositif dépasse le cap (`_MAX_DISPOSITIF` : budget,
        PLFSS) n'en portera jamais : son PDF est donc retéléchargé à chaque run,
        coût accepté (quelques dizaines de dossiers) pour ne pas inventer un
        marqueur d'absence en base.
        """
        prev_expose, prev_dispositif = await self._texte_en_base(session, dossier.id)
        dossier.expose_motifs = prev_expose
        dossier.dispositif = prev_dispositif
        if prev_expose is not None and prev_dispositif is not None:
            return
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
            if dossier.dispositif is None:
                dispositif = construire_dispositif(uid, pdf)
                if dispositif is not None:
                    dossier.dispositif = dispositif
                    report.dispositifs_recuperes += 1
            if dossier.expose_motifs is None:
                expose = construire_expose(uid, pdf)
                if expose is not None:
                    dossier.expose_motifs = expose
                    report.exposes_recuperes += 1
                else:
                    # PDF AN = transmission Sénat ? L'exposé est alors sur senat.fr.
                    await self._enrichir_senat(dossier, pdf, report)
            if dossier.expose_motifs is not None and dossier.dispositif is not None:
                return

    async def _enrichir_senat(
        self, dossier: Dossier, pdf_transmission: bytes, report: SyncReport
    ) -> bool:
        """Récupère l'exposé (et le dispositif) sur senat.fr quand le texte AN
        est une transmission.

        Le numéro Sénat est cité dans le PDF de transmission ; on en dérive
        l'URL du PDF Sénat (préfixe pjl/ppl selon la nature, l'autre en repli)
        et on y extrait l'exposé. Renvoie True si un exposé a été attaché."""
        texte = lire_pdf(pdf_transmission)
        if not texte:
            return False
        ref = reference_senat(texte)
        if ref is None:
            return False
        projet = "projet de loi" in fold(dossier.titre_officiel)
        for url in urls_pdf_senat(ref, projet=projet):
            pdf_senat = await self._client.download_texte_pdf(url)
            if not pdf_senat:
                continue
            if dossier.dispositif is None:
                dispositif = construire_dispositif_senat(url, pdf_senat)
                if dispositif is not None:
                    dossier.dispositif = dispositif
                    report.dispositifs_recuperes += 1
            expose = construire_expose_senat(url, pdf_senat)
            if expose is not None:
                dossier.expose_motifs = expose
                report.exposes_recuperes += 1
                report.exposes_senat += 1
                return True
        return False

    async def _reclasser_theme(
        self, session: AsyncSession, dossier: Dossier, report: SyncReport
    ) -> None:
        """Affine le thème d'un dossier « Autre » via le LLM (liste fermée).

        On ne touche qu'aux dossiers que l'heuristique n'a pas su classer, et on
        n'applique qu'un thème **valide et non « Autre »** — sinon on garde
        l'existant (sortie LLM hors-liste/verbeuse → repli, cf. `classifier_theme`).
        Si un run précédent a déjà résolu ce dossier (thème en base ≠ « Autre »),
        on ne rappelle pas le LLM pour rien : la fusion (`_merge_avec_existant`)
        préserve de toute façon ce thème déjà acquis.
        """
        if self._llm is None or dossier.theme != "Autre":
            return
        deja_resolu = await self._theme_en_base(session, dossier.id)
        if deja_resolu is not None and deja_resolu != "Autre":
            return
        # L'exposé des motifs est déjà chargé (_enrichir_texte_depose, appelé
        # avant) : on le donne au classifieur comme signal supplémentaire.
        expose = dossier.expose_motifs.texte if dossier.expose_motifs else None
        nouveau = await classifier_theme(
            dossier.titre_officiel, self._llm, THEMES, objet=None, expose=expose
        )
        if nouveau and nouveau != "Autre":
            dossier.theme = nouveau
            report.themes_reclasses += 1

    async def _classifier_publics(
        self, session: AsyncSession, dossier: Dossier, report: SyncReport
    ) -> None:
        """Renseigne « Qui est concerné ? » depuis la liste fermée `PUBLICS`.

        Même garde-fou que le thème : sortie hors-liste rejetée, rien de valide
        → liste vide → section masquée (§2.5). Des publics déjà en base ne sont
        pas recalculés (le texte déposé ne change pas).
        """
        if self._llm is None:
            return
        deja = await self._publics_en_base(session, dossier.id)
        if deja:
            dossier.resume.public_concerne = deja
            self._marquer_documente(dossier)
            return
        expose = dossier.expose_motifs.texte if dossier.expose_motifs else None
        dispositif = dossier.dispositif.texte if dossier.dispositif else None
        if not expose and not dispositif:
            return
        publics = await classifier_publics(
            dossier.titre_officiel, self._llm, expose=expose, dispositif=dispositif
        )
        if publics:
            dossier.resume.public_concerne = publics
            self._marquer_documente(dossier)
            report.publics_classes += 1

    @staticmethod
    def _marquer_documente(dossier: Dossier) -> None:
        """Retire « public_concerne » des champs annoncés non documentés — le
        gabarit l'y met par défaut (`app.ai.gabarit`), faute de le connaître au
        moment où il compose le résumé."""
        dossier.resume.champs_non_documentes = [
            c for c in dossier.resume.champs_non_documentes if c != "public_concerne"
        ]

    async def _publics_en_base(
        self, session: AsyncSession, dossier_id: str
    ) -> list[str]:
        """Les publics déjà persistés pour ce dossier (liste vide si aucun)."""
        row = await session.get(DossierRow, dossier_id)
        if row is None:
            return []
        resume = (row.payload or {}).get("resume") or {}
        return list(resume.get("publicConcerne") or [])

    async def _theme_en_base(
        self, session: AsyncSession, dossier_id: str
    ) -> str | None:
        """Le thème déjà persisté pour ce dossier, s'il existe déjà en base."""
        row = await session.get(DossierRow, dossier_id)
        return row.theme if row is not None else None

    async def _questions_en_base(
        self, session: AsyncSession, dossier_id: str
    ) -> QuestionsCitoyennes | None:
        """Les questions déjà persistées pour ce dossier, s'il y en a."""
        row = await session.get(DossierRow, dossier_id)
        if row is None:
            return None
        brut = ((row.payload or {}).get("resume") or {}).get("questions")
        return QuestionsCitoyennes.model_validate(brut) if brut else None

    async def _construire_desaccord(
        self,
        dossier: Dossier,
        dossier_ref: str | None,
        votes_texte: list[Scrutin],
        questions: QuestionsCitoyennes,
        report: SyncReport,
    ) -> bool:
        """Renseigne Q2 (« principal désaccord ») depuis les débats de la séance.

        Relie le **vote conclusif** du texte (`_vote_conclusif`) au compte rendu
        (par numéro de texte, sinon date + titre) puis joint, PAR GROUPE, ses
        prises de parole aux positions du scrutin : le SENS (pour/contre) vient du
        scrutin, l'ARGUMENT est paraphrasé par le LLM et validé. Source des
        arguments : les **explications de vote** formelles si présentes, sinon
        **en repli** la **discussion générale** (mêmes garde-fous, §7.4).

        L'objet du vote d'ancrage est conservé (`desaccord_objet`) : les positions
        affichées sont celles exprimées SUR CE VOTE, et l'app doit pouvoir le dire
        — « pour » sur une motion de rejet préalable veut dire « pour le rejet du
        texte ». Renvoie True si au moins un argument a été produit."""
        if self._llm is None or self._index_debats is None:
            return False
        ancre = _vote_conclusif(votes_texte)
        if ancre is None:
            return False
        debat = self._index_debats.pour_vote(
            ancre.date,
            ancre.objet,
            self._numeros_par_ref.get(dossier_ref or ""),
        )
        if debat is None:
            return False
        positions = {g.groupe_id: g for g in ancre.positions_groupes}
        # Repli : explications de vote formelles d'abord, discussion générale sinon.
        prises = debat.explications or debat.interventions_generales
        interventions: list[tuple[str, object, str]] = []
        vus: set[str] = set()  # un seul argument par groupe (symétrie §7.4)
        for pdp in prises:
            if pdp.acteur_ref:  # discussion générale : orateur → groupe (annuaire)
                resolu = self._groupe_par_acteur.get(pdp.acteur_ref)
                if resolu is None:  # ministre / ancien député : hors annuaire
                    continue
                groupe_id, groupe_nom = resolu
            else:  # explication de vote : abréviation écrite au CR
                info = self._groupe_par_abbrev(pdp.groupe)
                if info is None:  # abréviation divergente → fuite mesurée (§7.4)
                    report.abrevs_non_resolues.add(pdp.groupe)
                    continue
                groupe_id, groupe_nom = info.id, info.nom
            if groupe_id in vus:
                continue
            pos = positions.get(groupe_id)
            if pos is None or not _position_documentee(pos):
                continue
            vus.add(groupe_id)
            interventions.append((groupe_nom, pos.position_majoritaire, pdp.texte))
        arguments = await generer_desaccord(interventions, self._llm)
        if not arguments:
            return False
        questions.desaccord = arguments
        questions.desaccord_objet = ancre.objet
        questions.desaccord_source = SourceOfficielle(
            type="texte",
            libelle="Compte rendu de la séance (Assemblée nationale)",
            url=url_compte_rendu(self._client.legislature, debat.seance_uid),
        )
        return True

    async def _generer_questions(
        self,
        session: AsyncSession,
        dossier: Dossier,
        dossier_ref: str | None,
        votes_texte: list[Scrutin],
        report: SyncReport,
    ) -> None:
        """Renseigne les 4 questions citoyennes du résumé (§2.2).

        Q3 (résultat) est recomposée à chaque run — déterministe, elle suit les
        nouveaux votes. Q1/Q4 (LLM depuis le texte) et Q2 (LLM depuis les débats)
        déjà en base sont réutilisées : on ne rappelle pas le modèle pour rien.

        Exception : une Q4 tirée de l'**exposé** (donc attribuée à l'auteur, sans
        `changement_source`) est **regénérée** dès qu'un dispositif est
        disponible — le fait officiel prime sur la parole du déposant.
        """
        prev = await self._questions_en_base(session, dossier.id)
        peut_mieux_faire = (
            dossier.dispositif is not None
            and prev is not None
            and prev.changement_source is None
        )
        deja_completes = (
            prev is not None
            and prev.pourquoi
            and prev.changement
            and not peut_mieux_faire
        )
        expose = dossier.expose_motifs.texte if dossier.expose_motifs else None
        questions = await generer_questions(
            dossier.titre_officiel,
            dossier.scrutins,
            expose,
            None if deja_completes else self._llm,
            dispositif=dossier.dispositif,
        )
        if questions.pourquoi or questions.changement:
            report.questions_generees += 1
        if questions.changement_source is not None:
            report.changements_factuels += 1

        # Q2 « désaccord » : on la (re)génère si elle n'est pas déjà en base.
        # Les ARGUMENTS déjà validés sont réutilisés tels quels (pas de réappel au
        # modèle), mais leur SENS et leur ancre sont recomposés depuis le scrutin
        # à chaque run — ce sont des faits, pas des sorties de modèle.
        if prev is not None and prev.desaccord:
            ancre = _vote_conclusif(votes_texte)
            arguments = (
                _positions_documentees(prev.desaccord, ancre)
                if ancre is not None
                else []
            )
            if arguments:
                questions.desaccord = arguments
                questions.desaccord_objet = ancre.objet
                questions.desaccord_source = prev.desaccord_source
        elif await self._construire_desaccord(
            dossier, dossier_ref, votes_texte, questions, report
        ):
            report.desaccords_generes += 1

        if prev is not None:
            # Une réponse validée en base ne se perd pas sur un run sans LLM
            # (ou dont la sortie a été rejetée par les contrôles). La source
            # suit sa réponse : les deux se reprennent ensemble ou pas du tout.
            questions.pourquoi = questions.pourquoi or prev.pourquoi
            if not questions.changement:
                questions.changement = prev.changement
                questions.changement_source = prev.changement_source
        dossier.resume.questions = questions

    def _composer_accroche(self, dossier: Dossier) -> None:
        """Pose l'accroche de carte à partir de la Q1 (§2.2, §8).

        Rien n'est généré ici : on réutilise la Q1 déjà validée
        (`_generer_questions`, appelée juste avant) en lui retirant son amorce.
        Pas de Q1 → pas d'accroche, la carte n'affiche rien (§2.5).
        """
        questions = dossier.resume.questions
        dossier.accroche = accroche_depuis_q1(questions.pourquoi if questions else None)

    async def _questions_amendement_en_base(
        self, session: AsyncSession, scrutin_id: str
    ) -> QuestionsAmendement | None:
        """Les questions déjà persistées pour ce vote d'amendement, s'il y en a."""
        row = await session.get(ScrutinRow, scrutin_id)
        if row is None:
            return None
        brut = (row.payload or {}).get("questions")
        return QuestionsAmendement.model_validate(brut) if brut else None

    async def _generer_questions_amendement(
        self, session: AsyncSession, scrutin: Scrutin, report: SyncReport
    ) -> None:
        """Renseigne les questions citoyennes d'un vote d'amendement (§2.2).

        Le résultat (déterministe) est recomposé à chaque run. Les réponses LLM
        (pourquoi ← exposé sommaire, changement ← dispositif) déjà en base sont
        réutilisées — on ne rappelle le modèle que pour ce qui manque ET dont la
        source est disponible (un amendement sans contenu enrichi n'a rien à
        générer, §2.5).
        """
        prev = await self._questions_amendement_en_base(session, scrutin.id)
        deja_completes = prev is not None and (
            (prev.pourquoi or not scrutin.expose_sommaire)
            and (prev.changement or not scrutin.dispositif)
        )
        questions = await generer_questions_amendement(
            scrutin, None if deja_completes else self._llm
        )
        if questions.pourquoi or questions.changement:
            report.questions_amendements_generees += 1
        if prev is not None:
            # Une réponse validée en base ne se perd pas sur un run sans LLM
            # (ou dont la sortie a été rejetée par les contrôles).
            questions.pourquoi = questions.pourquoi or prev.pourquoi
            questions.changement = questions.changement or prev.changement
        scrutin.questions = questions

    async def run(self, limit: int | None = None) -> SyncReport:
        report = SyncReport(started_at=datetime.now(timezone.utc))

        # 1) Référentiels AMO : groupes + annuaire des députés (nominatif).
        organes, acteurs_bruts = await self._client.download_amo()
        resolver = build_resolver_from_organes(organes)
        acteurs = build_acteurs_from_amo(acteurs_bruts)
        self._indexer_groupes(resolver)
        async with self._sf() as session:
            report.groupes = await _upsert_groupes(session, resolver)
            # Annuaire des députés (mandats actifs) : alimente la fiche député
            # (§5.2). Le référentiel est petit (~570 lignes) et se refait à
            # chaque run — un changement de groupe s'y répercute. Les photos
            # officielles sont vérifiées une à une avant d'être attachées
            # (best-effort : sans réseau, on repart sans photo).
            deputes = build_deputes_from_amo(acteurs_bruts, resolver)
            report.portraits = await attacher_portraits(
                deputes, self._client.legislature
            )
            report.deputes = await upsert_deputes(session, deputes)
            await session.commit()
        # Résolution orateur → groupe pour les interventions en discussion générale
        # (le CR n'y porte pas l'abréviation de groupe, cf. debats.py).
        self._groupe_par_acteur = {
            d.id: (d.groupe_id, d.groupe_nom) for d in deputes
        }

        # 1ter) LLM : health-check AVANT le long run. Un serveur configuré mais
        #       injoignable (PC distant éteint…) rendrait chaque appel muet :
        #       autant courir sans LLM et le dire, que semer des trous invisibles.
        if self._llm is not None:
            disponible = getattr(self._llm, "disponible", None)
            if disponible is not None and not await disponible():
                report.llm_indisponible = True
                report.anomalies.append(
                    "LLM configuré mais injoignable : run sans LLM "
                    "(thèmes/questions non générés, regénérés au prochain run)"
                )
                self._llm = None

        #       Débats en séance (comptes rendus) : explications de vote par
        #       groupe, pour le « principal désaccord » (§2.2). Archive lourde
        #       (~55 Mo) et utile seulement au LLM → téléchargée si LLM présent.
        #       Best-effort (§2.5) : un échec de téléchargement (coupure sur ce
        #       gros fichier) ne doit PAS tuer le run — les désaccords déjà en
        #       base sont réutilisés, l'index reste simplement vide ce run-ci.
        if self._llm is not None:
            try:
                xmls = await self._client.download_debats()
                self._index_debats = IndexDebats.depuis_xmls(xmls)
            except (httpx.HTTPError, zipfile.BadZipFile) as exc:
                report.anomalies.append(
                    f"débats non téléchargés ({type(exc).__name__}) : "
                    "désaccords non régénérés ce run (existants préservés)"
                )

        #       Amendements (contenu + exposé sommaire) : archive très lourde
        #       (~300 Mo). Best-effort (§2.5) : un échec de téléchargement ne tue
        #       pas le run — les amendements gardent leur enrichissement déjà en
        #       base (préservé à la fusion), l'index reste simplement vide.
        try:
            self._index_amendements = await self._client.download_amendements()
        except (httpx.HTTPError, zipfile.BadZipFile) as exc:
            report.anomalies.append(
                f"amendements non téléchargés ({type(exc).__name__}) : "
                "contenu non régénéré ce run (existant préservé)"
            )

        # 1bis) Dossiers législatifs : titres officiels + réconciliation des
        #       scrutins sans dossierRef vers leur vrai dossier (§5.1). On
        #       inclut aussi l'archive de la législature PRÉCÉDENTE : un
        #       dossier reporté après une dissolution garde son `dossierRef`
        #       d'origine (vécu : « simplification de la vie économique »,
        #       ref L16, encore voté en L17) — sans ce repli, un tel texte
        #       n'est jamais retrouvé par titre et se fragmente en `TXT-…`.
        #       Best-effort (§2.5) : un échec de téléchargement de l'archive
        #       précédente ne tue pas le run, on reste sur la seule courante.
        documents = await self._client.download_dossiers()
        legislatures = (self._client.legislature,)
        if self._client.legislature > 1:
            try:
                documents += await self._client.download_dossiers(
                    self._client.legislature - 1
                )
                legislatures = (self._client.legislature, self._client.legislature - 1)
            except (httpx.HTTPError, zipfile.BadZipFile) as exc:
                report.anomalies.append(
                    f"dossiers de la législature précédente non téléchargés "
                    f"({type(exc).__name__}) : réconciliation limitée à la "
                    "législature courante ce run"
                )
        reconciliation = construire_reconciliation(documents, legislatures)
        # Index dossierRef → texte AN déposé, pour récupérer l'exposé des motifs
        # (PDF officiel) au niveau du dossier — bloc attribué, option (a).
        index_textes = construire_index_textes(documents, legislatures)
        # Index dossierRef → numéros de documents, pour la liaison certaine
        # débat ↔ dossier (le CR cite « (n° X) »). Les numéros exposés sont ceux
        # de la législature courante — la seule dont on lit les comptes rendus.
        self._numeros_par_ref = construire_index_numeros(
            documents, legislatures, courante=self._client.legislature
        )

        # 2) Scrutins → parsing (avec nominatif) → regroupement par dossier.
        bruts = await self._client.download_scrutins(limit=limit)
        report.scrutins_vus = len(bruts)
        # Le JSON brut reste nécessaire APRÈS le parsing : c'est lui qui porte
        # la ventilation nominative (qui a voté quoi, §5.2), que `ScrutinParse`
        # ne transporte pas. On garde donc la correspondance uid → brut.
        bruts_par_uid: dict[str, dict] = {
            str((b.get("scrutin") or {}).get("uid")): b for b in bruts
        }
        par_dossier: dict[str, list[ScrutinParse]] = {}
        # Les clés de `_groupe_par_acteur` sont exactement les députés du
        # référentiel servi par l'API : ce sont eux, et eux seuls, dont la fiche
        # est atteignable depuis un nom de votant (§5.2).
        deputes_connus = frozenset(self._groupe_par_acteur)
        for brut in bruts:
            try:
                parse = parse_scrutin(
                    brut, resolver, acteurs, reconciliation, deputes_connus
                )
            except (KeyError, TypeError) as exc:
                report.anomalies.append(f"parsing échoué: {exc}")
                continue
            report.anomalies.extend(controles_coherence(parse.scrutin))
            par_dossier.setdefault(parse.dossier_id, []).append(parse)

        # 3) Upsert des dossiers (fusion avec l'existant → badge « mis à jour »)
        #    et du détail de chaque vote (table scrutin). Un COMMIT PAR DOSSIER
        #    (pas un commit unique en fin de run) : un run de plusieurs heures
        #    interrompu (crash, redémarrage, Ctrl-C) ne perd que le dossier en
        #    cours de traitement — tout ce qui est déjà committé (résumés,
        #    questions LLM validées…) survit, au lieu de tout reperdre.
        total = len(par_dossier)
        async with self._sf() as session:
            for i, parses in enumerate(par_dossier.values(), start=1):
                dossier = build_dossier(parses, self._index_amendements or None)
                # Scrutins complets sur le texte (positions par groupe) — pour
                # joindre les explications de vote du débat à la position votée.
                votes_texte = [
                    p.scrutin for p in parses if not est_amendement(p.scrutin.objet)
                ]
                await self._enrichir_texte_depose(
                    session, dossier, parses[0].dossier_ref, index_textes, report
                )
                await self._reclasser_theme(session, dossier, report)
                await self._classifier_publics(session, dossier, report)
                await self._generer_questions(
                    session, dossier, parses[0].dossier_ref, votes_texte, report
                )
                # Après les questions : l'accroche en est tirée.
                self._composer_accroche(dossier)
                dossier = await _upsert_dossier(session, dossier)
                report.amendements_enrichis += sum(
                    1
                    for a in dossier.amendements
                    for am in (a, *a.sous_amendements)
                    if am.dispositif or am.expose_sommaire
                )
                # Le scrutin d'un amendement embarque ses sous-amendements :
                # la fiche vote de l'amendement les liste (dossier fusionné =
                # rattachements connus, runs précédents compris).
                sous_par_scrutin = {
                    a.scrutin_id: a.sous_amendements
                    for a in dossier.amendements
                    if a.scrutin_id and a.sous_amendements
                }
                # Le contenu enrichi (dispositif/exposé/cible) doit aussi vivre
                # sur le scrutin servi par GET /scrutins/{id} : c'est là que la
                # fiche vote d'un amendement (ou sous-amendement, empilé) l'affiche.
                # On le reprend du dossier fusionné (enrichissement préservé).
                enrichi_par_scrutin = {
                    am.id: am
                    for a in dossier.amendements
                    for am in (a, *a.sous_amendements)
                    if am.dispositif or am.expose_sommaire or am.cible
                }
                for p in parses:
                    if p.scrutin.id in sous_par_scrutin:
                        p.scrutin.sous_amendements = sous_par_scrutin[p.scrutin.id]
                    enrichi = enrichi_par_scrutin.get(p.scrutin.id)
                    if enrichi is not None:
                        p.scrutin.cible = enrichi.cible
                        p.scrutin.dispositif = enrichi.dispositif
                        p.scrutin.expose_sommaire = enrichi.expose_sommaire
                    # Questions citoyennes du vote d'amendement (fiche vote) —
                    # après l'enrichissement : elles s'appuient sur le
                    # dispositif / l'exposé sommaire tout juste attachés.
                    if est_amendement(p.scrutin.objet):
                        await self._generer_questions_amendement(
                            session, p.scrutin, report
                        )
                    await _upsert_scrutin(session, p.scrutin)
                    # Votes nominatifs du scrutin (fiche député, §5.2) :
                    # réécrits depuis le JSON brut, dans le même commit que le
                    # scrutin auquel ils se rapportent.
                    brut = bruts_par_uid.get(p.scrutin.id)
                    if brut is not None:
                        report.votes_deputes += await remplacer_votes_du_scrutin(
                            session,
                            p.scrutin.id,
                            p.scrutin.date,
                            votes_du_scrutin(brut),
                        )
                report.dossiers_upserts += 1
                await session.commit()
                if self._on_progress:
                    self._on_progress(i, total, dossier.titre_clair)

        # 3bis) Nettoyage des dossiers orphelins : un dossier dont plus aucun
        #       scrutin ne dépend a été vidé par une migration (ex. un `TXT-`
        #       reconstitué dont tous les votes ont rejoint leur vrai dossier
        #       officiel après amélioration de la réconciliation). On le supprime
        #       pour ne pas laisser un doublon fantôme dans le fil. Sûr : ne
        #       touche jamais un dossier qui a encore des scrutins (§7.7).
        async with self._sf() as session:
            sous_requete = select(ScrutinRow.id).where(
                ScrutinRow.dossier_id == DossierRow.id
            )
            resultat = await session.execute(
                delete(DossierRow).where(~sous_requete.exists())
            )
            report.dossiers_orphelins_supprimes = resultat.rowcount or 0
            await session.commit()

        # 4) Journal.
        report.llm_echecs = getattr(self._llm, "echecs", 0)
        if report.llm_echecs:
            report.anomalies.append(
                f"{report.llm_echecs} appel(s) LLM en échec malgré les retries"
            )
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
