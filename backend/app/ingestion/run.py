"""CLI d'ingestion.

Exemples :
    python -m app.ingestion.run --limit 300     # 300 scrutins les plus récents
    python -m app.ingestion.run                 # toute la législature

Nécessite DATABASE_URL (voir .env). Crée les tables si absentes.
"""
from __future__ import annotations

import argparse
import asyncio

from app.ai.llm import get_llm_client
from app.config import settings
from app.db.session import init_models, make_engine, make_session_factory
from app.ingestion.assemblee import AssembleeOpenDataClient
from app.ingestion.sync import SyncJob


async def _main(limit: int | None, legislature: int) -> None:
    engine = make_engine()
    await init_models(engine)
    # LLM optionnel (classification de thème) : actif seulement si configuré
    # (LLM_PROVIDER=ollama). En mode « mock », on reste sur l'heuristique.
    llm = get_llm_client() if settings.llm_provider != "mock" else None
    job = SyncJob(
        make_session_factory(engine),
        client=AssembleeOpenDataClient(legislature=legislature),
        llm=llm,
    )
    llm_info = f"LLM={settings.llm_provider}:{settings.llm_model}" if llm else "LLM=off"
    print(f"Ingestion (législature {legislature}, limit={limit}, {llm_info})…")
    report = await job.run(limit=limit)
    await engine.dispose()

    print(
        f"Terminé : {report.dossiers_upserts} dossiers "
        f"({report.scrutins_vus} scrutins vus), {report.groupes} groupes, "
        f"{report.exposes_recuperes} exposés des motifs récupérés, "
        f"{report.themes_reclasses} thèmes reclassés, "
        f"{report.questions_generees} questions citoyennes générées, "
        f"{report.desaccords_generes} désaccords (débats) reliés."
    )
    if report.llm_indisponible:
        print("⚠ LLM configuré mais injoignable : run SANS LLM (relancer quand il répond).")
    if report.llm_echecs:
        print(f"⚠ {report.llm_echecs} appel(s) LLM en échec malgré les retries.")
    if report.anomalies:
        print(f"⚠ {len(report.anomalies)} anomalie(s) de cohérence (non bloquantes) :")
        for a in report.anomalies[:10]:
            print(f"  - {a}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingestion open data Assemblée nationale")
    parser.add_argument("--limit", type=int, default=None, help="Nb de scrutins récents")
    parser.add_argument("--legislature", type=int, default=17)
    args = parser.parse_args()
    asyncio.run(_main(args.limit, args.legislature))


if __name__ == "__main__":
    main()
