"""Test d'intégration du repository Postgres.

Opt-in : ne s'exécute que si TEST_DATABASE_URL est défini (sinon la suite reste
sans base). Crée les tables, insère un scrutin via le job d'upsert, lit via le
repository.

    TEST_DATABASE_URL=postgresql+asyncpg://localhost:5432/decrypte_test pytest -q
"""
from __future__ import annotations

import os

import pytest

TEST_DB = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not TEST_DB, reason="TEST_DATABASE_URL non défini"
)


async def test_upsert_puis_lecture():
    from app.data.seed import SEED_SCRUTINS
    from app.db.models import ScrutinRow
    from app.db.session import init_models, make_engine, make_session_factory
    from app.ingestion.sync import _upsert_scrutin
    from app.repositories.postgres import PostgresScrutinRepository

    engine = make_engine(TEST_DB)
    await init_models(engine)
    sf = make_session_factory(engine)

    # Nettoyage + insertion d'un scrutin connu (données seed).
    scrutin = SEED_SCRUTINS[0]
    async with sf() as session:
        await session.execute(ScrutinRow.__table__.delete())
        await _upsert_scrutin(session, scrutin)
        await session.commit()

    repo = PostgresScrutinRepository(sf)
    items = await repo.list()
    assert any(i.id == scrutin.id for i in items)

    detail = await repo.get(scrutin.id)
    assert detail is not None and detail.titre_clair == scrutin.titre_clair

    found = await repo.search("logement")
    assert any(i.id == scrutin.id for i in found)

    await engine.dispose()
