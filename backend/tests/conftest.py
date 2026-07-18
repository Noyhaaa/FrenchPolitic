from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import create_app


@pytest.fixture(autouse=True)
def _llm_mock():
    # Aucun test ne doit dépendre du réseau : on force le LLM « mock » quelle
    # que soit la config .env (qui peut pointer sur un Ollama distant en dev).
    previous = settings.llm_provider
    settings.llm_provider = "mock"
    try:
        yield
    finally:
        settings.llm_provider = previous


@pytest.fixture
def client() -> TestClient:
    # Les tests s'appuient sur les données seed : on force le backend « memory »
    # quelle que soit la config .env (qui peut pointer sur Postgres en dev).
    previous = settings.repository_backend
    settings.repository_backend = "memory"
    try:
        # TestClient déclenche le lifespan (construction du repository).
        with TestClient(create_app()) as c:
            yield c
    finally:
        settings.repository_backend = previous
