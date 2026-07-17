"""Tests de la classification de thème par LLM (validation stricte + repli)."""
from __future__ import annotations

from app.ai.theme import classifier_theme, valider_theme
from app.ingestion.normalize import THEMES


class _FakeLLM:
    """LLM factice : renvoie une réponse fixe (aucun réseau)."""

    def __init__(self, reponse: str) -> None:
        self._reponse = reponse

    async def generate_text(self, system: str, user: str) -> str:
        return self._reponse

    async def generate_json(self, system: str, user: str) -> dict:
        return {}


def test_valider_theme_exact_insensible_casse_accents():
    assert valider_theme("Justice", THEMES) == "Justice"
    assert valider_theme("justice.", THEMES) == "Justice"
    assert valider_theme("  SANTE ", THEMES) == "Santé"


def test_valider_theme_hors_liste_est_rejete():
    assert valider_theme("Economie", THEMES) is None
    assert valider_theme("Transport", THEMES) is None


def test_valider_theme_verbeux_est_rejete():
    # Le modèle ajoute une justification → on ne devine pas, on rejette.
    assert valider_theme("Environnement (car risque sanitaire)", THEMES) is None
    assert valider_theme("", THEMES) is None


async def test_classifier_retourne_theme_valide():
    assert await classifier_theme("Titre santé", _FakeLLM("Santé"), THEMES) == "Santé"


async def test_classifier_repli_si_reponse_invalide():
    # Sortie hors-liste → None (l'appelant garde l'existant).
    assert await classifier_theme("Titre", _FakeLLM("Economie"), THEMES) is None


async def test_classifier_repli_si_llm_muet():
    # LLM indisponible (chaîne vide) → None.
    assert await classifier_theme("Titre", _FakeLLM(""), THEMES) is None
