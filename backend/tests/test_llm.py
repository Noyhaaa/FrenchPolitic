"""Tests du client LLM Ollama : health-check résilient et retries silencieux."""
from __future__ import annotations

import httpx
import pytest

from app.ai import llm as llm_module
from app.ai.llm import OllamaLLM


class _FakeClient:
    """Faux httpx.AsyncClient : rejoue une file de résultats (exception ou
    réponse) pour `get`/`post`, quel que soit l'argument."""

    file: list = []

    def __init__(self, *a, **k) -> None:
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a) -> None:
        return None

    async def get(self, *a, **k):
        return self._prochain()

    async def post(self, *a, **k):
        return self._prochain()

    def _prochain(self):
        resultat = type(self).file.pop(0)
        if isinstance(resultat, Exception):
            raise resultat
        return resultat


class _Resp:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


@pytest.fixture(autouse=True)
def _sans_attente(monkeypatch):
    # Pas de vraies temporisations dans les tests.
    async def _noop(_):
        return None

    monkeypatch.setattr(llm_module.asyncio, "sleep", _noop)
    monkeypatch.setattr(llm_module.httpx, "AsyncClient", _FakeClient)
    _FakeClient.file = []
    yield


async def test_health_check_reessaie_puis_reussit():
    # Deux échecs transitoires puis une réponse OK → disponible malgré tout.
    _FakeClient.file = [
        httpx.ConnectError("nap"),
        httpx.ConnectError("nap"),
        _Resp({"models": []}),
    ]
    assert await OllamaLLM("m", "http://x").disponible() is True


async def test_health_check_abandonne_apres_les_tentatives():
    _FakeClient.file = [httpx.ConnectError("down")] * 4
    assert await OllamaLLM("m", "http://x").disponible() is False


async def test_generate_text_reessaie_puis_reussit_sans_incrementer_echecs():
    _FakeClient.file = [
        httpx.ConnectError("nap"),
        _Resp({"response": "  Bonjour  "}),
    ]
    llm = OllamaLLM("m", "http://x")
    assert await llm.generate_text("sys", "user") == "Bonjour"
    assert llm.echecs == 0


async def test_generate_text_echec_definitif_incremente_echecs():
    _FakeClient.file = [httpx.ConnectError("down")] * 3
    llm = OllamaLLM("m", "http://x")
    assert await llm.generate_text("sys", "user") == ""
    assert llm.echecs == 1
