"""Point d'entrée FastAPI.

Assemble l'application : CORS, repository (in-memory pour l'instant, Postgres en
Phase 1), et montage des routes du cœur produit.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import health, scrutins
from app.config import settings
from app.data.seed import SEED_SCRUTINS
from app.repositories import InMemoryScrutinRepository


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Construction du repository au démarrage selon la config. Les routes ne
    # dépendent que du protocole — passer de memory à postgres est transparent.
    if settings.repository_backend == "postgres":
        from app.db.session import make_engine, make_session_factory
        from app.repositories.postgres import PostgresScrutinRepository

        engine = make_engine()
        app.state.db_engine = engine
        app.state.scrutin_repository = PostgresScrutinRepository(
            make_session_factory(engine)
        )
        yield
        await engine.dispose()
    else:
        app.state.scrutin_repository = InMemoryScrutinRepository(SEED_SCRUTINS)
        yield


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.api_title,
        version=settings.api_version,
        lifespan=lifespan,
        summary="Le traducteur neutre et mobile des décisions de l'Assemblée nationale.",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.api_cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(scrutins.router)
    app.include_router(scrutins.search_router)
    return app


app = create_app()
