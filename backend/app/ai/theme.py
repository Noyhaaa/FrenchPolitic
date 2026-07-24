"""Classification de thème d'un dossier par LLM (tâche à faible risque éditorial).

Le modèle choisit UN thème dans une **liste fermée** ; toute réponse hors-liste
ou verbeuse est **rejetée** (repli sur l'heuristique / « Autre »). On ne produit
aucun texte affiché — c'est une **étiquette de rangement**, pas de la prose
neutre : le risque de neutralité (§4.3) ne s'applique pas ici, contrairement à la
génération de résumé (qu'un 7B local ne fait pas de façon fiable).
"""
from __future__ import annotations

from collections.abc import Sequence

from app.ai.llm import LLMClient
from app.utils.text import fold


def _system_prompt(themes: Sequence[str]) -> str:
    return (
        "Tu classes un texte de loi français dans UN thème, choisi STRICTEMENT "
        "dans cette liste : " + ", ".join(themes) + ".\n"
        "Réponds UNIQUEMENT par l'un de ces thèmes, recopié EXACTEMENT tel qu'écrit "
        "(y compris les espaces et le « & »), sans ponctuation ni explication.\n"
        "N'emploie « Autre » que si le texte n'a vraiment aucun sujet de fond "
        "rattachable à un thème de la liste."
    )


# Cap de l'extrait d'exposé injecté (la classification n'a besoin que de l'amorce).
_MAX_EXPOSE_PROMPT = 1000


def _user_prompt(titre: str, objet: str | None, expose: str | None) -> str:
    """Message utilisateur : titre + (objet du vote) + (amorce de l'exposé des
    motifs). Chaque partie est optionnelle — absente, sa ligne est omise, et on
    dégrade vers le comportement historique (titre seul)."""
    lignes = [f"Titre : {titre}"]
    if objet:
        lignes.append(f"Objet : {objet}")
    if expose:
        lignes.append(f"Exposé des motifs (extrait) : {expose[:_MAX_EXPOSE_PROMPT]}")
    return "\n".join(lignes)


def valider_theme(reponse: str, themes: Sequence[str]) -> str | None:
    """Thème valide si la réponse correspond **exactement** à un thème (à la casse
    et aux accents près). Réponse verbeuse (« Environnement (car…) ») ou
    hors-liste (« Economie », « Transport ») → None : on ne devine pas, on garde
    l'existant.
    """
    r = fold(reponse.strip().strip(".").strip())
    for t in themes:
        if fold(t) == r:
            return t
    return None


async def classifier_theme(
    titre: str,
    llm: LLMClient,
    themes: Sequence[str],
    *,
    objet: str | None = None,
    expose: str | None = None,
) -> str | None:
    """Thème proposé par le LLM, ou None si réponse invalide/absente.

    On donne au modèle le titre, l'objet du vote et une amorce de l'exposé des
    motifs quand ils sont disponibles : plus de signal que le titre seul → moins
    de repli sur « Autre ». La sortie reste **validée exact-match** contre la
    liste fermée (`valider_theme`), donc l'enrichissement ne peut pas introduire
    de thème invalide."""
    reponse = await llm.generate_text(
        _system_prompt(themes), _user_prompt(titre, objet, expose)
    )
    return valider_theme(reponse, themes)
