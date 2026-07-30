"""Les 4 questions citoyennes de la fiche dossier (§2.2 : comprendre en 30 s).

1. Pourquoi les députés ont-ils débattu ?   → LLM, depuis titre + exposé des motifs.
2. Quel était le principal désaccord ?       → `generer_desaccord`, depuis les
   **comptes rendus des débats** : une paraphrase par groupe de sa propre
   explication de vote, jamais une synthèse éditoriale. Le sens (pour/contre)
   vient du scrutin, pas du modèle. Rien à quoi s'ancrer (pas de compte rendu
   relié) → la réponse reste None : on ne déduit pas un désaccord du titre ou de
   l'exposé (§2.5).
3. Quel est le résultat du vote ?            → déterministe, depuis le vote décisif.
4. Qu'est-ce que cela change concrètement ?  → LLM, depuis le **dispositif**
   officiel du texte quand il est disponible (fait : pas d'attribution, la
   réponse porte le lien vers le texte déposé) ; à défaut seulement, depuis
   l'exposé des motifs, alors toujours préfixé « Selon l'auteur du texte »
   (point de vue du déposant, §4.3).

Pourquoi un LLM ici alors que le résumé reste au gabarit déterministe : ces deux
réponses sont **attribuables à une source unique** (l'exposé) et **vérifiables
par des contrôles déterministes** — tout chiffre de la réponse doit exister dans
la source, la nature du texte (proposition/projet) ne doit pas être inversée,
lexique évaluatif interdit, attribution imposée pour la Q4. Réponse en échec →
None (§2.5), jamais publiée. Épreuves qwen3:14b (2026-07-18) : consignes tenues
(« information non disponible » respecté, attribution respectée, chiffres exacts)
là où mistral 7B fabriquait — d'où le passage à qwen3 (voir README §IA).

Le module porte aussi les questions d'un **vote d'amendement** (fiche vote) :
même logique — LLM uniquement sur ce qui est attribuable à une source unique
(exposé sommaire, dispositif) et validé déterministiquement ; résultat composé
déterministiquement ; le « qui était pour / contre » reste rendu côté app depuis
les positions de groupes du scrutin (jamais généré).
"""
from __future__ import annotations

import re

from app.ai.guardrails import LEXIQUE_ORIENTE
from app.ai.llm import LLMClient
from app.domain.enums import TypeVote
from app.ingestion.normalize import deposant, truncate_mots
from app.schemas import (
    ArgumentGroupe,
    DispositifTexte,
    QuestionsAmendement,
    QuestionsCitoyennes,
    Scrutin,
    ScrutinResume,
    TexteAdopte,
)
from app.utils.text import fold

PREFIXE_AUTEUR = "Selon l'auteur du texte"
# Attribution des réponses tirées de l'exposé sommaire d'un amendement (§4.3).
# « Selon son auteur » vaut pour un amendement comme pour un sous-amendement.
PREFIXE_AUTEUR_AMENDEMENT = "Selon son auteur"

# Une réponse doit rester lisible en un coup d'œil (§8) ; au-delà, le modèle
# a probablement brodé — on rejette plutôt que de tronquer une phrase.
_MAX_CHARS = 500

# L'exposé complet peut dépasser la fenêtre utile : le « pourquoi » et le
# « changement » sont dans les premières pages (constat + intention). Aligné sur
# le cap de stockage (`decouper_expose`, 4000) pour ne pas amputer l'exposé lu.
_MAX_EXPOSE_PROMPT = 4000

_STATUT_FR = {"adopte": "adopté", "rejete": "rejeté"}

_CONSIGNES_COMMUNES = (
    "Règles ABSOLUES :\n"
    "- Langage simple, sans vocabulaire juridique, phrases courtes.\n"
    "- Aucun jugement, aucun qualificatif évaluatif.\n"
    "- Ne cite AUCUN chiffre qui n'est pas écrit tel quel dans les données fournies.\n"
    "- Ne change pas la nature du texte (une proposition de loi n'est pas un "
    "projet de loi).\n"
    "- Ne développe JAMAIS un sigle (Anses, Arcom, CNIL…) et n'ajoute aucune "
    "explication entre parenthèses : recopie le sigle tel quel.\n"
    "- Ne dis pas qui a déposé le texte ou l'amendement si les données ne le "
    "disent pas : n'écris ni « le député », ni « le Gouvernement », par défaut.\n"
    "- 1 à 3 phrases maximum. Réponds uniquement par ces phrases, rien d'autre."
)

