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
from datetime import date

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


def _date(valeur: object) -> date | None:
    if not isinstance(valeur, str) or len(valeur) < 10:
        return None
    try:
        return date.fromisoformat(valeur[:10])
    except ValueError:
        return None


def construire_index(
    zf: zipfile.ZipFile,
) -> dict[tuple[str, str], list[AmendementEnrichi]]:
    """Indexe les amendements de **séance** par (dossierRef, numéro).

    Ne retient que les amendements de séance (préfixe d'organe « AN », numéro
    purement numérique) : ce sont ceux mis aux voix en public, donc ceux que le
    fil référence. Les amendements de commission (numéros préfixés « AE… ») sont
    ignorés — ils ne portent pas de scrutin public dans le modèle.
    """
    index: dict[tuple[str, str], list[AmendementEnrichi]] = {}
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
    return index


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
