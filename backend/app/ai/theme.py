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
        "Réponds UNIQUEMENT par un seul mot de la liste, exactement tel qu'écrit, "
        "sans ponctuation ni explication.\n"
        "Un texte de procédure (motion de censure, commission d'enquête, "
        "résolution) sans sujet de fond clair → Autre."
    )


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
    titre: str, llm: LLMClient, themes: Sequence[str]
) -> str | None:
    """Thème proposé par le LLM pour un titre, ou None si réponse invalide/absente."""
    reponse = await llm.generate_text(_system_prompt(themes), f"Titre : {titre}")
    return valider_theme(reponse, themes)
