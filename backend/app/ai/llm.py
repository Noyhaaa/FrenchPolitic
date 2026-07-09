"""Abstraction du fournisseur d'IA (§6 : « rester capable de changer de modèle »).

Les routes/générateurs dépendent du protocole `LLMClient`, jamais d'un SDK
concret. `MockLLM` permet de développer et tester tout le pipeline sans clé API ;
un `AnthropicLLM` viendra en Phase 2 (voir app.config.settings.llm_provider).
"""
from __future__ import annotations

import json
from typing import Protocol

from app.config import settings


class LLMClient(Protocol):
    async def generate_json(self, system: str, user: str) -> dict:
        """Retourne un objet JSON structuré (format imposé §4.2)."""
        ...


class MockLLM(LLMClient):
    """Implémentation déterministe, sans réseau.

    Ne fabrique jamais d'information : si le contexte fourni est vide, elle renvoie
    un résumé vide avec confiance « faible » — conforme à la règle d'or (§2.5).
    """

    async def generate_json(self, system: str, user: str) -> dict:
        has_context = "[" in user  # un passage étiqueté [source_id] est présent
        if not has_context:
            return {
                "titre_clair": "",
                "resume": [],
                "public_concerne": [],
                "confiance": "faible",
                "champs_non_documentes": ["resume"],
            }
        # En présence de contexte, un vrai modèle reformulerait ; ici on renvoie
        # une enveloppe minimale valide (le pipeline réel branchera AnthropicLLM).
        return {
            "titre_clair": "",
            "resume": [],
            "public_concerne": [],
            "confiance": "moyenne",
            "champs_non_documentes": [],
        }


def get_llm_client() -> LLMClient:
    """Fabrique le client selon la configuration."""
    provider = settings.llm_provider.lower()
    if provider == "mock":
        return MockLLM()
    # TODO(Phase 2) : if provider == "anthropic": return AnthropicLLM(...)
    raise NotImplementedError(
        f"Fournisseur LLM non implémenté : '{provider}'. "
        "Seul 'mock' est disponible pour l'instant."
    )


def dumps(obj: dict) -> str:
    return json.dumps(obj, ensure_ascii=False)
