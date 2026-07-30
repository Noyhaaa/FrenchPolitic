"""Helpers de normalisation open data → schéma `Scrutin`."""
from __future__ import annotations

import re

from app.domain.enums import ObjetVote, PositionVote, TypeVote
from app.utils.text import fold

# Liste fermée des thèmes (source unique, miroir de `ThemeScrutin` côté front).
# L'open data ne fournit pas de thème : on le devine par heuristique (mots-clés du
# titre) puis, pour les « Autre » restants, par LLM (liste imposée, cf. app.ai.theme).
# ⚠️ Contrat : tout ajout ici doit l'être aussi dans `src/types/index.ts`
# (`ThemeScrutin`) et `src/constants/themes.ts` (3 maps). Cap 32 car. (DB `String(32)`).
THEMES: tuple[str, ...] = (
    "Logement",
    "Santé",
    "Fiscalité",
    "Énergie",
    "Éducation",
    "Environnement",
    "Justice",
    "Travail",
    "Économie",
    "Institutions",
    "Vie parlementaire",
    "International & Défense",
    "Agriculture",
    "Transports",
    "Culture",
    "Sport",
    "Immigration",
    "Sécurité",
    "Autre",
)

# Thème dédié aux textes purement procéduraux (routage déterministe, sans LLM).
THEME_PROCEDURAL = "Vie parlementaire"

# Phrases complètes (foldées) marquant un texte procédural. On teste des phrases
# entières et non le mot « motion » seul, qui capterait « motion de rejet préalable »
# ou « motion de renvoi en commission » attachées à un texte de fond.
_PHRASES_PROCEDURALES: tuple[str, ...] = (
    "motion de censure",
    "declaration de politique generale",
)

# Devine le thème à partir de mots-clés du titre (heuristique, pas d'opinion).
# Sous-ensemble de THEMES : seuls les thèmes à sous-chaînes FIABLES sont ici.
# Institutions & International/Défense sont laissés au LLM (leurs mots — « traite »
# ⊂ « traitement », « etranger » ⊂ « affaires étrangères », « election »… — sont
# trop larges/collisionnants). Ordre = précédence (1er match gagne) : le spécifique
# avant le générique. Transports AVANT Sport car « sport » ⊂ « transport ». Économie
# (large) en dernier.
_THEME_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("Agriculture", ("agricol", "alimentaire", "paysan")),
    ("Transports", ("transport", "autorouti", "ferroviaire", "mobilite", "aerien")),
    ("Sport", ("sport", "olympique")),
    ("Culture", ("culturel", "patrimoine", "audiovisuel", "restitution")),
    ("Immigration", ("immigration", "asile", "nationalite")),
    # « municip » couvre municipal/municipaux/municipale ; « scrutin » les modes de
    # scrutin (Conseil de Paris…). On évite « election » (⊂ « sélection »).
    ("Institutions", ("municip", "electoral", "scrutin", "constitutionnel", "corse", "caledonie", "elu local")),
    ("Sécurité", ("securite civile", "gendarmerie", "pompier")),
    ("Logement", ("logement", "loyer", "habitat", "bail", "locati", "hlm")),
    ("Santé", ("sante", "soin", "hopital", "medecin", "medical", "hospital", "palliati", "aide a mourir", "fin de vie")),
    ("Fiscalité", ("impot", "fiscal", "taxe", "budget", "finances", "tva")),
    ("Énergie", ("energie", "electricite", "gaz", "nucleaire", "carburant", "petrol")),
    ("Éducation", ("ecole", "education", "enseign", "universit", "scolaire", "eleve", "etudiant")),
    ("Environnement", ("environnement", "climat", "ecolog", "pollution", "biodiversite", "pesticide")),
    ("Justice", ("justice", "penal", "peine", "tribunal", "delit", "criminel", "prison", "victim")),
    ("Travail", ("travail", "emploi", "salari", "chomage", "retraite", "syndic")),
    ("Économie", ("economi", "industrie", "entreprise", "consommateur", "concurrence")),
]

