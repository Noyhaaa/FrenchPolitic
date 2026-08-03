"""Abstraction du fournisseur d'IA (§6 : « rester capable de changer de modèle »).

Les générateurs dépendent du protocole `LLMClient`, jamais d'un SDK concret.

⚠️ Une seule tâche passe par un modèle : ce qui est **vérifiable
déterministiquement** (thème, publics, questions citoyennes). Le résumé neutre
est composé par un gabarit (`app.ai.generation`) — d'où l'absence de
`generate_json` ici : plus aucun appelant n'attend de JSON structuré du modèle.
"""
from __future__ import annotations

import asyncio
from typing import Protocol

import httpx

from app.config import settings


class LLMClient(Protocol):
    async def generate_text(self, system: str, user: str) -> str:
        """Retourne du texte brut (tâches simples : classification, étiquette).

        Chaîne vide en cas d'échec (modèle indisponible…) — l'appelant traite
        l'absence de réponse comme « pas de résultat » (§2.5), jamais un blocage.
        """
        ...


class OllamaLLM(LLMClient):
    """Client Ollama local (§6 : modèle interchangeable, sans clé API).

    Réservé aux tâches **vérifiables par des contrôles déterministes** :
    classification de thème (liste fermée, sortie hors-liste rejetée) et
    réponses aux questions citoyennes ancrées sur l'exposé des motifs
    (`app.ai.questions` : chiffres, nature du texte, lexique, attribution —
    rejet au moindre doute). PAS pour le résumé neutre : le gabarit déterministe
    reste seul maître (cf. README §IA — un modèle local peut distordre des faits
    de façon invisible aux garde-fous lexicaux).
    """

    # Un run d'ingestion dure des heures : une erreur réseau ponctuelle (Wi-Fi,
    # modèle en cours de chargement…) ne doit pas coûter silencieusement toutes
    # les réponses d'un dossier. On réessaie avec attente croissante, et on
    # COMPTE les échecs définitifs (`echecs`) pour que le rapport de sync les
    # rende visibles — un échec LLM est indistinguable d'une réponse vide sinon.
    _TENTATIVES = 3
    _ATTENTES_S = (2.0, 8.0)

    def __init__(
        self,
        model: str,
        base_url: str = "http://localhost:11434",
        timeout: float = 180.0,
    ) -> None:
        self._model = model
        self._url = base_url.rstrip("/")
        self._timeout = timeout
        self.echecs = 0

    # Un serveur distant peut répondre lentement au premier appel (modèle froid,
    # PC qui sort de veille) : le health-check réessaie avant de condamner tout
    # le run au mode sans-LLM. Timeout large, quelques essais espacés.
    _HEALTH_TENTATIVES = 4
    _HEALTH_ATTENTES_S = (2.0, 5.0, 10.0)
    _HEALTH_TIMEOUT_S = 15.0

    async def disponible(self) -> bool:
        """Le serveur Ollama répond-il ? (health-check avant un long run).

        Réessaie plusieurs fois : un unique échec ponctuel (Ollama froid, PC en
        sortie de veille) ne doit pas basculer tout le run en mode sans-LLM."""
        for tentative in range(self._HEALTH_TENTATIVES):
            try:
                async with httpx.AsyncClient(timeout=self._HEALTH_TIMEOUT_S) as c:
                    resp = await c.get(f"{self._url}/api/tags")
                    resp.raise_for_status()
                return True
            except httpx.HTTPError:
                if tentative < len(self._HEALTH_ATTENTES_S):
                    await asyncio.sleep(self._HEALTH_ATTENTES_S[tentative])
        return False

    async def _avec_retries(self, system: str, user: str, *, json_format: bool) -> str:
        for tentative in range(self._TENTATIVES):
            try:
                return await self._generate(system, user, json_format=json_format)
            except httpx.HTTPError:
                if tentative < len(self._ATTENTES_S):
                    await asyncio.sleep(self._ATTENTES_S[tentative])
        self.echecs += 1
        return ""  # Ollama indisponible malgré les retries → pas de résultat (§2.5)

    async def _generate(self, system: str, user: str, *, json_format: bool) -> str:
        payload: dict = {
            "model": self._model,
            "system": system,
            "prompt": user,
            "stream": False,
            # Coupe la chaîne de pensée des modèles « thinking » (qwen3…) :
            # on veut la réponse seule. Sans effet sur les autres (mistral…).
            "think": False,
            "options": {"temperature": 0},  # déterministe pour une tâche de tri
        }
        if json_format:
            payload["format"] = "json"
        async with httpx.AsyncClient(timeout=self._timeout) as c:
            resp = await c.post(f"{self._url}/api/generate", json=payload)
            resp.raise_for_status()
            return (resp.json().get("response") or "").strip()

    async def generate_text(self, system: str, user: str) -> str:
        return await self._avec_retries(system, user, json_format=False)


def get_llm_client() -> LLMClient:
    """Fabrique le client selon la configuration.

    ⚠️ `LLM_PROVIDER=mock` ne désigne PAS un client : c'est la sentinelle
    « pas de LLM du tout ». Les appelants la testent eux-mêmes avant d'appeler
    (`get_llm_client() if settings.llm_provider != "mock" else None`, cf.
    `ingestion/run.py` et `ingestion/lois.py`) et les tests la forcent
    (`tests/conftest.py`), de sorte que cette fonction n'est jamais atteinte
    avec « mock ». Elle lève donc plutôt que de rendre un client muet, qui
    ferait passer un run sans modèle pour un run avec modèle.
    """
    provider = settings.llm_provider.lower()
    if provider == "ollama":
        return OllamaLLM(settings.llm_model, settings.llm_base_url)
    if provider == "mock":
        raise NotImplementedError(
            "LLM_PROVIDER='mock' signifie « pas de LLM » : l'appelant doit "
            "garder le test `settings.llm_provider != \"mock\"` avant d'appeler "
            "get_llm_client()."
        )
    raise NotImplementedError(
        f"Fournisseur LLM non implémenté : '{provider}'. "
        "Disponibles : 'ollama' (ou 'mock' pour désactiver le LLM)."
    )
