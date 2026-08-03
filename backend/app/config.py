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

    # Base ingérée (voir .env.example). Vide = repository "memory" seul.
    database_url: str | None = None

    # Génération IA. ⚠️ « mock » ne désigne pas un client : c'est la sentinelle
    # « pas de LLM du tout », testée par les appelants avant qu'ils n'appellent
    # `get_llm_client()` (cf. `app.ai.llm`). Seul « ollama » est implémenté —
    # le résumé neutre, lui, n'est jamais produit par un modèle.
    llm_provider: str = "mock"  # "mock" (= aucun LLM) | "ollama"
    llm_model: str = "mistral-small:24b"
    llm_base_url: str = "http://localhost:11434"  # Ollama local

    # Comptes utilisateurs. Le secret signe les jetons de session : sans lui,
    # aucun jeton émis ne peut être vérifié. Absent en dev → un secret éphémère
    # est tiré au démarrage (les jetons ne survivent alors pas à un
    # redémarrage, ce qui est le comportement attendu en local) ; absent
    # ailleurs → l'application refuse de démarrer (cf. app.security).
    jwt_secret: str | None = None
    # Durée de validité d'un jeton (30 jours) : l'app mobile le garde et
    # l'envoie à chaque requête de compte, il n'y a pas de rafraîchissement.
    jwt_ttl_heures: int = 720


settings = Settings()
