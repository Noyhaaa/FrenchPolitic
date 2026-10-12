"""Enrichissement des amendements votés depuis l'open data AN.

Chaque vote d'amendement du fil ne portait jusqu'ici que l'objet officiel du
scrutin (« l'amendement n° 80 de M. X, adopté ») : ni le **contenu** de
l'amendement (ce qu'il propose de changer), ni son **exposé sommaire** (le
pourquoi, côté auteur). L'archive « Amendements » de l'AN
(`.../loi/amendements_div_legis/Amendements.json.zip`) fournit les deux, par
amendement, sans passer par Légifrance.

Liaison au vote : l'archive est rangée `json/{dossierRef}/{texteRef}/{uid}.json`
et chaque amendement de **séance** (préfixe d'organe « AN ») porte un
`numeroLong` numérique = le numéro cité dans l'objet du vote. On indexe donc par
**(dossierRef, numéro)**. Une même paire peut exister sur deux lectures de la
navette (numéros repartant à 1) → on **désambiguïse par la date** du vote
(fenêtre courte) et, en cas d'ambiguïté persistante, on n'attache rien (§2.5 :
on n'invente pas).

Le **dispositif** (texte de l'amendement) est un extrait officiel factuel ;
l'**exposé sommaire** est le point de vue de l'auteur (non neutre, §4.3) → à
présenter en bloc attribué côté app, jamais fondu dans le résumé neutre — même
traitement que l'exposé des motifs (`textes_an.py`).
"""
from __future__ import annotations

import html as _html
import json
import re
import zipfile
from dataclasses import dataclass
from datetime import date, timedelta

from app.domain.enums import Chambre, ModaliteVote, StatutScrutin
from app.ingestion.assemblee import ScrutinParse
from app.ingestion.dossiers_legislatifs import legislature_du_ref
from app.ingestion.normalize import (
    est_amendement,
    guess_theme,
    numeros_amendements_votes,
)
from app.schemas import ResultatGlobal, Scrutin, SourceOfficielle

AMENDEMENTS_URL = (
    "https://data.assemblee-nationale.fr/static/openData/repository/"
    "{leg}/loi/amendements_div_legis/Amendements.json.zip"
)

# Les numéros de séance repartent à 1 à chaque lecture : deux amendements peuvent
# donc partager (dossierRef, numéro). On les distingue par la date du vote — le
# vote solennel a lieu le jour du sort de l'amendement (ou à un ou deux jours).
_FENETRE_JOURS = 3
# Garde-fous de longueur : le dispositif/exposé peut être long ; on borne pour
# ne pas gonfler le payload (l'app affiche un extrait, la source reste à 1 tap).
_DISPOSITIF_MAX = 2500
_EXPOSE_MAX = 2500

_RE_TAG = re.compile(r"<[^>]+>")
_RE_BLOC = re.compile(r"</p\s*>|<br\s*/?>", re.IGNORECASE)
_RE_ESPACES = re.compile(r"[ \t]+")


def nettoyer_html(brut: object) -> str | None:
    """Convertit le HTML d'un champ d'amendement en texte lisible.

    Les paragraphes (`</p>`, `<br>`) deviennent des sauts de ligne ; les entités
    (`&#160;`, `&#x00C0;`…) sont décodées ; l'espace insécable est normalisé.
    None si vide ou non-texte (l'open data met un dict `{@xsi:nil}` sur l'absent).
    """
    if not isinstance(brut, str) or not brut.strip():
        return None
    texte = _RE_BLOC.sub("\n", brut)
    texte = _RE_TAG.sub("", texte)
    texte = _html.unescape(texte)
    texte = texte.replace("\xa0", " ").replace("’", "'")
    lignes = [_RE_ESPACES.sub(" ", ligne).strip() for ligne in texte.split("\n")]
    texte = "\n".join(ligne for ligne in lignes if ligne).strip()
    return texte or None


def _tronque(texte: str | None, maxi: int) -> str | None:
    if texte is None:
        return None
    if len(texte) <= maxi:
        return texte
    return texte[: maxi - 1].rstrip() + "…"


def _cible_division(division: object) -> str | None:
    """Libellé de l'article/division visé (« Article 2 », « Article unique »).

    Métadonnée factuelle et neutre, tirée de `pointeurFragmentTexte.division`.
    """
    if not isinstance(division, dict):
        return None
    titre = division.get("titre")
    return titre.strip() if isinstance(titre, str) and titre.strip() else None