# Garde-fou : toute étiquette de mots-clés doit exister dans la liste fermée.
assert all(t in THEMES for t, _ in _THEME_KEYWORDS), "thème mots-clés hors THEMES"
assert THEME_PROCEDURAL in THEMES


def est_texte_procedural(*textes: str) -> bool:
    """Le vote porte-t-il sur un texte purement procédural (motion de censure,
    déclaration de politique générale) ? Ces événements n'ont pas de sujet de fond
    et sont rangés dans « Vie parlementaire » plutôt que « Autre »."""
    blob = fold(" ".join(t for t in textes if t))
    return any(p in blob for p in _PHRASES_PROCEDURALES)


# Votes portant sur la CONDUITE DE LA SÉANCE, pas sur un contenu : ils sont
# archivés comme les autres scrutins publics et peuvent être très serrés, mais
# « les députés ont refusé de prolonger la séance au-delà de minuit » ne dit rien
# de ce que le Parlement a décidé. Liste fermée, relevée sur les objets réels de
# la base — on n'écarte que ce qu'on a constaté (§2.5).
#
# À distinguer d'`est_texte_procedural` : une motion de censure ou une
# déclaration de politique générale sont, elles, des événements de fond.
_PHRASES_CONDUITE_DE_SEANCE: tuple[str, ...] = (
    "suspension de seance",
    "prolonger la seance",
    "seconde deliberation",
)


def est_vote_de_conduite_de_seance(objet: str) -> bool:
    """Le vote porte-t-il sur le déroulement de la séance (suspension,
    prolongation au-delà de minuit, demande de seconde délibération) ?"""
    blob = fold(objet)
    return any(p in blob for p in _PHRASES_CONDUITE_DE_SEANCE)


def guess_theme(*textes: str) -> str:
    if est_texte_procedural(*textes):
        return THEME_PROCEDURAL
    blob = fold(" ".join(t for t in textes if t))
    for theme, mots in _THEME_KEYWORDS:
        if any(m in blob for m in mots):
            return theme
    return "Autre"


def map_statut(sort_code: str) -> str:
    """« adopté » → adopte, sinon rejete (un scrutin a toujours un résultat)."""
    return "adopte" if "adopt" in fold(sort_code) else "rejete"


# Les seuls `codeTypeVote` que l'archive produit (vérifié sur les 8 434 scrutins
# de la 17e législature : SPO 8 339, SPS 72, MOC 23). Table **fermée** : un code
# nouveau ne se devine pas, il ne produit simplement pas de type (§2.5).
_TYPES_VOTE = {
    "SPO": TypeVote.ordinaire,
    "SPS": TypeVote.solennel,
    "MOC": TypeVote.motion_censure,
}


def type_vote(code: str | None) -> TypeVote | None:
    """Forme du scrutin public d'après son code officiel, sinon None.

    C'est elle qui explique le nombre de votants : un scrutin **ordinaire** se
    tient en séance parmi les députés alors présents (médiane 132), un scrutin
    **solennel** est annoncé à l'avance (médiane 528). Cf. `TypeVote`.
    """
    return _TYPES_VOTE.get((code or "").strip().upper())


def est_amendement(objet: str) -> bool:
    """Le scrutin porte-t-il sur un amendement (vs. le texte : ensemble, article,
    motion) ? Heuristique sur l'objet du vote (couvre « amendement »,
    « sous-amendement », « amendements identiques »)."""
    return "amendement" in fold(objet)


def est_sous_amendement(objet: str) -> bool:
    """Le scrutin porte-t-il sur un sous-amendement (amendement à un amendement) ?"""
    return "sous-amendement" in fold(objet)


def type_objet_vote(objet: str) -> ObjetVote:
    """Nature de ce sur quoi portait un vote (texte, amendement, sous-amendement).

    Même partition que le classement des scrutins d'un dossier ; sert à situer
    chaque ligne de l'historique de vote d'un député (§5.2).
    """
    if est_sous_amendement(objet):
        return ObjetVote.sous_amendement
    if est_amendement(objet):
        return ObjetVote.amendement
    return ObjetVote.dossier


