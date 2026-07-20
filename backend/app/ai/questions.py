"""Les 4 questions citoyennes de la fiche dossier (§2.2 : comprendre en 30 s).

1. Pourquoi les députés ont-ils débattu ?   → LLM, depuis titre + exposé des motifs.
2. Quel était le principal désaccord ?       → JAMAIS généré ici : il faudrait les
   comptes rendus des débats en séance (non ingérés). On ne déduit pas un
   désaccord du titre ou de l'exposé (§2.5) — la réponse reste None.
3. Quel est le résultat du vote ?            → déterministe, depuis le vote décisif.
4. Qu'est-ce que cela change concrètement ?  → LLM, depuis l'exposé des motifs,
   toujours préfixé « Selon l'auteur du texte » (point de vue du déposant, §4.3).

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
from app.schemas import (
    ArgumentGroupe,
    QuestionsAmendement,
    QuestionsCitoyennes,
    Scrutin,
    ScrutinResume,
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
# « changement » sont dans les premières pages (constat + intention).
_MAX_EXPOSE_PROMPT = 3000

_STATUT_FR = {"adopte": "adopté", "rejete": "rejeté"}

_CONSIGNES_COMMUNES = (
    "Règles ABSOLUES :\n"
    "- Langage simple, sans vocabulaire juridique, phrases courtes.\n"
    "- Aucun jugement, aucun qualificatif évaluatif.\n"
    "- Ne cite AUCUN chiffre qui n'est pas écrit tel quel dans les données fournies.\n"
    "- Ne change pas la nature du texte (une proposition de loi n'est pas un "
    "projet de loi).\n"
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

_SYS_POURQUOI_AMENDEMENT = (
    "Tu expliques à un citoyen pourquoi un député a proposé un amendement à un "
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


def valider_reponse(
    reponse: str,
    sources: str,
    *,
    prefixe: str | None = None,
    max_chars: int = _MAX_CHARS,
) -> str | None:
    """Contrôles déterministes d'une réponse LLM ; None au moindre doute (§2.5).

    - vide / trop longue → rejet ;
    - caractère hors français (fuite CJK d'un modèle multilingue) → rejet ;
    - lexique évaluatif (liste noire §4.3) → rejet ;
    - un nombre absent des sources → rejet (chiffre inventé ou converti) ;
    - nature du texte inversée (proposition ↔ projet) → rejet ;
    - préfixe d'attribution manquant (Q4) → rejet.
    """
    reponse = reponse.strip()
    if not reponse or len(reponse) > max_chars:
        return None
    if _caracteres_hors_francais(reponse):
        return None
    if prefixe is not None and not reponse.startswith(prefixe):
        return None
    r_fold = fold(reponse)
    if any(mot in LEXIQUE_ORIENTE for mot in re.findall(r"[a-z]+", r_fold)):
        return None
    if not _chiffres(reponse) <= _chiffres(sources):
        return None
    s_fold = fold(sources)
    for nature, opposee in (
        ("proposition de loi", "projet de loi"),
        ("projet de loi", "proposition de loi"),
    ):
        if nature in s_fold and opposee not in s_fold and opposee in r_fold:
            return None
    return reponse


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
    return _decompte(sujet, statut, d.statut.value, d.resultat)


def _decompte(sujet: str, statut: str, statut_brut: str, r) -> str:
    """« … par X voix contre Y » avec le camp GAGNANT en premier : « rejeté par
    268 voix contre 188 » (et non l'inverse, trompeur quand pour < contre)."""
    gagnant, perdant = (
        (r.pour, r.contre) if statut_brut == "adopte" else (r.contre, r.pour)
    )
    phrase = f"{sujet} {statut} par {gagnant} voix contre {perdant}"
    if r.abstention:
        phrase += f", avec {r.abstention} abstention{_s(r.abstention)}"
    return phrase + "."


async def generer_questions(
    titre_officiel: str,
    scrutins: list[ScrutinResume],
    expose_texte: str | None,
    llm: LLMClient | None,
) -> QuestionsCitoyennes:
    """Compose les 4 réponses. Sans LLM ou sans exposé, seule la Q3 (déterministe)
    est renseignée — les autres restent « information non disponible » (§2.5)."""
    questions = QuestionsCitoyennes(resultat=phrase_resultat(scrutins))
    if llm is None or not expose_texte:
        return questions

    expose = expose_texte[:_MAX_EXPOSE_PROMPT]
    sources = f"{titre_officiel}\n{expose}"
    user = f"TITRE : {titre_officiel}\n\nEXPOSÉ DES MOTIFS :\n{expose}"

    reponse = await llm.generate_text(_SYS_POURQUOI, user)
    questions.pourquoi = valider_reponse(reponse, sources)

    reponse = await llm.generate_text(_SYS_CHANGEMENT, user)
    questions.changement = valider_reponse(reponse, sources, prefixe=PREFIXE_AUTEUR)

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
    if scrutin.expose_sommaire:
        sources = f"{scrutin.objet}\n{scrutin.expose_sommaire}"
        user = (
            f"VOTE : {scrutin.objet}\n\n"
            f"EXPOSÉ SOMMAIRE :\n{scrutin.expose_sommaire}"
        )
        reponse = await llm.generate_text(_SYS_POURQUOI_AMENDEMENT, user)
        questions.pourquoi = valider_reponse(
            reponse, sources, prefixe=PREFIXE_AUTEUR_AMENDEMENT
        )

    if scrutin.dispositif:
        sources = f"{scrutin.objet}\n{scrutin.dispositif}"
        user = f"VOTE : {scrutin.objet}\n\nDISPOSITIF :\n{scrutin.dispositif}"
        reponse = await llm.generate_text(_SYS_CHANGEMENT_AMENDEMENT, user)
        questions.changement = valider_reponse(reponse, sources)

    return questions


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
    """
    if llm is None:
        return []
    arguments: list[ArgumentGroupe] = []
    for groupe, sens, texte in interventions:
        user = f"GROUPE : {groupe}\nEXPLICATION DE VOTE :\n{texte}"
        reponse = await llm.generate_text(_SYS_ARGUMENT, user)
        argument = valider_reponse(reponse, texte, max_chars=_MAX_ARGUMENT)
        if argument:
            arguments.append(
                ArgumentGroupe(groupe=groupe, sens=sens, argument=argument)
            )
    return arguments
