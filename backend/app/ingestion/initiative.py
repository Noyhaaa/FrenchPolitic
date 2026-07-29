"""Qui porte le texte — l'initiative d'un dossier (§5.1).

L'app disait *ce qui a été voté* et *comment chaque groupe a voté*, jamais **d'où
vient le texte**. Un projet de loi du Gouvernement et une proposition déposée par
une députée de l'opposition s'affichaient à l'identique. C'est pourtant un fait
officiel, écrit dans l'archive « dossiers législatifs » déjà téléchargée à chaque
run : chaque `document` porte ses `auteurs`.

On lit l'auteur sur le **document de dépôt initial** du dossier (le plus petit
numéro de distribution), le même que celui d'où sortent l'exposé des motifs et le
dispositif (`textes_an.construire_index_textes`).

Trois origines, et rien d'autre :

- **Gouvernement** — dès que le texte est un *projet* de loi. C'est la définition
  constitutionnelle (art. 39 : un projet émane du Gouvernement, une proposition
  d'un parlementaire), déjà le raisonnement de `normalize.deposant`. On ne nomme
  **pas** le ministre déposant : sa qualité ministérielle n'est documentée dans
  aucune de nos sources, et 7 dossiers sur 48 seulement seraient nommables — une
  attribution qui ne marche qu'une fois sur sept vaut moins que « Gouvernement »,
  exact partout.
- **Parlementaire** — un auteur `qualite="auteur"` et un seul. Plusieurs auteurs
  → on garde l'origine mais **on ne nomme personne** : désigner le premier de la
  liste serait choisir à la place de la source (§2.5, même règle que
  `normalize.auteur_amendement`). Mesuré sur les dossiers votés : 140 sur 143
  n'ont qu'un auteur, la prudence ne coûte presque rien.
- **Sénat** — le texte a été déposé au Sénat puis transmis à l'Assemblée. L'AN
  n'enregistre alors aucune personne : l'auteur est l'organe `PO838901`, et le
  dépôt est classé « Initiative en Navette ». Mesuré : 69 dossiers, tous avec ce
  même couple. La personne existe, mais elle est dans les archives du Sénat, pas
  ici — on dit donc « transmis par le Sénat » et rien de plus.

⚠️ Les entrées `qualite="rapporteur"` figurent dans la **même liste** que les
auteurs : ce sont les rapporteurs du texte, jamais ses auteurs.

Module **pur** : il ne résout pas l'`acteurRef` en nom. C'est `sync` qui le fait,
avec l'annuaire AMO, exactement comme pour les votants nominatifs — et qui
n'attache l'identifiant de fiche que si le parlementaire siège encore.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, NamedTuple

from app.ingestion.dossiers_legislatifs import _DENOMINATIONS_TEXTE
from app.ingestion.normalize import as_list
from app.ingestion.textes_an import _numero_uid
from app.schemas import Initiative

OrigineInitiative = Literal["gouvernement", "parlementaire", "senat"]

# Organe auteur des textes déposés au Sénat puis transmis à l'Assemblée.
# Relevé sur l'archive : 69 dossiers, 69 fois le même organe, tous classés
# « Initiative en Navette ». On exige les DEUX indices — un organe seul dans un
# dépôt initial ne serait pas la même chose.
_ORGANE_SENAT = "PO838901"
_DEPOT_NAVETTE = "INITNAV"

# Textes de l'Assemblée dont le dépôt est enregistré ici (propositions de loi,
# projets de loi, propositions de résolution). Même filtre que l'index des
# textes déposés — les rapports et avis ne portent pas l'initiative du texte.
_PREFIXES_UID = ("PIONAN", "PRJLAN", "PNREAN")


class IdentiteAuteur(NamedTuple):
    """Ce que le référentiel des parlementaires sait d'un auteur.

    `portrait_url` vient du référentiel tel quel — côté Assemblée il n'y est
    posé qu'après vérification, côté Sénat il est donné par l'annuaire. On ne
    dérive donc aucune URL de photo ici : absente, l'app affiche les initiales.
    """

    nom: str
    groupe_nom: str
    groupe_couleur: str
    portrait_url: str | None = None


@dataclass(frozen=True)
class InitiativeBrute:
    """Initiative d'un texte, avant résolution de l'acteur en nom.

    `acteur_ref` n'est renseigné que pour l'origine « parlementaire », et
    seulement quand la source ne désigne **qu'un** auteur.
    """

    origine: OrigineInitiative
    acteur_ref: str | None = None


def _auteurs(document: dict) -> list[dict]:
    """Entrées de `auteurs.auteur` — la source sérialise un auteur unique en
    objet et plusieurs en liste."""
    return as_list((document.get("auteurs") or {}).get("auteur"))


def _refs_auteurs(entrees: list[dict]) -> list[str]:
    """`acteurRef` des seules entrées de qualité « auteur » (pas rapporteur)."""
    refs: list[str] = []
    for entree in entrees:
        acteur = entree.get("acteur") if isinstance(entree, dict) else None
        if not isinstance(acteur, dict):
            continue
        if (acteur.get("qualite") or "").strip().lower() != "auteur":
            continue
        ref = (acteur.get("acteurRef") or "").strip()
        if ref:
            refs.append(ref)
    return refs


def _organes(entrees: list[dict]) -> list[str]:
    refs: list[str] = []
    for entree in entrees:
        organe = entree.get("organe") if isinstance(entree, dict) else None
        if isinstance(organe, dict):
            ref = (organe.get("organeRef") or "").strip()
            if ref:
                refs.append(ref)
    return refs


def _code_depot(document: dict) -> str:
    famille = (document.get("classification") or {}).get("famille") or {}
    return ((famille.get("depot") or {}).get("code") or "").strip().upper()


def initiative_du_document(document: dict) -> InitiativeBrute | None:
    """Initiative portée par un document de dépôt, sinon None (§2.5).

    Pure et testable : l'ordre des règles est celui du module.
    """
    if (document.get("denominationStructurelle") or "") == "Projet de loi":
        # Art. 39 : le déposant nommé est le ministre porteur, l'initiative est
        # celle du Gouvernement. On ne descend pas au ministre (cf. docstring).
        return InitiativeBrute(origine="gouvernement")

    entrees = _auteurs(document)
    refs = _refs_auteurs(entrees)
    if refs:
        # Plusieurs auteurs : l'origine reste vraie, le nom devient indécidable.
        return InitiativeBrute(
            origine="parlementaire",
            acteur_ref=refs[0] if len(set(refs)) == 1 else None,
        )

    if _ORGANE_SENAT in _organes(entrees) and _code_depot(document) == _DEPOT_NAVETTE:
        return InitiativeBrute(origine="senat")

    return None


def construire_index_initiatives(
    documents: list[dict], legislatures: tuple[int, ...]
) -> dict[str, InitiativeBrute]:
    """Table `dossierRef → initiative`, lue sur le **dépôt initial** du dossier.

    Mêmes filtres que `textes_an.construire_index_textes` (textes AN, provenance
    « Texte Déposé », dénominations de texte de loi), à une exception près : on
    n'exige pas que l'URL du PDF soit dérivable de l'uid. Il en faut une pour
    aller lire l'exposé des motifs, pas pour lire un auteur — l'imposer ici
    perdrait des dossiers sans raison.

    `legislatures` couvre typiquement la courante + la précédente : un dossier
    reporté après une dissolution garde son `dossierRef` d'origine.

    ⚠️ On retient le dépôt initial **puis** on lit son initiative — jamais le
    premier document qui *aurait* une initiative lisible. Les documents suivants
    d'une navette portent d'autres auteurs (un texte renvoyé par le Sénat après
    une première lecture à l'Assemblée y est signé du Sénat) : s'y rabattre
    ferait passer un texte né à l'Assemblée pour un texte sénatorial.
    """
    prefixes = tuple(f"DLR5L{leg}" for leg in legislatures)
    # dossierRef -> (numéro de distribution, document) du dépôt le plus ancien.
    depot_initial: dict[str, tuple[int, dict]] = {}

    for brut in documents:
        doc = brut.get("document") or brut
        ref = doc.get("dossierRef") or ""
        uid = doc.get("uid") or ""
        if not ref.startswith(prefixes) or not uid.startswith(_PREFIXES_UID):
            continue
        if (doc.get("denominationStructurelle") or "") not in _DENOMINATIONS_TEXTE:
            continue
        if (doc.get("provenance") or "") != "Texte Déposé":
            continue
        numero = _numero_uid(uid)
        connu = depot_initial.get(ref)
        if connu is None or numero < connu[0]:
            depot_initial[ref] = (numero, doc)

    index: dict[str, InitiativeBrute] = {}
    for ref, (_, doc) in depot_initial.items():
        initiative = initiative_du_document(doc)
        if initiative is not None:
            index[ref] = initiative
    return index


def resoudre_initiative(
    brute: InitiativeBrute | None,
    identites: dict[str, IdentiteAuteur],
) -> Initiative | None:
    """Complète une initiative brute avec l'identité de son auteur.

    `identites` va de l'`acteurRef` à ce que le référentiel sait de lui, et ses
    clés sont **exactement** celles du référentiel servi par l'API : un auteur
    qui n'y est plus (mandat terminé) garde son origine mais perd son nom. On
    n'affiche jamais une référence machine « PA… » en guise de nom (§2.5), et
    `depute_id` n'est posé que là où la fiche existe — un lien ne doit jamais
    mener à un 404.

    ⚠️ Le groupe est celui du député **aujourd'hui**, pas celui qu'il avait au
    dépôt : l'archive AMO ne publie que les mandats actifs, un groupe quitté n'y
    figure plus. C'est le même compromis que partout ailleurs dans l'app, où le
    nom d'un votant d'un scrutin ancien ouvre sa fiche actuelle.
    """
    if brute is None:
        return None
    identite = identites.get(brute.acteur_ref or "")
    if identite is None:
        return Initiative(origine=brute.origine)
    return Initiative(
        origine=brute.origine,
        nom=identite.nom,
        depute_id=brute.acteur_ref,
        groupe_nom=identite.groupe_nom,
        groupe_couleur=identite.groupe_couleur,
        portrait_url=identite.portrait_url,
    )