# « (sous-)amendement … n° 80 » — fold() transforme « º » en « o », d'où [°o].
# Le remplissage [^,]*? tolère « amendement de suppression n° 25 ».
_RE_NUMERO = re.compile(r"(?:sous-)?amendements?[^,]*?n[°o]\s*(\d+)")
# Numéro de l'amendement PARENT d'un sous-amendement (« … à l'amendement n° X ») :
# on exclut le mot « amendement » contenu dans « sous-amendement ».
_RE_NUMERO_PARENT = re.compile(r"(?<!sous-)amendements?[^,]*?n[°o]\s*(\d+)")
# « de M. Léaument » / « de Mme K/Bidi » — nom en un token, tel qu'écrit.
_RE_AUTEUR = re.compile(r"\bde\s+(M\.|Mme)\s+([A-ZÀ-Þ][\w'’/-]*)")


# Zone de l'objet qui décrit l'amendement voté, avant toute référence à un AUTRE
# amendement (« … à l'amendement n° 80 » d'un sous-amendement). Même découpe que
# `auteur_amendement`, pour la même raison.
_RE_RENVOI_AMENDEMENT = re.compile(r"(?:à\s+l['’]|aux\s+)amendements?\b", re.IGNORECASE)
# Un objet au pluriel (« les amendements identiques n° 154 …, n° 207 … et n° 410 »)
# porte plusieurs numéros : aucun ne désigne « l'amendement » voté à lui seul.
_RE_PLURIEL = re.compile(r"\bamendements\b")
_RE_TOUT_NUMERO = re.compile(r"n[°o]\s*\d+")


def numero_amendement(objet: str) -> str | None:
    """Numéro de l'amendement (ou du sous-amendement) voté, extrait de l'objet
    officiel. None si non identifiable (§2.5 : on n'invente pas).

    Un vote sur des **amendements identiques** (« les amendements identiques
    n° 154 rectifié, …, n° 207 rectifié bis, et n° 410 ») porte plusieurs
    numéros : en retenir un seul laisserait croire que le vote ne concernait que
    celui-là. On n'en retient donc aucun, et l'objet officiel est restitué tel
    quel par l'app.
    """
    zone = _RE_RENVOI_AMENDEMENT.split(objet, maxsplit=1)[0]
    if _RE_PLURIEL.search(fold(zone)) and len(_RE_TOUT_NUMERO.findall(fold(zone))) > 1:
        return None
    m = _RE_NUMERO.search(fold(objet))
    return m.group(1) if m else None


def numero_amendement_parent(objet: str) -> str | None:
    """Pour un sous-amendement : numéro de l'amendement visé
    (« le sous-amendement n° 3 … à l'amendement n° 80 » → « 80 »)."""
    m = _RE_NUMERO_PARENT.search(fold(objet))
    return m.group(1) if m else None


def auteur_amendement(objet: str) -> str | None:
    """Auteur (« M. X » / « Mme Y ») si l'objet officiel en désigne un seul.

    Plusieurs auteurs (amendements identiques) → None : pas d'ambiguïté (§2.5).
    Pour un sous-amendement, la mention de l'amendement parent (« … à
    l'amendement n° X de Mme Y ») est ignorée.
    """
    zone = re.split(r"(?:à\s+l['’]|aux\s+)amendements?\b", objet, flags=re.IGNORECASE)[0]
    auteurs = {f"{civ} {nom}" for civ, nom in _RE_AUTEUR.findall(zone)}
    return auteurs.pop() if len(auteurs) == 1 else None