_SYS_POURQUOI = (
    "Tu expliques à un citoyen pourquoi les députés ont examiné un texte à "
    "l'Assemblée nationale, uniquement à partir du titre du texte et de son "
    "exposé des motifs (écrit par l'auteur du texte).\n" + _CONSIGNES_COMMUNES
)

_SYS_CHANGEMENT = (
    "Tu expliques à un citoyen ce qu'un texte de loi changerait concrètement, "
    "uniquement à partir de son exposé des motifs (écrit par l'auteur du texte, "
    "donc non neutre).\n"
    f"Commence obligatoirement ta réponse par « {PREFIXE_AUTEUR}, ».\n"
    "Utilise le conditionnel (« permettrait », « créerait ») : le changement "
    "n'est qu'annoncé par l'auteur.\n" + _CONSIGNES_COMMUNES
)

_SYS_CHANGEMENT_TEXTE = (
    "Tu expliques à un citoyen ce qu'un texte de loi français prévoit, "
    "uniquement à partir de son dispositif (les articles du texte déposé, "
    "c'est-à-dire le texte officiel lui-même).\n"
    "Utilise le conditionnel (« créerait », « obligerait ») : le texte n'est "
    "qu'une proposition tant qu'il n'est pas promulgué.\n"
    "N'attribue rien à personne : ce n'est pas un point de vue, c'est ce "
    "qu'écrit le texte.\n" + _CONSIGNES_COMMUNES
)

_SYS_CHANGEMENT_LOI = (
    "Tu expliques à un citoyen ce que change une loi française déjà en vigueur, "
    "uniquement à partir de son texte définitivement voté par le Parlement.\n"
    # Le SEUL registre qui diffère des deux autres sources de la Q4, et c'est le
    # cœur du sujet : le conditionnel dit « ce n'est qu'une proposition ». Sur un
    # texte promulgué, ce serait faux — la loi s'applique.
    "Utilise l'indicatif présent (« La loi interdit… », « Elle crée… ») : le "
    "texte a été voté et promulgué, il s'applique.\n"
    "N'attribue rien à personne : ce n'est pas un point de vue, c'est ce "
    "qu'écrit la loi.\n" + _CONSIGNES_COMMUNES
)

_SYS_POURQUOI_AMENDEMENT = (
    # « son auteur » et non « un député » : un amendement peut être déposé par
    # le Gouvernement ou par une commission (art. 44). L'ancienne formulation
    # faisait écrire au modèle « le député a proposé » sur un amendement
    # gouvernemental — d'où le garde-fou `deposant` en plus de la consigne.
    "Tu expliques à un citoyen pourquoi son auteur a déposé un amendement à un "
    "texte de loi, uniquement à partir de l'exposé sommaire de l'amendement "
    "(écrit par son auteur, donc non neutre).\n"
    f"Commence obligatoirement ta réponse par « {PREFIXE_AUTEUR_AMENDEMENT}, ».\n"
    + _CONSIGNES_COMMUNES
)

_SYS_CHANGEMENT_AMENDEMENT = (
    "Tu expliques à un citoyen ce qu'un amendement changerait dans un texte de "
    "loi, uniquement à partir du dispositif de l'amendement (le texte officiel "
    "de ce qu'il propose de modifier).\n"
    "Utilise le conditionnel (« ajouterait », « supprimerait ») : l'amendement "
    "n'est qu'une proposition de modification.\n" + _CONSIGNES_COMMUNES
)

# Une explication de vote paraphrasée doit tenir en une phrase courte (§8).
_MAX_ARGUMENT = 220

# Part minimale des mots de contenu d'un argument qui doit se retrouver dans
# l'explication de vote qu'il résume (cf. `_ancrage`). Volontairement PERMISSIF :
# l'extrait de compte rendu est désormais conservé en base
# (`dossier.desaccord_sources`), donc resserrer ce seuil plus tard ne coûte plus
# aucun appel au modèle — `python -m app.ingestion.revalider` suffit.
SEUIL_ANCRAGE_ARGUMENT = 0.30

_SYS_ARGUMENT = (
    "Un groupe politique explique en séance pourquoi il vote sur un texte à "
    "l'Assemblée nationale. Résume EN UNE SEULE PHRASE courte la raison qu'il "
    "donne, dans un langage simple et sobre.\n"
    "Règles ABSOLUES :\n"
    "- Reste fidèle au FOND de ce que dit le groupe ; n'ajoute rien, n'invente rien.\n"
    "- Ne reprends PAS les formules polémiques, vulgaires ou les attaques "
    "personnelles : garde l'argument de fond, dans un ton neutre.\n"
    "- Aucun jugement de ta part, aucun qualificatif évaluatif.\n"
    "- Ne dis pas s'il vote pour ou contre (c'est indiqué par ailleurs) : donne "
    "seulement la RAISON.\n"
    "- Ne cite aucun chiffre absent du texte fourni.\n"
    "- Une seule phrase, rien d'autre."
)


