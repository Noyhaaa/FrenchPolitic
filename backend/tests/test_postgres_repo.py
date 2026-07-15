"""Test d'intégration du repository Postgres.

Opt-in : ne s'exécute que si TEST_DATABASE_URL est défini (sinon la suite reste
sans base). Crée les tables, insère un dossier via le job d'upsert, lit via le
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
    from app.data.seed import SEED_DOSSIERS, SEED_SCRUTINS
    from app.db.models import DossierRow, ScrutinRow
    from app.db.session import init_models, make_engine, make_session_factory
    from app.ingestion.sync import _upsert_dossier, _upsert_scrutin
    from app.repositories.postgres import PostgresDossierRepository

    engine = make_engine(TEST_DB)
    await init_models(engine)
    sf = make_session_factory(engine)

    # Nettoyage + insertion d'un dossier connu (données seed) et de ses votes.
    dossier = SEED_DOSSIERS[0]
    scrutins = [s for s in SEED_SCRUTINS if s.dossier_id == dossier.id]
    async with sf() as session:
        await session.execute(DossierRow.__table__.delete())
        await session.execute(ScrutinRow.__table__.delete())
        await _upsert_dossier(session, dossier)
        for s in scrutins:
            await _upsert_scrutin(session, s)
        await session.commit()

    repo = PostgresDossierRepository(sf)
    items = await repo.list()
    assert any(i.id == dossier.id for i in items)

    detail = await repo.get(dossier.id)
    assert detail is not None and detail.titre_clair == dossier.titre_clair
    assert len(detail.scrutins) == len(dossier.scrutins)

    vote = await repo.get_scrutin(scrutins[0].id)
    assert vote is not None and vote.dossier_id == dossier.id
    assert len(vote.positions_groupes) >= 1

    found = await repo.search("logement")
    assert any(i.id == dossier.id for i in found)

    await engine.dispose()
