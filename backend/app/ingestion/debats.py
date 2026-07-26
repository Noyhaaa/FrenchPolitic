"""Comptes rendus des débats en séance (« SyceronBrut ») → explications de vote.

Objectif : alimenter le « principal désaccord » d'un dossier (Q2 des questions
citoyennes) à partir de la section **Explications de vote** de la séance, où
**chaque groupe explique lui-même** pourquoi il vote pour ou contre. On n'en tire
JAMAIS une synthèse éditoriale : chaque prise de parole reste **attribuée à son
groupe** (§7.4), et le sens du vote (pour/contre) vient du **scrutin**, pas du
débat (donc jamais du LLM).

Tous les débats n'ont pas de section « Explications de vote » : on retombe alors
sur la **discussion générale**, puis en dernier ressort sur les débats sans
section dédiée — motion de rejet préalable (`MOTION_RP_1_1`) et prises de parole
placées directement sous le titre de discussion (motion de censure, déclaration
au titre de l'article 50-1). Voir `_VIVIERS`.

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
    """Une prise de parole de groupe : le groupe et le texte prononcé (mots exacts).

    Deux origines, résolues différemment vers un groupe côté ingestion :
    - explication de vote formelle : `groupe` = abréviation écrite au CR (« RN »,
      « LFI-NFP »…), `acteur_ref` = None ;
    - intervention en discussion générale : le CR n'y met PAS l'abréviation de
      groupe dans le nom → `groupe` = "", `acteur_ref` = « PA… » (l'orateur, résolu
      en groupe via l'annuaire des députés).
    """

    groupe: str  # abréviation telle qu'écrite au CR (« RN », « LFI-NFP »…), ou ""
    orateur: str
    texte: str
    acteur_ref: str | None = None


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
    # Prises de parole des groupes en discussion générale — source de REPLI pour
    # le désaccord quand le texte n'a pas d'explications de vote formelles.
    interventions_generales: list[ExplicationVote] = field(default_factory=list)

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


# Les trois viviers de prises de position, par ordre de préférence décroissant.
# `_REPLI` couvre deux formats de séance où le CR n'ouvre NI section
# « Explications de vote » NI `DISC_GENERALE_1` : la motion de rejet préalable
# (section `MOTION_RP_1_1`) et le débat placé directement sous le titre de
# discussion — motion de censure, déclaration au titre de l'article 50-1.
_EXPLICATIONS = "explications"
_DISCUSSION = "discussion"
_REPLI = "repli"
_VIVIERS = (_EXPLICATIONS, _DISCUSSION, _REPLI)


def _orateur(nom: str) -> str:
    """« M. Yoann Gillet (RN) » → « M. Yoann Gillet »."""
    return re.sub(r"\s*\([^()]+\)\s*$", "", nom).strip()


# La présidence de séance est nommée par sa fonction (« Mme la présidente ») et
# porte un identifiant d'acteur, car elle est elle-même députée : sans ce filtre,
# ses annonces d'ordre du jour (« La parole est à M. X. ») seraient attribuées à
# son groupe comme une prise de position (§7.4). Les ministres, eux, sont écartés
# plus loin : nommés sans fonction, ils sont absents de l'annuaire des députés
# (mandat suspendu) et leur `acteur_ref` ne se résout donc en aucun groupe.
_RE_PRESIDENCE = re.compile(r"^(?:m\.|mme)\s+l[ae]\s+president", re.I)


# Une prise de parole en cours de constitution : [nom brut, morceaux, acteurRef].
_Prise = list


def _explications_de_vote(prises: list[_Prise]) -> list[ExplicationVote]:
    """Explications de vote formelles : le groupe est écrit dans le nom
    (« M. Yoann Gillet (RN) »). Sans groupe (présidence, ministre) → ignoré."""
    out: list[ExplicationVote] = []
    for nom, morceaux, _ref in prises:
        texte = " ".join(morceaux)
        m = _RE_GROUPE.search(nom)
        if not m or len(texte) < _MIN_LONGUEUR:
            continue
        out.append(
            ExplicationVote(
                groupe=m.group(1).strip(),
                orateur=_orateur(nom),
                texte=texte[:_MAX_LONGUEUR],
            )
        )
    return out


def _interventions(prises: list[_Prise]) -> list[ExplicationVote]:
    """Prises de parole hors explications de vote : le CR n'y écrit PAS
    l'abréviation de groupe, on garde donc l'identifiant d'acteur (résolu en
    groupe via l'annuaire des députés, côté ingestion).

    Un orateur qui reprend la parole plus tard dans la séance n'est compté
    qu'une fois : un seul argument par groupe (§7.4)."""
    out: list[ExplicationVote] = []
    vus: set[str] = set()
    for nom, morceaux, ref in prises:
        texte = " ".join(morceaux)
        if not ref or len(texte) < _MIN_LONGUEUR:
            continue
        if _RE_PRESIDENCE.match(fold(nom)):
            continue
        acteur_ref = ref if ref.startswith("PA") else f"PA{ref}"
        if acteur_ref in vus:
            continue
        vus.add(acteur_ref)
        out.append(
            ExplicationVote(
                groupe="",
                orateur=_orateur(nom),
                texte=texte[:_MAX_LONGUEUR],
                acteur_ref=acteur_ref,
            )
        )
    return out


def extraire_debats(xml: str) -> list[DebatTexte]:
    """Extrait, pour un compte rendu, les textes discutés et les prises de
    position de groupe qui les accompagnent.

    On parcourt la séance en ordre de lecture : chaque `TITRE_TEXTE_DISCUSSION`
    ouvre un texte, et chaque parole tombe dans le vivier de la section courante
    (cf. `_VIVIERS`). Les explications de vote formelles priment ; à défaut la
    discussion générale ; à défaut seulement le vivier de repli. On ignore les
    interruptions et rappels au règlement (seul `PAROLE_GENERIQUE` compte) et les
    prises de parole sans locuteur identifiable.

    Les morceaux **consécutifs** d'un même orateur sont recollés : une prise de
    parole hachée par les interruptions ne doit pas être réduite à son premier
    fragment (mesuré : longueur médiane 350 → 552 caractères)."""
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return []
    date = _date_iso(root.findtext(f".//{_NS}dateSeanceJour") or "")
    uid = (root.findtext(f"{_NS}uid") or "").strip()

    textes: list[DebatTexte] = []
    courant: DebatTexte | None = None
    section: str | None = None
    prises: dict[int, dict[str, list[_Prise]]] = {}

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
                prises[id(courant)] = {v: [] for v in _VIVIERS}
                # Les paroles qui suivent immédiatement le titre, avant toute
                # sous-section, sont celles d'un débat sans section dédiée.
                section = _REPLI
            elif courant is None:
                continue
            elif cg == "DISC_GENERALE_1":
                section = _DISCUSSION
            elif _est_section_explications(titre):
                section = _EXPLICATIONS
            elif cg == "MOTION_RP_1_1":
                section = _REPLI
            elif section != _EXPLICATIONS or cg.startswith(
                ("VOTE_", "APPEL_", "SCRUTIN")
            ):
                # Tout autre point (discussion des articles…) ferme le vivier
                # courant ; les explications de vote, elles, se poursuivent à
                # travers leurs sous-points jusqu'au vote.
                section = None
        elif t == "paragraphe" and courant is not None and section:
            if e.attrib.get("code_grammaire", "") != "PAROLE_GENERIQUE":
                continue
            orateur_el = e.find(f"{_NS}orateurs/{_NS}orateur")
            if orateur_el is None:
                continue
            nom = (orateur_el.findtext(f"{_NS}nom") or "").strip()
            texte = (e.findtext(f"{_NS}texte") or "").strip()
            if not texte:
                continue
            vivier = prises[id(courant)][section]
            if vivier and vivier[-1][0] == nom:
                vivier[-1][1].append(texte)  # même orateur : on recolle
            else:
                ref = (orateur_el.findtext(f"{_NS}id") or "").strip()
                vivier.append([nom, [texte], ref])

    out: list[DebatTexte] = []
    for texte_discute in textes:
        viviers = prises[id(texte_discute)]
        texte_discute.explications.extend(
            _explications_de_vote(viviers[_EXPLICATIONS])
        )
        texte_discute.interventions_generales.extend(
            _interventions(viviers[_DISCUSSION])
        )
        if not texte_discute.explications and not texte_discute.interventions_generales:
            texte_discute.interventions_generales.extend(
                _interventions(viviers[_REPLI])
            )
        if texte_discute.explications or texte_discute.interventions_generales:
            out.append(texte_discute)
    return out


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


def _cle_texte(debat: DebatTexte) -> tuple:
    """Ce qui identifie le texte discuté : ses numéros quand le CR les porte
    (certain), sinon son titre plié."""
    return tuple(sorted(debat.numeros)) if debat.numeros else fold(debat.titre)


def fusionner_meme_texte(debats: list[DebatTexte]) -> list[DebatTexte]:
    """Recolle les discussions d'un MÊME texte le MÊME jour en un seul débat.

    Le compte rendu rouvre un `TITRE_TEXTE_DISCUSSION` à chaque reprise de
    séance : un texte débattu matin et après-midi apparaît deux fois. Sans cette
    fusion, `pour_vote` voit deux candidats quasi identiques, l'écart entre les
    deux meilleurs scores tombe sous `_ECART_MIN` et la liaison est refusée comme
    « ambiguë » — mesuré sur l'archive 17e législature : 31 cas d'ambiguïté,
    31 faux positifs, zéro vraie collision entre deux textes différents.

    La séance retenue est celle qui a fourni les prises de parole conservées, de
    sorte que le lien « compte rendu » renvoie bien à ce qui est cité (§7.5).
    """
    groupes: dict[tuple, list[DebatTexte]] = {}
    for d in debats:
        groupes.setdefault((d.date, _cle_texte(d)), []).append(d)
    fusionnes: list[DebatTexte] = []
    for groupe in groupes.values():
        if len(groupe) == 1:
            fusionnes.append(groupe[0])
            continue
        # Les explications de vote priment sur la discussion générale, ici comme
        # dans `extraire_debats` : si une seule des séances en porte, c'est elle
        # qui fait foi (et qui donne l'uid de séance cité en source).
        avec_explications = [d for d in groupe if d.explications]
        retenus = avec_explications or groupe
        fusionne = DebatTexte(
            titre=retenus[0].titre,
            date=retenus[0].date,
            seance_uid=retenus[0].seance_uid,
            numeros=frozenset().union(*(d.numeros for d in groupe)),
        )
        vus_groupes: set[str] = set()
        for d in retenus:
            for e in d.explications:
                if e.groupe not in vus_groupes:
                    vus_groupes.add(e.groupe)
                    fusionne.explications.append(e)
        if not fusionne.explications:
            vus_acteurs: set[str | None] = set()
            for d in retenus:
                for e in d.interventions_generales:
                    if e.acteur_ref not in vus_acteurs:
                        vus_acteurs.add(e.acteur_ref)
                        fusionne.interventions_generales.append(e)
        fusionnes.append(fusionne)
    return fusionnes


class IndexDebats:
    """Index des explications de vote, interrogeable par (date, titre, numéros).

    Construit une fois par run à partir de tous les comptes rendus, puis
    interrogé dossier par dossier avec la date et l'objet du vote conclusif, et
    les numéros de texte connus du dossier (archive dossiers législatifs) quand
    le dossier est officiel.
    """

    def __init__(self, debats: list[DebatTexte]) -> None:
        self._par_date: dict[str, list[DebatTexte]] = {}
        for d in fusionner_meme_texte(debats):
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