def _chiffres(texte: str) -> set[str]:
    """Les nombres (chiffres arabes) présents dans un texte, sans zéros de tête."""
    return {n.lstrip("0") or "0" for n in re.findall(r"\d+", texte)}


# Ponctuation typographique au-delà du latin étendu, légitime en français.
_PONCTUATION_AUTORISEE = frozenset(
    "\u2018\u2019\u201c\u201d\u2013\u2014\u2026\u20ac\u00a0\u202f"
)


def _caracteres_hors_francais(texte: str) -> bool:
    """Un caractère hors latin étendu / ponctuation française → texte suspect.

    Les modèles multilingues (qwen…) laissent parfois fuir des caractères CJK
    au milieu d'une phrase française — vu en épreuve (« décès婴幼儿 »)."""
    return any(
        ord(c) > 0x024F and c not in _PONCTUATION_AUTORISEE for c in texte
    )


# Glose entre parenthèses : un sigle ne se développe pas tout seul. Si la source
# écrit « l'Anses » sans jamais la développer, une réponse qui ajoute
# « (Agence nationale de sécurité du médicament et des produits de santé) »
# invente — et se trompe au passage (c'est le développement de l'ANSM). Cas réel,
# vu en base sur l'amendement n° 7 du projet de loi agricole.
_RE_PARENTHESE = re.compile(r"\(([^)]*)\)")


def _mots(texte: str) -> list[str]:
    """Suite des mots/nombres d'un texte, sans accents ni ponctuation."""
    return re.findall(r"[a-z0-9]+", fold(texte))


def _glose_ajoutee(reponse: str, sources: str) -> bool:
    """Une parenthèse dont le contenu n'est pas dans les sources = fait ajouté.

    Comparaison sur la suite des mots (ponctuation et accents neutralisés) :
    « (article 8) » passe si la source écrit « à l'article 8 ».
    """
    src = " ".join(_mots(sources))
    return any(
        (glose := " ".join(_mots(contenu))) and glose not in src
        for contenu in _RE_PARENTHESE.findall(reponse)
    )


# Termes désignant un parlementaire. Contrôle **asymétrique** : on rejette
# « le député » quand la source dit « du Gouvernement », mais pas l'inverse —
# l'exposé d'un amendement parlementaire mentionne légitimement le Gouvernement
# (« le Gouvernement n'a pas répondu à… »), alors que le Gouvernement n'est
# jamais un député.
_TERMES_PARLEMENTAIRE = frozenset(
    {
        "depute",
        "deputee",
        "deputes",
        "deputees",
        "senateur",
        "senatrice",
        "senateurs",
        "senatrices",
        "parlementaire",
        "parlementaires",
    }
)


def _deposant_requalifie(reponse: str, sources: str, deposant: str | None) -> bool:
    """Le déposant est le Gouvernement (ou une commission) et la réponse en fait
    un parlementaire, sans que la source emploie le mot."""
    if deposant not in ("gouvernement", "commission"):
        return False
    dans_la_source = set(_mots(sources))
    return any(
        mot in _TERMES_PARLEMENTAIRE and mot not in dans_la_source
        for mot in _mots(reponse)
    )


# --- Ancrage lexical -------------------------------------------------------
#
# Même règle que pour les chiffres et la glose — *le modèle reformule une source,
# il n'y ajoute rien* — étendue aux mots de contenu. Une paraphrase fidèle
# reprend forcément une partie du vocabulaire de ce qu'elle résume ; une phrase
# fabriquée n'en partage presque rien. Cas réel mesuré en base : « le texte ne
# répond pas aux attentes des Français en matière de sécurité et d'immigration »,
# servi tel quel sur trois dossiers sans rapport (dont un texte sur les honoraires
# d'expert-comptable), attribué à un groupe qui avait voté POUR — aucun contrôle
# de forme ne pouvait l'attraper.

# Mots vides du français courant : présents partout, ils ne prouvent aucun
# ancrage. Distincte de `_STOP` de `debats.py`, taillée pour les titres de textes
# juridiques : ici on compare de la prose à de la prose.
_MOTS_VIDES = frozenset(
    "le la les un une des du de au aux et ou mais donc car ni or que qui quoi "
    "dont ou est sont etre ete a ai as ont avoir eu il elle ils elles on nous "
    "vous je tu se sa son ses leur leurs ce cet cette ces cela ceci celui celle "
    "pour par sur sous dans avec sans vers chez entre pas ne plus moins tres "
    "aussi meme tout tous toute toutes autre autres quand comme si alors ainsi "
    "afin lors depuis apres avant encore deja bien fait faire dit dire peut "
    "doit devoir sera serait avait etaient nos vos mes tes leurs y en".split()
)

