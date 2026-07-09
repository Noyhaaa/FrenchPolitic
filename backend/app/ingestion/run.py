"""CLI d'ingestion.

Exemples :
    python -m app.ingestion.run --limit 300     # 300 scrutins les plus récents
    python -m app.ingestion.run                 # toute la législature

Nécessite DATABASE_URL (voir .env). Crée les tables si absentes.
"""
from __future__ import annotations

import argparse
import asyncio

from app.db.session import init_models, make_engine, make_session_factory
from app.ingestion.assemblee import AssembleeOpenDataClient
from app.ingestion.sync import SyncJob


async def _main(limit: int | None, legislature: int) -> None:
    engine = make_engine()
    await init_models(engine)
    job = SyncJob(
        make_session_factory(engine),
        client=AssembleeOpenDataClient(legislature=legislature),
    )
    print(f"Ingestion (législature {legislature}, limit={limit})…")
    report = await job.run(limit=limit)
    await engine.dispose()

    print(
        f"Terminé : {report.scrutins_upserts}/{report.scrutins_vus} scrutins, "
        f"{report.groupes} groupes."
    )
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