# Qui a déposé, tel que l'objet officiel le désigne. L'Assemblée écrit « du
# Gouvernement », le Sénat « présenté par le Gouvernement » ; et la nature du
# texte porte le même fait, par définition constitutionnelle (art. 39 : un
# PROJET de loi émane du Gouvernement, une PROPOSITION d'un parlementaire).
_RE_DEPOSANT_GOUVERNEMENT = re.compile(r"\b(?:du|par le)\s+gouvernement\b", re.I)
# « de la commission des lois » désigne un déposant ; « de la commission mixte
# paritaire » désigne le TEXTE examiné (mention de procédure), pas un auteur.
_RE_DEPOSANT_COMMISSION = re.compile(
    r"\b(?:de|par)\s+la\s+commission\b(?!\s+mixte\s+paritaire)", re.I
)
_RE_NATURE_GOUVERNEMENT = re.compile(r"\bprojet de loi\b", re.I)
_RE_NATURE_PARLEMENTAIRE = re.compile(r"\bproposition de (?:loi|r[ée]solution)\b", re.I)
# Le Sénat écrit « présenté par M. Prénom Nom » là où l'AN écrit « de M. Nom » :
# une seule des deux formes suffit à désigner un parlementaire.
_RE_AUTEUR_PERSONNE = re.compile(r"\b(?:de|par)\s+(?:M\.|Mme|MM\.|Mmes)\s", re.I)


def deposant(objet: str) -> str | None:
    """« gouvernement » / « commission » / « parlementaire » si l'objet officiel
    du vote désigne le déposant **sans ambiguïté** — sinon None (§2.5).

    Sert de garde-fou aux réponses générées : le modèle ne doit pas requalifier
    l'auteur (cas réel : « Selon son auteur, LE DÉPUTÉ a proposé cet
    amendement » sur l'amendement n° 7 **du Gouvernement**).

    Deux indices concordants sont exigés dans les faits : quand la mention du
    déposant et la nature du texte se contredisent — « l'amendement n° 3 de
    M. Fugit … de la proposition de loi » concorde, mais « de M. X au projet de
    loi » désigne un amendement parlementaire sur un texte gouvernemental —, on
    renvoie None plutôt que de trancher. C'est ce qui rend le garde-fou sûr : il
    ne s'applique que là où la source est univoque.
    """
    zone = _RE_RENVOI_AMENDEMENT.split(objet)[0]
    trouves: set[str] = set()
    if _RE_DEPOSANT_GOUVERNEMENT.search(zone):
        trouves.add("gouvernement")
    if _RE_DEPOSANT_COMMISSION.search(zone):
        trouves.add("commission")
    if _RE_AUTEUR_PERSONNE.search(zone):
        trouves.add("parlementaire")
    # La nature du texte ne désigne que le déposant DU TEXTE : sur un vote
    # d'amendement, « … à l'article 5 du projet de loi » ne dit rien de qui a
    # déposé l'AMENDEMENT (un député amende couramment un projet de loi). On ne
    # s'en sert donc que pour un vote portant sur le texte lui-même.
    if not est_amendement(objet) and not est_sous_amendement(objet):
        if _RE_NATURE_GOUVERNEMENT.search(zone):
            trouves.add("gouvernement")
        if _RE_NATURE_PARLEMENTAIRE.search(zone):
            trouves.add("parlementaire")
    return trouves.pop() if len(trouves) == 1 else None


# Texte de loi cité dans l'objet d'un vote (« … à l'article 2 de la proposition
# de loi visant à … ») : nature reconnue puis tout ce qui suit. Seule
# « résolution » porte un accent → classe [ée] (pas de fold : on veut retrouver
# la casse/les accents d'origine pour le titre affiché).
_RE_TEXTE_RATTACHEMENT = re.compile(
    r"(?:projet de loi|proposition de loi|proposition de r[ée]solution)\b.*$",
    re.IGNORECASE | re.DOTALL,
)
# Mentions finales de procédure entre parenthèses (« (deuxième lecture) »,
# « (texte de la commission mixte paritaire) ») : à retirer de la clé de
# regroupement pour qu'un même texte ne soit pas éclaté par lecture.
#
# ⚠️ La source en ENCHAÎNE parfois deux : « …le droit à l'aide à mourir (seconde
# délibération) (deuxième lecture). » Le motif doit donc être répétable — ancré
# sur `$`, il n'en retirait qu'une, le titre gardait « (seconde délibération) »,
# sa signature ne correspondait plus au titre officiel et la réconciliation
# échouait : le texte se dédoublait en un `TXT-…` vide à côté de son vrai
# dossier. Vécu sur l'aide à mourir, le PLF 2026 et Mayotte.
#
# Seule la FIN est concernée : une parenthèse au milieu du titre (« l'article 24
# (supprimé) du projet de loi… ») fait partie de ce que la source désigne.
_RE_MENTION_FINALE = re.compile(r"(?:\s*\([^()]*\))+\s*$")