# Longueur de racine comparée : une paraphrase dit « remboursement » là où
# l'orateur a dit « rembourser ». Tronquer à 6 caractères rapproche les deux sans
# rapprocher des mots réellement différents.
_RACINE = 6


def _racines(texte: str) -> set[str]:
    """Racines des mots de contenu d'un texte (mots vides et mots courts exclus)."""
    return {
        mot[:_RACINE]
        for mot in _mots(texte)
        if len(mot) > 2 and mot not in _MOTS_VIDES
    }


def _ancrage(reponse: str, sources: str) -> float:
    """Part des mots de contenu de la réponse qui figurent dans la source.

    Normalisé sur la **réponse**, pas sur la source : ce qu'on mesure est ce que
    la paraphrase a ajouté, pas ce qu'elle a laissé de côté (une phrase courte
    résumant une longue intervention est légitime). Réponse sans aucun mot de
    contenu → 0.0, donc rejetée dès qu'un seuil est demandé."""
    mots = _racines(reponse)
    if not mots:
        return 0.0
    return len(mots & _racines(sources)) / len(mots)


def valider_reponse(
    reponse: str,
    sources: str,
    *,
    prefixe: str | None = None,
    max_chars: int = _MAX_CHARS,
    lexique_de_la_source_admis: bool = False,
    deposant: str | None = None,
    ancrage_minimal: float | None = None,
) -> str | None:
    """Contrôles déterministes d'une réponse LLM ; None au moindre doute (§2.5).

    - vide / trop longue → rejet ;
    - caractère hors français (fuite CJK d'un modèle multilingue) → rejet ;
    - lexique évaluatif (liste noire §4.3) → rejet ;
    - un nombre absent des sources → rejet (chiffre inventé ou converti) ;
    - nature du texte inversée (proposition ↔ projet) → rejet ;
    - préfixe d'attribution manquant (Q4 tirée de l'exposé) → rejet ;
    - glose entre parenthèses absente des sources → rejet (sigle « développé »
      de son propre chef, donc de travers) ;
    - déposant requalifié en parlementaire alors que la source désigne le
      Gouvernement ou une commission (`deposant`) → rejet ;
    - `ancrage_minimal` demandé et part des mots de contenu retrouvés dans la
      source inférieure au seuil → rejet (phrase fabriquée, sans rapport avec ce
      qu'elle prétend résumer).

    Ces trois derniers contrôles relèvent de la même règle que les chiffres : le
    modèle **reformule** une source, il n'y **ajoute** rien.

    `ancrage_minimal` est **opt-in** : il n'est activé que pour les paraphrases
    d'explication de vote (Q2), où la source est une prose courte et où le modèle
    a démontré qu'il savait broder du vraisemblable. La Q1/Q4 travaillent sur des
    exposés longs et parfois très éloignés du vocabulaire de la réponse : leur
    appliquer le même seuil sans campagne de mesure les invaliderait en masse.

    `lexique_de_la_source_admis` n'est activé que lorsque la source est un
    **texte officiel** (dispositif d'un texte ou d'un amendement) : un mot de la
    liste noire y est alors toléré s'il figure **tel quel dans la source** —
    même logique de contenance que pour les chiffres. Ce qu'on interdit, c'est
    que le modèle AJOUTE un jugement, pas qu'il reprenne les mots de la loi
    (cas réel : « l'exposition des jeunes utilisateurs aux contenus dangereux »,
    écrit dans l'article unique d'une proposition de résolution).
    """
    # Espaces normalisés : les cartes rendent un paragraphe, et le modèle livre
    # parfois une phrase par ligne — 23 réponses en base portaient déjà ces sauts
    # de ligne. Purement cosmétique, aucun mot n'est touché.
    reponse = re.sub(r"\s+", " ", reponse).strip()
    if not reponse or len(reponse) > max_chars:
        return None
    if _caracteres_hors_francais(reponse):
        return None
    if prefixe is not None and not reponse.startswith(prefixe):
        return None
    r_fold = fold(reponse)
    s_fold = fold(sources)
    orientes = {m for m in re.findall(r"[a-z]+", r_fold) if m in LEXIQUE_ORIENTE}
    if orientes and not (
        lexique_de_la_source_admis
        and orientes <= set(re.findall(r"[a-z]+", s_fold))
    ):
        return None
    if not _chiffres(reponse) <= _chiffres(sources):
        return None
    if _glose_ajoutee(reponse, sources):
        return None
    # Uniquement sur une réponse ATTRIBUÉE (« Selon son auteur, … ») : là, le
    # sujet de la phrase EST le déposant. Une réponse non attribuée nomme
    # légitimement les députés comme ceux qui ont examiné le texte — c'est même
    # l'amorce imposée à la Q1 (« Les députés ont examiné ce texte pour… »).
    if prefixe is not None and _deposant_requalifie(reponse, sources, deposant):
        return None
    if ancrage_minimal is not None and _ancrage(reponse, sources) < ancrage_minimal:
        return None
    for nature, opposee in (
        ("proposition de loi", "projet de loi"),
        ("projet de loi", "proposition de loi"),
    ):
        if nature in s_fold and opposee not in s_fold and opposee in r_fold:
            return None
    return reponse


