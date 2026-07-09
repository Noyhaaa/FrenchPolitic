from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import create_app


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