@dataclass(frozen=True)
class AmendementEnrichi:
    """Contenu d'un amendement, prêt à attacher à son vote."""

    dispositif: str | None       # ce que l'amendement propose (extrait officiel)
    expose_sommaire: str | None  # le pourquoi, côté auteur (non neutre, §4.3)
    cible: str | None            # article/division visé (neutre)
    date_sort: date | None       # pour la désambiguïsation par date


def _jour_de_seance(valeur: object) -> str | None:
    """Le jour de la SÉANCE où l'amendement a été tranché, d'après l'horodatage
    de son sort (« 2026-02-04T00:03:06+01:00 »).

    Une séance de nuit déborde après minuit : un sort tranché à 0 h 03 le 4
    appartient à la séance du 3 — la date que portent les scrutins publics de
    cette séance. Sans ce report, le texte voté à 23 h passait pour « en
    discussion », parce qu'un amendement semblait voté le lendemain. Aucune
    séance ne s'ouvre avant 9 h : tout sort antérieur à 7 h est de la veille.
    """
    if not isinstance(valeur, str) or len(valeur) < 10:
        return None
    try:
        jour = date.fromisoformat(valeur[:10])
    except ValueError:
        return None
    heure = valeur[11:13]
    if heure.isdigit() and int(heure) < 7:
        jour = jour - timedelta(days=1)
    return jour.isoformat()


def _date(valeur: object) -> date | None:
    if not isinstance(valeur, str) or len(valeur) < 10:
        return None
    try:
        return date.fromisoformat(valeur[:10])
    except ValueError:
        return None


IndexAmendements = dict[tuple[str, str], list[AmendementEnrichi]]


@dataclass(frozen=True)
class AmendementSeance:
    """Un amendement de séance mis aux voix, tel que l'archive le décrit.

    Sert aux amendements votés **sans scrutin public** (main levée) : l'archive
    est alors la seule source de leur sort — aucun scrutin ne les mentionne.
    """

    uid: str
    dossier_ref: str
    numero: str
    adopte: bool
    jour: str  # date du sort, ISO « AAAA-MM-JJ »
    # Premier signataire : « Gouvernement », « Député », « Rapporteur »… et sa
    # référence d'acteur (PA…) quand c'est un parlementaire.
    type_auteur: str | None
    acteur_ref: str | None
    # Sous-amendement : uid de l'amendement visé.
    parent_uid: str | None
    # Amendements identiques mis aux voix ENSEMBLE (`discussionIdentique`) :
    # un seul scrutin public les tranche tous, sans citer leurs numéros.
    discussion_identique: str | None
    contenu: AmendementEnrichi


@dataclass(frozen=True)
class ArchiveAmendements:
    """Ce qu'on tire de l'archive en une lecture : l'index de contenu (pour
    enrichir les votes publics) et les amendements de séance tranchés (pour
    ceux votés sans scrutin)."""

    index: IndexAmendements
    seance: list[AmendementSeance]
    # uid → numéro, pour nommer l'amendement visé par un sous-amendement.
    numero_par_uid: dict[str, str]


# Sorts d'un amendement MIS AUX VOIX. « Tombé », « Non soutenu », « Retiré »,
# « Irrecevable » ne sont pas des votes : ils ne produisent rien ici.
_SORTS_VOTES = {"Adopté": True, "Rejeté": False}


def _texte(valeur: object) -> str | None:
    """Champ texte de l'archive (`{@xsi:nil}` pour l'absent)."""
    return valeur.strip() if isinstance(valeur, str) and valeur.strip() else None