# --- Accroche de carte, dérivée de la Q1 -----------------------------------
#
# L'accroche affichée dans le fil et la recherche n'est PAS une nouvelle
# génération : c'est la première phrase de la Q1 — déjà passée par
# `valider_reponse` — débarrassée de son amorce. Aucun fait nouveau n'est
# introduit ; sans Q1, il n'y a pas d'accroche (§2.5 : on masque).

# Une accroche tient sur deux lignes de carte.
_MAX_ACCROCHE = 160

# En deçà, la « phrase » est trop courte pour être une accroche (abréviation
# prise pour une fin de phrase, énumération) : on continue jusqu'à la suivante.
_MIN_PHRASE = 40

# Fin de phrase — un point précédé d'une seule majuscule est une abréviation
# (« M. Dupont », « Mme »), pas une fin de phrase.
_RE_FIN_PHRASE = re.compile(r"(?<![A-ZÀÂÉÈÊËÎÏÔÙÛÜÇ])[.!?](?:\s|$)")

# Amorce imposée par `_SYS_POURQUOI` (« pourquoi les députés ont examiné un
# texte ») : 185 des 187 Q1 en base la portent. Testée sur la forme foldée, d'où
# l'absence d'accents ; les deux apostrophes (droite et courbe) sont acceptées,
# `fold` ne les normalise pas.
_RE_AMORCE_Q1 = re.compile(
    r"^les deputes\s+(?:ont examine|examinent|ont debattu de|ont vote sur|"
    r"ont etudie|se sont penches sur)\s+"
    r"(?:ce|cette|le|la)\s+(?:texte|projet|proposition|resolution|dossier)"
    r"(?:\s+de\s+(?:loi|resolution))?(?:\s+organique)?"
    r"(?:\s+a l['’]assemblee nationale)?"
    r"(?:\s+(?:pour|car|afin d['’e]|parce qu['’e]|puisqu['’e]))?\s*"
)


def _phrases(texte: str) -> list[str]:
    """Découpe en phrases exploitables (les fragments courts sont recollés à la
    suivante, cf. `_MIN_PHRASE`)."""
    phrases: list[str] = []
    debut = 0
    for m in _RE_FIN_PHRASE.finditer(texte):
        candidate = texte[debut : m.end()].strip()
        if len(candidate) >= _MIN_PHRASE:
            phrases.append(candidate)
            debut = m.end()
    reste = texte[debut:].strip()
    if len(reste) >= _MIN_PHRASE:
        phrases.append(reste)
    return phrases or [texte]


def _sans_amorce(phrase: str) -> str:
    """La phrase débarrassée de l'amorce de Q1 (chaîne vide s'il ne reste rien)."""
    plie = fold(phrase)
    m = _RE_AMORCE_Q1.match(plie)
    if not m:
        return phrase
    # `fold` peut théoriquement changer la longueur (ligatures) : on ne coupe
    # que si l'index reste valide sur la chaîne d'origine.
    if fold(phrase[: m.end()]) != plie[: m.end()]:
        return phrase
    reste = phrase[m.end() :].lstrip(" ,;:–-")
    # « Les députés ont examiné cette proposition de résolution. » : il ne reste
    # que la ponctuation finale — la phrase n'était QUE l'amorce.
    return reste.strip() if any(c.isalpha() for c in reste) else ""


