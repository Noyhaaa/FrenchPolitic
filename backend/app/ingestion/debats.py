"""Comptes rendus des débats en séance (« SyceronBrut ») → explications de vote.

Objectif : alimenter le « principal désaccord » d'un dossier (Q2 des questions
citoyennes) à partir de la section **Explications de vote** de la séance, où
**chaque groupe explique lui-même** pourquoi il vote pour ou contre. On n'en tire
JAMAIS une synthèse éditoriale : chaque prise de parole reste **attribuée à son
groupe** (§7.4), et le sens du vote (pour/contre) vient du **scrutin**, pas du
débat (donc jamais du LLM).

Liaison au dossier : le compte rendu ne porte aucune référence machine de
dossier, mais le titre de discussion porte le **numéro du texte** (« (n[[o]]
525) ») — le même numéro que les documents de l'archive dossiers législatifs.
La liaison se fait donc par **numéro de texte** (certaine, y compris quand le
vote solennel a lieu quelques jours après le débat), avec repli sur **date de
séance + recoupement du titre**. Un même jour peut voir plusieurs textes votés
et l'archive ne capture pas toutes les séances : un candidat unique le jour J
ne suffit JAMAIS sans recoupement (§2.5 : jamais de rattachement douteux —
constaté en réel : des explications sur le don du sang reliées à un texte sur
le vote des détenus).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date as _date, timedelta
from xml.etree import ElementTree as ET

from app.utils.text import fold

_NS = "{http://schemas.assemblee-nationale.fr/referentiel}"


def _tag(e: ET.Element) -> str:
    return e.tag.split("}")[-1]


# Groupe politique entre parenthèses en fin de nom : « M. Yoann Gillet (RN) ».
_RE_GROUPE = re.compile(r"\(([^()]+)\)\s*$")

# Longueur minimale d'une explication de vote exploitable (sous ce seuil, c'est
# une interjection, pas un argument).
_MIN_LONGUEUR = 40
# Longueur d'explication conservée pour le prompt LLM (au-delà, on tronque : la
# position tient dans les premières phrases).
_MAX_LONGUEUR = 1200

_MOIS = {
    m: i
    for i, m in enumerate(
        [
            "janvier", "fevrier", "mars", "avril", "mai", "juin",
            "juillet", "aout", "septembre", "octobre", "novembre", "decembre",
        ],
        start=1,
    )
}
_RE_DATE = re.compile(r"(\d{1,2})\s+([a-z]+)\s+(\d{4})")

# Mots vides ignorés dans le recoupement de titre (structure juridique commune).
_STOP = frozenset(
    "de la le les des du un une et a l en pour sur au aux d proposition loi projet "
    "resolution visant relative relatif relatifs portant ensemble texte commission "
    "premiere deuxieme lecture nouvelle organique apres engagement procedure "
    "acceleree adoptee par senat".split()
)


def _date_iso(jour_txt: str) -> str | None:
    """« mercredi 06 novembre 2024 » → « 2024-11-06 ». None si non datable."""
    m = _RE_DATE.search(fold(jour_txt))
    if not m:
        return None
    jour, mois, annee = m.groups()
    num = _MOIS.get(mois)
    return f"{annee}-{num:02d}-{int(jour):02d}" if num else None


def _tokens(titre: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]+", fold(titre)) if w not in _STOP and len(w) > 2}


@dataclass(frozen=True)
class ExplicationVote:
    """Une explication de vote : le groupe et le texte prononcé (mots exacts)."""

    groupe: str  # abréviation telle qu'écrite au CR (« RN », « LFI-NFP »…)
    orateur: str
    texte: str


@dataclass(frozen=True)
class DebatTexte:
    """Les explications de vote d'un texte discuté lors d'une séance."""

    titre: str
    date: str | None  # ISO (jour de séance)
    seance_uid: str
    # Numéro(s) du texte discuté, portés par l'attribut `valeur` du titre de
    # discussion (« (n[[o]] 525) », parfois plusieurs : « n[[os]] 1681, 1682 »).
    numeros: frozenset[int] = frozenset()
    explications: list[ExplicationVote] = field(default_factory=list)

    @property
    def tokens_titre(self) -> set[str]:
        return _tokens(self.titre)


def _titre_point(point: ET.Element) -> str:
    for sub in point.iter():
        if _tag(sub) == "texte" and (sub.text or "").strip():
            return sub.text.strip()
    return ""


def _numeros_point(point: ET.Element) -> frozenset[int]:
    """Numéro(s) de texte de l'attribut `valeur` : « (n[[o]] 525) »,
    « (n[[os]] 1681 rectifié, 1682) »… Vide si l'attribut n'en porte pas."""
    return frozenset(int(n) for n in re.findall(r"\d+", point.attrib.get("valeur", "")))


# La section des explications de vote connaît des variantes de titre au CR :
# « Explications de vote », « Explication de vote », « Explications de vote
# communes » (recensées dans l'archive 17e législature).
def _est_section_explications(titre: str) -> bool:
    f = fold(titre)
    return f.startswith("explication") and "vote" in f


def extraire_debats(xml: str) -> list[DebatTexte]:
    """Extrait, pour un compte rendu, les textes discutés et leurs explications
    de vote par groupe.

    On parcourt la séance en ordre de lecture : chaque `TITRE_TEXTE_DISCUSSION`
    ouvre un texte ; la sous-section « Explications de vote » capture les prises
    de parole de groupe jusqu'au vote (VOTE_…) ou au texte suivant. On ignore les
    interruptions/rappels au règlement (seul `PAROLE_GENERIQUE`) et les prises de
    parole sans groupe identifiable (présidence, gouvernement)."""
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return []
    date = _date_iso(root.findtext(f".//{_NS}dateSeanceJour") or "")
    uid = (root.findtext(f"{_NS}uid") or "").strip()

    textes: list[DebatTexte] = []
    courant: DebatTexte | None = None
    dans_explications = False

    for e in root.iter():
        t = _tag(e)
        if t == "point":
            cg = e.attrib.get("code_grammaire", "")
            titre = _titre_point(e)
            if cg == "TITRE_TEXTE_DISCUSSION":
                courant = DebatTexte(
                    titre=titre,
                    date=date,
                    seance_uid=uid,
                    numeros=_numeros_point(e),
                )
                textes.append(courant)
                dans_explications = False
            elif _est_section_explications(titre):
                dans_explications = True
            elif cg.startswith(("VOTE_", "APPEL_", "SCRUTIN")):
                dans_explications = False
        elif t == "paragraphe" and dans_explications and courant is not None:
            if e.attrib.get("code_grammaire", "") != "PAROLE_GENERIQUE":
                continue
            orateur_el = e.find(f"{_NS}orateurs/{_NS}orateur")
            if orateur_el is None:
                continue
            nom = (orateur_el.findtext(f"{_NS}nom") or "").strip()
            m = _RE_GROUPE.search(nom)
            if not m:  # présidence, ministre : pas de groupe → ignoré
                continue
            texte = (e.findtext(f"{_NS}texte") or "").strip()
            if len(texte) < _MIN_LONGUEUR:
                continue
            courant.explications.append(
                ExplicationVote(
                    groupe=m.group(1).strip(),
                    orateur=re.sub(r"\s*\([^()]+\)\s*$", "", nom).strip(),
                    texte=texte[:_MAX_LONGUEUR],
                )
            )
    # On ne garde que les textes qui ont réellement des explications de vote.
    return [t for t in textes if t.explications]


# Recoupement de titre minimal (coefficient de recouvrement, adapté aux labels
# courts du CR face aux objets longs des scrutins) et écart au 2e candidat :
# au-dessus, la correspondance est sûre ; sinon on s'abstient (§2.5).
_SEUIL_TITRE = 0.50
_ECART_MIN = 0.15
# Le vote solennel peut avoir lieu quelques jours après le débat : fenêtre de
# recherche par numéro de texte (le débat précède toujours le vote).
_FENETRE_JOURS = 14


def _recouvrement(cible: set[str], titre: set[str]) -> float:
    """Coefficient de recouvrement : |∩| / min(|A|, |B|). Contrairement à
    Jaccard, un label court du CR entièrement contenu dans l'objet long d'un
    scrutin (« Lutte contre les déserts médicaux » ⊂ « l'ensemble de la
    proposition de loi visant à lutter contre… ») score haut."""
    if not cible or not titre:
        return 0.0
    return len(cible & titre) / min(len(cible), len(titre))


class IndexDebats:
    """Index des explications de vote, interrogeable par (date, titre, numéros).

    Construit une fois par run à partir de tous les comptes rendus, puis
    interrogé dossier par dossier avec la date et l'objet du vote sur
    l'ensemble, et les numéros de texte connus du dossier (archive dossiers
    législatifs) quand le dossier est officiel.
    """

    def __init__(self, debats: list[DebatTexte]) -> None:
        self._par_date: dict[str, list[DebatTexte]] = {}
        for d in debats:
            if d.date:
                self._par_date.setdefault(d.date, []).append(d)

    @classmethod
    def depuis_xmls(cls, xmls: list[str]) -> "IndexDebats":
        debats: list[DebatTexte] = []
        for xml in xmls:
            debats.extend(extraire_debats(xml))
        return cls(debats)

    def _fenetre(self, date_vote: str) -> list[DebatTexte]:
        """Les débats de la fenêtre [date_vote − N jours, date_vote], du plus
        récent au plus ancien (le débat précède toujours le vote)."""
        try:
            fin = _date.fromisoformat((date_vote or "")[:10])
        except ValueError:
            return []
        jours = [
            (fin - timedelta(days=i)).isoformat() for i in range(_FENETRE_JOURS + 1)
        ]
        return [d for j in jours for d in self._par_date.get(j, [])]

    def pour_vote(
        self, date: str, objet: str, numeros: set[int] | None = None
    ) -> DebatTexte | None:
        """Le débat correspondant à un vote sur l'ensemble. None si aucune
        correspondance sûre (§2.5 : on ne devine pas).

        1. **Numéro de texte** (certain) : un débat de la fenêtre dont le
           numéro appartient aux documents du dossier — y compris quand le
           vote solennel a lieu après la séance de débat.
        2. **Repli titre** : même jour uniquement, recoupement de titre
           suffisant et non ambigu. Un candidat unique le jour J ne suffit
           pas : plusieurs textes peuvent être votés le même jour.
        """
        if numeros:
            trouves = [d for d in self._fenetre(date) if d.numeros & numeros]
            if trouves:
                # Le plus proche du vote ; ambigu si plusieurs le même jour.
                premier = trouves[0]
                memes_jour = [d for d in trouves if d.date == premier.date]
                return premier if len(memes_jour) == 1 else None
        candidats = self._par_date.get((date or "")[:10])
        if not candidats:
            return None
        cible = _tokens(objet)
        if not cible:
            return None
        scores = sorted(
            (
                (_recouvrement(cible, d.tokens_titre), d)
                for d in candidats
                if d.tokens_titre
            ),
            key=lambda x: x[0],
            reverse=True,
        )
        if not scores:
            return None
        meilleur, debat = scores[0]
        second = scores[1][0] if len(scores) > 1 else 0.0
        if meilleur >= _SEUIL_TITRE and meilleur - second >= _ECART_MIN:
            return debat
        return None  # ambigu : on ne devine pas (§2.5)


def url_compte_rendu(legislature: int, seance_uid: str) -> str:
    """URL publique du compte rendu de séance (réversibilité §7.5)."""
    return (
        f"https://www.assemblee-nationale.fr/dyn/{legislature}"
        f"/comptes-rendus/seance/{seance_uid}"
    )