def lire_archive(zf: zipfile.ZipFile) -> ArchiveAmendements:
    """Lit l'archive des amendements une fois, en flux.

    Ne retient que les amendements de **séance** (préfixe d'organe « AN »,
    numéro purement numérique). Les amendements de commission (numéros
    préfixés « AE… ») sont ignorés : un vote de commission n'est pas un vote de
    l'Assemblée, et le modèle ne les porte pas.
    """
    index: IndexAmendements = {}
    seance: list[AmendementSeance] = []
    numero_par_uid: dict[str, str] = {}
    for name in zf.namelist():
        if not name.endswith(".json"):
            continue
        parts = name.split("/")
        if len(parts) < 2:
            continue
        dossier_ref = parts[1]
        try:
            with zf.open(name) as f:
                amendement = json.load(f).get("amendement", {})
        except (json.JSONDecodeError, KeyError):
            continue
        identification = amendement.get("identification", {})
        if identification.get("prefixeOrganeExamen") != "AN":
            continue
        numero = identification.get("numeroLong", "")
        if not isinstance(numero, str) or not numero.isdigit():
            continue
        corps = amendement.get("corps", {}).get("contenuAuteur", {})
        pointeur = amendement.get("pointeurFragmentTexte", {})
        cycle = amendement.get("cycleDeVie", {})
        enrichi = AmendementEnrichi(
            dispositif=_tronque(nettoyer_html(corps.get("dispositif")), _DISPOSITIF_MAX),
            expose_sommaire=_tronque(
                nettoyer_html(corps.get("exposeSommaire")), _EXPOSE_MAX
            ),
            cible=_cible_division(pointeur.get("division")),
            date_sort=_date(cycle.get("dateSort")),
        )
        index.setdefault((dossier_ref, numero), []).append(enrichi)
        uid = _texte(amendement.get("uid"))
        if uid is None:
            continue
        numero_par_uid[uid] = numero
        adopte = _SORTS_VOTES.get(_texte(cycle.get("sort")) or "")
        jour = _jour_de_seance(cycle.get("dateSort"))
        if adopte is None or jour is None:
            continue
        auteur = (amendement.get("signataires") or {}).get("auteur") or {}
        identique = amendement.get("discussionIdentique")
        seance.append(
            AmendementSeance(
                uid=uid,
                dossier_ref=dossier_ref,
                numero=numero,
                adopte=adopte,
                jour=jour,
                type_auteur=_texte(auteur.get("typeAuteur")),
                acteur_ref=_texte(auteur.get("acteurRef")),
                parent_uid=_texte(amendement.get("amendementParentRef")),
                discussion_identique=(
                    _texte(identique.get("idDiscussion"))
                    if isinstance(identique, dict)
                    else None
                ),
                contenu=enrichi,
            )
        )
    return ArchiveAmendements(index=index, seance=seance, numero_par_uid=numero_par_uid)


def construire_index(zf: zipfile.ZipFile) -> IndexAmendements:
    """Indexe les amendements de **séance** par (dossierRef, numéro)."""
    return lire_archive(zf).index


def enrichir(
    index: dict[tuple[str, str], list[AmendementEnrichi]],
    dossier_ref: str | None,
    numero: str | None,
    date_vote: date | None,
) -> AmendementEnrichi | None:
    """Retrouve l'amendement de l'archive correspondant au vote.

    Renvoie None (rien à attacher, §2.5) si le dossier n'a pas de référence
    officielle, si le numéro manque, si aucun candidat, ou si plusieurs candidats
    restent indistinguables par la date.
    """
    if not dossier_ref or not dossier_ref.startswith("DLR") or not numero:
        return None
    candidats = index.get((dossier_ref, numero))
    if not candidats:
        return None
    if len(candidats) == 1:
        return candidats[0]
    # Ambiguïté (plusieurs lectures) : le vrai est celui dont le sort tombe le
    # jour du vote (± quelques jours). Sans date exploitable, on n'attache rien.
    if date_vote is None:
        return None
    proches = [
        c
        for c in candidats
        if c.date_sort is not None
        and abs((c.date_sort - date_vote).days) <= _FENETRE_JOURS
    ]
    if len(proches) != 1:
        return None
    return proches[0]


# ---------------------------------------------------------------------------
# Amendements votés SANS scrutin public (§5.2)
# ---------------------------------------------------------------------------

# Le scrutin public d'un amendement et la date de son sort dans l'archive
# peuvent différer d'un jour ou deux (séance levée après minuit) : même
# fenêtre que l'enrichissement des votes publics.
_RE_LEGISLATURE_AMENDEMENT = re.compile(r"^AMANR5L(\d+)")
URL_AMENDEMENT = "https://www.assemblee-nationale.fr/dyn/{leg}/amendements/{uid}"