def accroche_depuis_q1(pourquoi: str | None) -> str | None:
    """Accroche de carte tirée de la Q1 « pourquoi ont-ils débattu ? ».

    On garde la première phrase et on retire l'amorce (« Les députés ont examiné
    ce texte pour… ») : répétée sur chaque carte du fil, elle mange la place
    utile sans rien dire. Une phrase qui n'est QUE l'amorce (« Les députés ont
    examiné cette proposition de résolution. ») ne dit rien non plus : on passe
    à la suivante. Amorce non reconnue → phrase rendue telle quelle. Pas de Q1,
    ou rien d'exploitable → pas d'accroche (§2.5).
    """
    if not pourquoi or not pourquoi.strip():
        return None
    for phrase in _phrases(" ".join(pourquoi.split())):
        reste = _sans_amorce(phrase)
        if reste:
            return truncate_mots(reste[0].upper() + reste[1:], _MAX_ACCROCHE)
    return None


def _vote_decisif(scrutins: list[ScrutinResume]) -> ScrutinResume | None:
    """Le vote sur l'ensemble si présent, sinon le plus récent (liste triée
    du plus récent au plus ancien) — même règle que `faits._vote_decisif`."""
    for s in scrutins:
        if "ensemble" in fold(s.objet):
            return s
    return scrutins[0] if scrutins else None


def _s(n: int) -> str:
    return "s" if n > 1 else ""


def phrase_resultat(scrutins: list[ScrutinResume]) -> str | None:
    """Q3, déterministe : le résultat du vote décisif, en une phrase (§8).

    Sans vote décisif au statut tranché, ou sans décompte public affichable
    (vote à main levée, §5.2) → None (§2.5)."""
    d = _vote_decisif(scrutins)
    if d is None:
        return None
    statut = _STATUT_FR.get(d.statut.value)
    if statut is None:
        return None
    sujet = (
        "Le texte a été"
        if "ensemble" in fold(d.objet)
        else "Le dernier vote sur le texte a été"
    )
    if not d.scrutin_public:
        return f"{sujet} {statut} à main levée (pas de décompte des voix)."
    if d.type_vote is TypeVote.motion_censure:
        return phrase_motion_censure(d)
    return _decompte(sujet, statut, d.statut.value, d.resultat)


def phrase_motion_censure(s) -> str:
    """Le résultat d'une motion de censure — qui ne se raconte PAS pour/contre.

    L'article 49 de la Constitution ne fait recenser que les voix **favorables**
    à la motion : `contre` et `abstention` valent 0 par construction (vérifié sur
    les 23 motions de la législature). La formule générale, qui met « le camp
    gagnant en premier », produisait donc sur un rejet « rejeté par **0 voix
    contre 267** » — l'inverse exact du fait, puisque 267 députés avaient voté
    POUR la censure. Le seul rapport qui décide est voix recueillies / requises.

    Le seuil manquant (source muette) n'est pas deviné : on s'en tient alors aux
    voix recueillies (§2.5).
    """
    voix = s.resultat.pour
    requises = s.suffrages_requis
    if requises:
        recueil = f"La motion de censure a recueilli {voix} voix sur les {requises} requises"
    else:
        recueil = f"La motion de censure a recueilli {voix} voix"
    issue = (
        "elle a été adoptée et le gouvernement est renversé"
        if s.statut.value == "adopte"
        else "elle n'a pas été adoptée"
    )
    return f"{recueil} ; {issue}."


def _decompte(sujet: str, statut: str, statut_brut: str, r) -> str:
    """« … par X voix contre Y » avec le camp GAGNANT en premier : « rejeté par
    268 voix contre 188 » (et non l'inverse, trompeur quand pour < contre).

    ⚠️ Ne convient PAS à une motion de censure, dont les opposants ne sont pas
    recensés — voir `phrase_motion_censure`.
    """
    gagnant, perdant = (
        (r.pour, r.contre) if statut_brut == "adopte" else (r.contre, r.pour)
    )
    phrase = f"{sujet} {statut} par {gagnant} voix contre {perdant}"
    if r.abstention:
        phrase += f", avec {r.abstention} abstention{_s(r.abstention)}"
    return phrase + "."


async def generer_changement_texte(
    titre_officiel: str, dispositif: str, llm: LLMClient
) -> str | None:
    """Q4 **factuelle** : ce que le texte prévoit, depuis son dispositif officiel.

    Mêmes contrôles déterministes que partout ailleurs (`valider_reponse`), mais
    **sans préfixe d'attribution** : la source n'est pas un point de vue, c'est
    le texte lui-même. None si la réponse ne passe pas les contrôles (§2.5).
    Le dispositif est lu ENTIÈREMENT (le cap est appliqué à l'extraction, cf.
    `textes_an._MAX_DISPOSITIF` : au-delà, il n'est pas stocké du tout).
    """
    sources = f"{titre_officiel}\n{dispositif}"
    user = f"TITRE : {titre_officiel}\n\nDISPOSITIF DU TEXTE :\n{dispositif}"
    reponse = await llm.generate_text(_SYS_CHANGEMENT_TEXTE, user)
    return valider_reponse(reponse, sources, lexique_de_la_source_admis=True)


