"""Abstraction du fournisseur d'IA (§6 : « rester capable de changer de modèle »).

Les routes/générateurs dépendent du protocole `LLMClient`, jamais d'un SDK
concret. `MockLLM` permet de développer et tester tout le pipeline sans clé API ;
un `AnthropicLLM` viendra en Phase 2 (voir app.config.settings.llm_provider).
"""
from __future__ import annotations

import json
from typing import Protocol

import httpx

from app.config import settings


class LLMClient(Protocol):
    async def generate_json(self, system: str, user: str) -> dict:
        """Retourne un objet JSON structuré (format imposé §4.2)."""
        ...

    async def generate_text(self, system: str, user: str) -> str:
        """Retourne du texte brut (tâches simples : classification, étiquette).

        Chaîne vide en cas d'échec (modèle indisponible…) — l'appelant traite
        l'absence de réponse comme « pas de résultat » (§2.5), jamais un blocage.
        """
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

    async def generate_text(self, system: str, user: str) -> str:
        return ""  # sans modèle réel, pas de résultat (§2.5)


class OllamaLLM(LLMClient):
    """Client Ollama local (§6 : modèle interchangeable, sans clé API).

    Réservé aux tâches à **faible risque éditorial** — aujourd'hui la
    classification de thème (une étiquette dans une liste fermée). PAS pour
    générer de la prose neutre : un modèle 7B local n'y est pas assez fiable et
    les garde-fous lexicaux ne rattrapent pas ses biais (cf. README §IA).
    """

    def __init__(
        self,
        model: str,
        base_url: str = "http://localhost:11434",
        timeout: float = 60.0,
    ) -> None:
        self._model = model
        self._url = base_url.rstrip("/")
        self._timeout = timeout

    async def _generate(self, system: str, user: str, *, json_format: bool) -> str:
        payload: dict = {
            "model": self._model,
            "system": system,
            "prompt": user,
            "stream": False,
            "options": {"temperature": 0},  # déterministe pour une tâche de tri
        }
        if json_format:
            payload["format"] = "json"
        async with httpx.AsyncClient(timeout=self._timeout) as c:
            resp = await c.post(f"{self._url}/api/generate", json=payload)
            resp.raise_for_status()
            return (resp.json().get("response") or "").strip()

    async def generate_text(self, system: str, user: str) -> str:
        try:
            return await self._generate(system, user, json_format=False)
        except httpx.HTTPError:
            return ""  # Ollama absent/indisponible → pas de résultat (§2.5)

    async def generate_json(self, system: str, user: str) -> dict:
        try:
            raw = await self._generate(system, user, json_format=True)
            return json.loads(raw) if raw else {}
        except (httpx.HTTPError, json.JSONDecodeError):
            return {}


def get_llm_client() -> LLMClient:
    """Fabrique le client selon la configuration."""
    provider = settings.llm_provider.lower()
    if provider == "mock":
        return MockLLM()
    if provider == "ollama":
        return OllamaLLM(settings.llm_model, settings.llm_base_url)
    # TODO(Phase 2) : if provider == "anthropic": return AnthropicLLM(...)
    raise NotImplementedError(
        f"Fournisseur LLM non implémenté : '{provider}'. "
        "Disponibles : 'mock', 'ollama'."
    )


def dumps(obj: dict) -> str:
    return json.dumps(obj, ensure_ascii=False)