def amendements_sans_scrutin(
    seance: list[AmendementSeance],
    votes_publics: list[tuple[str, str, str]],
    depuis: str,
) -> list[AmendementSeance]:
    """Les amendements de séance tranchés SANS scrutin public.

    `votes_publics` : les scrutins publics d'amendement de l'Assemblée connus
    (de ce run ET de la base), en (dossier, date, objet). Un amendement est
    couvert quand l'un d'eux porte son numéro, à `_FENETRE_JOURS` près de son
    sort, dans son dossier — ou dans un dossier reconstitué (`TXT-…`), dont on
    ne sait pas s'il est le même texte : dans le doute, on ne déclare pas
    « main levée » un amendement qui a peut-être eu son scrutin (§2.5).

    Des amendements **identiques** sont mis aux voix ensemble : l'objet du
    scrutin n'en cite souvent qu'un (« l'amendement n° 1964 et les amendements
    identiques suivants »). Si l'un d'eux est couvert, tous le sont.
    """
    dans_dossier: dict[tuple[str, str], list[date]] = {}
    hors_archive: dict[str, list[date]] = {}
    for dossier_id, date_vote, objet in votes_publics:
        if not est_amendement(objet):
            continue
        jour = _date(date_vote)
        if jour is None:
            continue
        for numero in numeros_amendements_votes(objet):
            if dossier_id.startswith("DLR"):
                dans_dossier.setdefault((dossier_id, numero), []).append(jour)
            else:
                hors_archive.setdefault(numero, []).append(jour)

    def couvert(a: AmendementSeance) -> bool:
        jour = date.fromisoformat(a.jour)
        jours = dans_dossier.get((a.dossier_ref, a.numero), []) + hors_archive.get(
            a.numero, []
        )
        return any(abs((j - jour).days) <= _FENETRE_JOURS for j in jours)

    groupes_couverts = {
        (a.dossier_ref, a.discussion_identique)
        for a in seance
        if a.discussion_identique and couvert(a)
    }
    return [
        a
        for a in seance
        if a.jour >= depuis
        and not couvert(a)
        and (a.dossier_ref, a.discussion_identique) not in groupes_couverts
    ]


def objet_amendement_seance(
    a: AmendementSeance, numero_parent: str | None, civilites: dict[str, str]
) -> str:
    """L'objet d'un amendement voté sans scrutin, dans les termes qu'emploie
    l'Assemblée pour ses scrutins (« l'amendement n° 80 de M. Girard », « … du
    Gouvernement », « le sous-amendement n° 12 … à l'amendement n° 80 »). Un
    auteur qu'on ne sait pas nommer n'est pas écrit (§2.5)."""
    if a.type_auteur == "Gouvernement":
        auteur = " du Gouvernement"
    elif a.acteur_ref and a.acteur_ref in civilites:
        auteur = f" de {civilites[a.acteur_ref]}"
    else:
        auteur = ""
    if a.parent_uid is None:
        return f"l'amendement n° {a.numero}{auteur}"
    renvoi = f" à l'amendement n° {numero_parent}" if numero_parent else ""
    return f"le sous-amendement n° {a.numero}{auteur}{renvoi}"


def parse_amendement_seance(
    a: AmendementSeance,
    archive: ArchiveAmendements,
    titre_dossier: str,
    civilites: dict[str, str],
) -> ScrutinParse:
    """L'amendement en `ScrutinParse` : un vote sans scrutin public, rangé dans
    le dossier que l'archive lui donne (`json/{dossierRef}/…`) — un fait, pas
    une correspondance de titre.

    Son contenu (dispositif, exposé sommaire, article visé) voyage avec lui :
    il vient du même fichier, il n'y a rien à apparier. `resultat` vaut 0 par
    contrat ; `scrutin_public` faux et `modalite` disent qu'il n'y a pas de
    décompte. La source est la page de l'amendement sur le site de l'Assemblée,
    que l'Assemblée résout elle-même depuis l'identifiant de son archive.
    """
    m = _RE_LEGISLATURE_AMENDEMENT.match(a.uid)
    numero_parent = archive.numero_par_uid.get(a.parent_uid) if a.parent_uid else None
    scrutin = Scrutin(
        id=a.uid,
        dossier_id=a.dossier_ref,
        date=a.jour,
        objet=objet_amendement_seance(a, numero_parent, civilites),
        statut=StatutScrutin.adopte if a.adopte else StatutScrutin.rejete,
        chambre=Chambre.assemblee,
        scrutin_public=False,
        modalite=ModaliteVote.main_levee,
        resultat=ResultatGlobal(pour=0, contre=0, abstention=0, non_votants=0),
        cible=a.contenu.cible,
        dispositif=a.contenu.dispositif,
        expose_sommaire=a.contenu.expose_sommaire,
        sources=(
            [
                SourceOfficielle(
                    type="amendements",
                    libelle="Amendement (Assemblée nationale)",
                    url=URL_AMENDEMENT.format(leg=m.group(1), uid=a.uid),
                )
            ]
            if m
            else []
        ),
    )
    return ScrutinParse(
        scrutin=scrutin,
        dossier_id=a.dossier_ref,
        dossier_titre=titre_dossier,
        dossier_ref=a.dossier_ref,
        theme=guess_theme(titre_dossier),
        legislature=legislature_du_ref(a.dossier_ref) or "",
        numero="",
        ref_du_scrutin=True,
        parent_id=a.parent_uid,
    )