async def generer_changement_loi(
    titre_officiel: str, texte_loi: str, llm: LLMClient
) -> str | None:
    """Q4 d'une **loi en vigueur** : ce qu'elle change, depuis le texte voté.

    Même contrat que `generer_changement_texte` — fait officiel, aucune
    attribution, mêmes contrôles déterministes — à un mot près, décisif :
    l'**indicatif**. Le dispositif du texte déposé décrit une proposition et se
    dit au conditionnel ; la loi promulguée, elle, s'applique.
    """
    sources = f"{titre_officiel}\n{texte_loi}"
    user = f"TITRE : {titre_officiel}\n\nTEXTE DE LOI VOTÉ :\n{texte_loi}"
    reponse = await llm.generate_text(_SYS_CHANGEMENT_LOI, user)
    return valider_reponse(reponse, sources, lexique_de_la_source_admis=True)


async def generer_questions(
    titre_officiel: str,
    scrutins: list[ScrutinResume],
    expose_texte: str | None,
    llm: LLMClient | None,
    dispositif: DispositifTexte | None = None,
    texte_adopte: TexteAdopte | None = None,
) -> QuestionsCitoyennes:
    """Compose les 4 réponses. Sans LLM (ni exposé ni dispositif), seule la Q3
    (déterministe) est renseignée — les autres restent « information non
    disponible » (§2.5).

    Q4 « qu'est-ce que ça change » a **trois** sources, dans cet ordre — chacune
    plus proche de ce qui s'applique réellement que la suivante :

    1. le **texte définitivement voté** (la loi elle-même) : fait, sans
       attribution, à l'**indicatif** ;
    2. le **dispositif du texte déposé** : fait aussi, mais d'une version que la
       navette a modifiée — d'où le conditionnel ;
    3. l'**exposé des motifs** : point de vue de l'auteur, obligatoirement
       préfixé « Selon l'auteur du texte ».

    C'est le prolongement de la règle déjà en place (« le fait officiel prime sur
    la parole du déposant ») : la loi votée prime sur le texte déposé.
    """
    questions = QuestionsCitoyennes(resultat=phrase_resultat(scrutins))
    if llm is None:
        return questions

    if texte_adopte and texte_adopte.texte:
        questions.changement = await generer_changement_loi(
            titre_officiel, texte_adopte.texte, llm
        )
        if questions.changement:
            questions.changement_source = texte_adopte.source

    if dispositif and not questions.changement:
        questions.changement = await generer_changement_texte(
            titre_officiel, dispositif.texte, llm
        )
        if questions.changement:
            # La réponse est un fait : elle porte son lien vers le texte (§7.5).
            questions.changement_source = dispositif.source

    if not expose_texte:
        return questions

    expose = expose_texte[:_MAX_EXPOSE_PROMPT]
    sources = f"{titre_officiel}\n{expose}"
    user = f"TITRE : {titre_officiel}\n\nEXPOSÉ DES MOTIFS :\n{expose}"
    # Un PROJET de loi émane du Gouvernement (art. 39) : la Q4, attribuée à
    # « l'auteur du texte », ne doit pas en faire un député.
    qui_depose = deposant(titre_officiel)

    reponse = await llm.generate_text(_SYS_POURQUOI, user)
    questions.pourquoi = valider_reponse(reponse, sources)

    # Repli seulement : le fait officiel prime sur la parole de l'auteur.
    if not questions.changement:
        reponse = await llm.generate_text(_SYS_CHANGEMENT, user)
        questions.changement = valider_reponse(
            reponse, sources, prefixe=PREFIXE_AUTEUR, deposant=qui_depose
        )

    return questions


def phrase_resultat_amendement(scrutin: Scrutin) -> str | None:
    """Résultat du vote d'un amendement, déterministe, en une phrase (§8).

    Sans statut tranché → None (§2.5). Sans décompte public (main levée, §5.2),
    on le dit sans chiffres."""
    statut = _STATUT_FR.get(scrutin.statut.value)
    if statut is None:
        return None
    sujet = (
        "Le sous-amendement a été"
        if "sous-amendement" in fold(scrutin.objet)
        else "L'amendement a été"
    )
    if not scrutin.scrutin_public:
        return f"{sujet} {statut} à main levée (pas de décompte des voix)."
    # Pas de branche « motion de censure » ici : un amendement n'en est jamais
    # une (le type `MOC` ne porte que sur la motion elle-même).
    return _decompte(sujet, statut, scrutin.statut.value, scrutin.resultat)