def texte_de_rattachement(objet: str) -> str | None:
    """Titre du texte de loi auquel se rattache un vote, extrait de son objet
    officiel (sous-chaîne telle quelle, §2.5 : rien n'est reformulé).

    Sert à regrouper sous un même dossier les scrutins dépourvus de
    `dossierRef` (amendements, articles, motions liées à un texte). None si
    l'objet ne cite aucun texte (motion de censure, déclaration…).
    """
    m = _RE_TEXTE_RATTACHEMENT.search(objet)
    if not m:
        return None
    titre = m.group(0).strip().rstrip(".").strip()
    titre = _RE_MENTION_FINALE.sub("", titre).strip()
    if not titre:
        return None
    return titre[0].upper() + titre[1:]


# Nature du texte, reconnue en tête de titre (miroir de `natureTexte` côté
# frontend). Ordre important : les variantes « organique » avant les génériques.
_NATURES: tuple[tuple[str, str], ...] = (
    ("projet de loi organique", "Projet de loi organique"),
    ("projet de loi", "Projet de loi"),
    ("proposition de loi organique", "Proposition de loi organique"),
    ("proposition de loi", "Proposition de loi"),
    # « européenne » avant le générique : sinon le préfixe court gagne et la
    # mention européenne resterait collée en tête du titre d'affichage.
    ("proposition de resolution europeenne", "Proposition de résolution européenne"),
    ("proposition de resolution", "Proposition de résolution"),
)


def nature_texte(titre: str) -> str | None:
    """Nature du texte (« Projet de loi »…) si le titre la porte, sinon None
    (§2.5 : on ne déduit pas)."""
    t = fold(titre).lstrip()
    for prefixe, libelle in _NATURES:
        if t.startswith(prefixe):
            return libelle
    return None


# Connecteurs (foldés) qui, APRÈS une nature, introduisent l'objet du texte :
# « Proposition de loi *visant à* améliorer… » → « Améliorer… ». Liste fermée :
# hors de cette liste, on ne touche pas au titre. C'est le garde-fou qui protège
# « Projet de loi *de finances* pour 2025 » ou « Proposition de loi *d'*abrogation
# de la retraite à 64 ans », où la nature fait partie du nom du texte.
_CONNECTEURS: tuple[str, ...] = (
    "visant a",
    # « visant AU rétablissement » : l'article contracté fait corps avec le
    # connecteur, il ne peut pas être capté par le groupe d'article qui suit.
    "visant au",
    "visant aux",
    "tendant a",
    "tendant au",
    "tendant aux",
    "relatif a",
    "relative a",
    "relatif au",
    "relative au",
    "relatif aux",
    "relative aux",
    "relatifs a",
    "relatives a",
    "appelant a",
    "appelant au",
    "appelant aux",
    "portant",
    "autorisant",
    "actualisant",
    "abrogeant",
    "prorogeant",
    "transposant",
    "organisant",
    "instituant",
    "creant",
    "modifiant",
    "ratifiant",
    "permettant",
    "renforcant",
    "ameliorant",
    "elargissant",
    "assurant",
    "adaptant",
    "simplifiant",
    "encadrant",
    "garantissant",
    "interdisant",
    "facilitant",
    "supprimant",
    "instaurant",
    "reconnaissant",
)


def _alternance(mots: tuple[str, ...]) -> str:
    """Alternance regex, du plus long au plus court (« relatif aux » avant
    « relatif au »), sur des chaînes déjà foldées."""
    return "|".join(re.escape(m) for m in sorted(mots, key=len, reverse=True))


