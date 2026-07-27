"""Recherche de dossiers : index, découpage en termes et pertinence (§3.3).

Trois fonctions **pures**, partagées par les deux repositories (`memory` et
`postgres`) : c'est ce qui garantit que les tests — qui tournent sur le backend
`memory` — prouvent quelque chose du comportement servi en production.

Pourquoi pas `tsvector` : à l'échelle du corpus (quelques centaines de
dossiers), un préfiltre `LIKE` suivi d'un score explicite en Python est plus
simple à lire, testable comme fonction pure, et identique dans les deux
backends. Le jour où le corpus change d'ordre de grandeur, seul le préfiltre est
à remplacer — `score` reste.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.schemas import Dossier
from app.utils.text import fold

# En dessous, un terme ne discrimine plus rien (« de », « la », « à ») et
# ramènerait la moitié du corpus.
_LONGUEUR_MIN_TERME = 2

# Pertinence : le champ d'où vient la correspondance prime sur le nombre de
# correspondances. Un mot trouvé dans la réponse « pourquoi ont-ils débattu ? »
# ne doit jamais passer devant un texte dont c'est le titre.
SCORE_TITRE_EXACT = 4  # la requête entière, en toutes lettres, dans un titre
SCORE_TITRE = 3  # tous les termes dans les titres
SCORE_ACCROCHE = 2  # tous les termes dans l'accroche ou le thème
SCORE_AUTRE = 1  # ailleurs dans l'index (Q1, Q4, publics concernés)


def termes(requete: str) -> list[str]:
    """Termes exploitables d'une requête, pliés (minuscule, sans accents).

    Découpe sur les blancs ; les termes trop courts sont écartés. Liste vide
    pour une requête vide ou uniquement faite de bruit — l'appelant retombe
    alors sur le fil récent.
    """
    return [
        t for t in fold(requete).split() if len(t) >= _LONGUEUR_MIN_TERME
    ]


def index_recherche(dossier: Dossier) -> str:
    """Le texte indexé d'un dossier — **source unique** de `search_index`.

    Au-delà des titres, on indexe ce qui est écrit en **langue simple et déjà
    validé** : les réponses Q1 (« pourquoi ») et Q4 (« ce que ça change ») et
    les publics concernés. C'est là que vit le vocabulaire du lecteur
    (« logement », « hôpital »), absent des titres officiels (« habitat »,
    « loi de finances ») — mesuré : 7 requêtes réalistes sur 17 sans aucun
    résultat avant, 2 après.

    ⚠️ L'**exposé des motifs** est délibérément exclu : long et argumentatif, il
    fait exploser le bruit (« fin de vie » y ramenait 120 des 291 dossiers, les
    mots « fin » et « vie » s'y croisant partout).
    """
    resume = dossier.resume
    questions = resume.questions
    morceaux = [
        dossier.titre_clair,
        dossier.titre_officiel,
        dossier.accroche or "",
        dossier.theme,
        (questions.pourquoi or "") if questions else "",
        (questions.changement or "") if questions else "",
        " ".join(resume.public_concerne or []),
    ]
    return fold(" ".join(m for m in morceaux if m))


@dataclass(frozen=True)
class ChampsRecherche:
    """Les champs sur lesquels se calcule la pertinence.

    Tous disponibles en **colonnes** côté Postgres (`DossierRow`) comme sur le
    `Dossier` en mémoire : marquer un résultat n'oblige jamais à ouvrir le
    payload.
    """

    titre_clair: str
    titre_officiel: str
    accroche: str | None
    theme: str
    index: str


def score(champs: ChampsRecherche, mots: list[str], requete: str = "") -> int:
    """Pertinence d'un dossier pour une requête. 0 = non pertinent.

    `requete` sert au seul bonus de phrase exacte ; le reste ne dépend que des
    termes. À score égal, l'appelant départage par date décroissante — le tri
    d'origine reste donc le comportement par défaut.
    """
    if not mots:
        return 0
    if not all(m in champs.index for m in mots):
        return 0
    titres = fold(f"{champs.titre_clair} {champs.titre_officiel}")
    phrase = fold(requete).strip()
    if phrase and phrase in titres:
        return SCORE_TITRE_EXACT
    if all(m in titres for m in mots):
        return SCORE_TITRE
    accroche = fold(f"{champs.accroche or ''} {champs.theme}")
    if all(m in accroche for m in mots):
        return SCORE_ACCROCHE
    return SCORE_AUTRE