async def generer_questions_amendement(
    scrutin: Scrutin, llm: LLMClient | None
) -> QuestionsAmendement:
    """Compose les questions citoyennes d'un vote d'amendement (fiche vote).

    - `resultat` : déterministe, depuis le vote lui-même.
    - `pourquoi` : LLM depuis l'**exposé sommaire** (point de vue de l'auteur →
      attribution « Selon son auteur » imposée et vérifiée, §4.3).
    - `changement` : LLM depuis le **dispositif** (extrait officiel), au
      conditionnel.
    Chaque réponse LLM passe les contrôles déterministes (`valider_reponse`) ;
    rejet → None (§2.5). Le « qui était pour / contre » n'est pas généré ici :
    l'app le rend depuis les positions de groupes du scrutin (déterministe).
    """
    questions = QuestionsAmendement(resultat=phrase_resultat_amendement(scrutin))
    if llm is None:
        return questions

    # L'objet officiel fait partie des sources : le numéro de l'amendement (ou
    # un article cité) peut légitimement apparaître dans la réponse.
    # Le déposant est lisible dans l'objet officiel (« … n° 7 du Gouvernement »).
    qui_depose = deposant(scrutin.objet)

    if scrutin.expose_sommaire:
        sources = f"{scrutin.objet}\n{scrutin.expose_sommaire}"
        user = (
            f"VOTE : {scrutin.objet}\n\n"
            f"EXPOSÉ SOMMAIRE :\n{scrutin.expose_sommaire}"
        )
        reponse = await llm.generate_text(_SYS_POURQUOI_AMENDEMENT, user)
        questions.pourquoi = valider_reponse(
            reponse,
            sources,
            prefixe=PREFIXE_AUTEUR_AMENDEMENT,
            deposant=qui_depose,
        )

    if scrutin.dispositif:
        sources = f"{scrutin.objet}\n{scrutin.dispositif}"
        user = f"VOTE : {scrutin.objet}\n\nDISPOSITIF :\n{scrutin.dispositif}"
        reponse = await llm.generate_text(_SYS_CHANGEMENT_AMENDEMENT, user)
        # Source officielle (le dispositif de l'amendement) : ses propres mots
        # sont admis, seul un jugement AJOUTÉ par le modèle est rejeté.
        questions.changement = valider_reponse(
            reponse,
            sources,
            lexique_de_la_source_admis=True,
            deposant=qui_depose,
        )

    return questions


def valider_argument(argument: str, prononce: str) -> str | None:
    """Contrôles d'une paraphrase d'explication de vote (Q2) ; None au moindre doute.

    Point d'entrée **unique**, partagé par la génération (`generer_desaccord`) et
    la revalidation hors ligne (`ingestion.revalider`) : les deux doivent juger
    sur exactement les mêmes règles, sinon un run réintroduirait ce que la
    revalidation vient d'effacer.
    """
    return valider_reponse(
        argument,
        prononce,
        max_chars=_MAX_ARGUMENT,
        ancrage_minimal=SEUIL_ANCRAGE_ARGUMENT,
    )


async def generer_desaccord(
    interventions: list[tuple[str, PositionVote, str]],
    llm: LLMClient | None,
) -> list[ArgumentGroupe]:
    """Q2 « principal désaccord » : une paraphrase courte, par groupe, de son
    explication de vote — attribuée, à même gabarit pour tous (§7.4).

    `interventions` = liste de (nom du groupe, sens de vote **issu du scrutin**,
    texte de l'explication de vote). Le LLM ne produit QUE l'argument (la raison
    donnée par le groupe), validé contre son propre texte (aucun fait ajouté).
    Le sens (pour/contre) n'est jamais touché par le LLM. Un groupe dont la
    paraphrase est rejetée est simplement omis (§2.5), sans bloquer les autres.

    L'argument est validé contre le texte réellement prononcé, **ancrage lexical
    compris** : mettre dans la bouche d'un groupe une opinion qu'il n'a pas
    exprimée est précisément ce que §7.4 interdit, et aucun contrôle de forme ne
    l'attrape.
    """
    if llm is None:
        return []
    arguments: list[ArgumentGroupe] = []
    for groupe, sens, texte in interventions:
        user = f"GROUPE : {groupe}\nEXPLICATION DE VOTE :\n{texte}"
        reponse = await llm.generate_text(_SYS_ARGUMENT, user)
        argument = valider_argument(reponse, texte)
        if argument:
            arguments.append(
                ArgumentGroupe(groupe=groupe, sens=sens, argument=argument)
            )
    return arguments
