"""Configuration de l'application, chargée depuis l'environnement / .env."""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_prefix="", extra="ignore"
    )

    app_env: str = "dev"
    api_title: str = "frenchpolitics"
    api_version: str = "0.1.0"

    # Origines autorisées pour l'app mobile (Metro / Expo web en dev).
    api_cors_origins: list[str] = [
        "http://localhost:8081",
        "http://localhost:19006",
        "http://localhost:3000",
    ]

    # Choix de la source de données : "memory" (seed) ou "postgres" (ingéré).
    repository_backend: str = "memory"

    # Branchées en Phase 1/2 (voir .env.example). Vides = mode mock.
    database_url: str | None = None
    an_opendata_base_url: str = "https://www.assemblee-nationale.fr/dyn/opendata"
    legifrance_client_id: str | None = None
    legifrance_client_secret: str | None = None

    # Génération IA (Phase 2).
    llm_provider: str = "mock"
    llm_model: str = "claude-sonnet-5"
    anthropic_api_key: str | None = None


settings = Settings()