# Nature + connecteur, plus l'article qui suit : « … visant à la nationalisation
# d'ArcelorMittal » → « Nationalisation d'ArcelorMittal » (un titre de carte se
# lit mieux sans son article de tête, comme un titre de presse).
# Mention de navette insérée entre la nature et le connecteur (« Proposition de
# loi, adoptée par le Sénat, relative à… ») : le fait est déjà porté par la
# trajectoire du dossier, il n'a pas à manger le titre de la carte.
_INSERTION_NAVETTE = r"(?:,\s*(?:adoptee|modifiee|rejetee)[^,]{0,40},)?"

# `fold` ne normalise PAS l'apostrophe : les deux formes doivent être écrites.
_ARTICLE = r"(?:les|la|le|l['’])"

_RE_NATURE_CONNECTEUR = re.compile(
    rf"^(?:{_alternance(tuple(p for p, _ in _NATURES))}){_INSERTION_NAVETTE}"
    rf"\s+(?:{_alternance(_CONNECTEURS)})\s+(?:{_ARTICLE}\s*)?"
)

# Article initial d'un objet de vote cité en minuscule (« la motion de censure
# déposée en application de l'article 49… »).
_RE_ARTICLE_INITIAL = re.compile(rf"^{_ARTICLE}\s*")


def titre_court(titre_officiel: str) -> str:
    """Titre d'affichage : le titre officiel débarrassé de ce qui est déjà porté
    ailleurs par l'interface (§8, langue simple).

    La nature (« Proposition de loi ») est affichée en label à part — la répéter
    en tête du titre coûte un quart de la place utile sur une vignette. On la
    retire donc, avec le connecteur qui la suit (« visant à », « portant »…),
    **uniquement** quand ce connecteur est dans la liste fermée `_CONNECTEURS` :
    ailleurs la nature fait partie du nom du texte (« Projet de loi de finances
    pour 2025 »), et on rend le titre intact.

    Rien n'est tronqué (le clamp de lignes de l'app s'en charge) et rien n'est
    reformulé (§2.5) : on ne fait que retirer un préfixe et capitaliser.
    """
    titre = " ".join(titre_officiel.split())
    if not titre:
        return titre
    plie = fold(titre)

    coupe = 0
    match = _RE_NATURE_CONNECTEUR.match(plie)
    if match:
        coupe = match.end()
    elif titre[0].islower():
        # Objet de vote cité tel quel par l'open data, en minuscule.
        article = _RE_ARTICLE_INITIAL.match(plie)
        coupe = article.end() if article else 0

    # `fold` peut théoriquement changer la longueur (ligatures) : on ne coupe que
    # si l'index reste valide sur la chaîne d'origine.
    if coupe and fold(titre[:coupe]) == plie[:coupe]:
        reste = titre[coupe:].strip()
        if reste:
            titre = reste

    return titre[0].upper() + titre[1:]


def map_position(position_majoritaire: str | None) -> PositionVote:
    """Position majoritaire d'un groupe → enum interne."""
    p = fold(position_majoritaire or "")
    if p.startswith("pour"):
        return PositionVote.pour
    if p.startswith("contre"):
        return PositionVote.contre
    if p.startswith("abstention"):
        return PositionVote.abstention
    # « absent », « nonVotant »… : le groupe n'a majoritairement pas pris part.
    return PositionVote.non_votant


def truncate(text: str, limit: int = 160) -> str:
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def truncate_mots(text: str, limit: int = 160) -> str:
    """Comme `truncate`, mais coupe à la frontière de mot.

    Pour une phrase lue par un humain (accroche d'une carte), un mot coupé en
    deux se remarque ; on recule au dernier espace, sauf s'il faut sacrifier
    plus de la moitié de la phrase (mot à rallonge) — auquel cas on coupe net.
    """
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    coupe = text[: limit - 1].rstrip()
    espace = coupe.rfind(" ")
    if espace > limit // 2:
        coupe = coupe[:espace]
    return coupe.rstrip(" ,;:") + "…"


def to_int(value: object, default: int = 0) -> int:
    """Les décomptes open data sont des chaînes ; conversion robuste."""
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def as_list(value: object) -> list:
    """L'open data sérialise « 1 élément » comme objet, « n » comme liste."""
    if value is None:
        return []
    return value if isinstance(value, list) else [value]
