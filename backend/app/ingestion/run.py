"""CLI d'ingestion (Assemblée nationale + Sénat).

Exemples :
    python -m app.ingestion.run --limit 300     # 300 scrutins les plus récents
    python -m app.ingestion.run                 # toute la législature
    python -m app.ingestion.run --sans-senat    # Assemblée seule

Nécessite DATABASE_URL (voir .env). Crée les tables si absentes.
"""
from __future__ import annotations

import argparse
import asyncio
from datetime import date

from app.ai.llm import get_llm_client
from app.config import settings
from app.db.session import init_models, make_engine, make_session_factory
from app.ingestion.assemblee import AssembleeOpenDataClient
from app.ingestion.senat import SenatOpenDataClient, session_pour
from app.ingestion.sync import SyncJob


async def _main(
    limit: int | None, legislature: int, session_senat: int | None, avec_senat: bool
) -> None:
    engine = make_engine()
    await init_models(engine)
    # LLM optionnel (classification de thème) : actif seulement si configuré
    # (LLM_PROVIDER=ollama). En mode « mock », on reste sur l'heuristique.
    llm = get_llm_client() if settings.llm_provider != "mock" else None

    def _on_progress(i: int, total: int, titre: str) -> None:
        print(f"  [{i}/{total}] {titre[:70]}")

    if session_senat is None:
        aujourdhui = date.today()
        session_senat = session_pour(aujourdhui.year, aujourdhui.month)

    job = SyncJob(
        make_session_factory(engine),
        client=AssembleeOpenDataClient(legislature=legislature),
        llm=llm,
        on_progress=_on_progress,
        client_senat=SenatOpenDataClient(session=session_senat) if avec_senat else None,
    )
    llm_info = f"LLM={settings.llm_provider}:{settings.llm_model}" if llm else "LLM=off"
    senat_info = f"Sénat=session {session_senat}" if avec_senat else "Sénat=off"
    print(
        f"Ingestion (législature {legislature}, limit={limit}, "
        f"{llm_info}, {senat_info})…"
    )
    report = await job.run(limit=limit)
    await engine.dispose()

    print(
        f"Terminé : {report.dossiers_upserts} dossiers "
        f"({report.scrutins_vus} scrutins vus), {report.groupes} groupes, "
        f"{report.deputes} députés ({report.portraits} photos, "
        f"{report.votes_deputes} votes nominatifs), "
        f"{report.exposes_recuperes} exposés des motifs récupérés "
        f"(dont {report.exposes_senat} via le Sénat), "
        f"{report.dispositifs_recuperes} dispositifs récupérés, "
        f"{report.themes_reclasses} thèmes reclassés, "
        f"{report.publics_classes} publics concernés classés, "
        f"{report.questions_generees} questions citoyennes générées "
        f"(dont {report.changements_factuels} « ce que ça change » depuis le "
        f"texte officiel), "
        f"{report.questions_amendements_generees} questions d'amendement générées, "
        f"{report.desaccords_generes} désaccords (débats) reliés, "
        f"{report.amendements_enrichis} amendements enrichis (contenu), "
        f"{report.initiatives} dossiers dont on sait qui porte le texte, "
        f"{report.etats} dossiers dont on sait où en est le texte, "
        f"{report.textes_adoptes} lois avec leur texte voté "
        f"(dont {report.lois_lues} lues, source de la Q4), "
        f"{report.rapports} rapports de commission liés."
    )
    if report.scrutins_senat or report.senateurs:
        print(
            f"  Sénat : {report.scrutins_senat} scrutins "
            f"({report.scrutins_senat_joints} rattachés à un dossier de "
            f"l'Assemblée, {report.dossiers_sans_ref_an} sans dossier AN "
            f"retrouvé → « SEN-… »), {report.senateurs} sénateurs."
        )
        print(
            "          Un texte encore au Sénat apparaît dans le fil même sans "
            "vote de l'Assemblée :\n"
            "          l'AN enregistre le dossier dès le dépôt, donc le "
            "rattachement réussit le plus souvent."
        )
    if report.dossiers_orphelins_supprimes:
        print(
            f"  {report.dossiers_orphelins_supprimes} dossier(s) orphelin(s) "
            "supprimé(s) (votes migrés vers leur vrai dossier)."
        )
    if report.conduites_de_seance_ecartees:
        print(
            f"  {report.conduites_de_seance_ecartees} vote(s) de conduite de "
            "séance écarté(s) du fil (suspension, seconde délibération)."
        )
    if report.abrevs_non_resolues:
        # Fuite mesurée (§7.4) : abréviation de groupe au CR non résolue par
        # l'annuaire AMO → à ajouter à `_ALIAS_ABBREV` sur preuve, sans deviner.
        print(
            "⚠ abréviations de groupe non résolues (désaccord) : "
            + ", ".join(sorted(report.abrevs_non_resolues))
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
    parser = argparse.ArgumentParser(
        description="Ingestion open data Assemblée nationale + Sénat"
    )
    parser.add_argument("--limit", type=int, default=None, help="Nb de scrutins récents")
    parser.add_argument("--legislature", type=int, default=17)
    parser.add_argument(
        "--session-senat",
        type=int,
        default=None,
        help="Année de DÉBUT de session du Sénat (oct.→sept.) ; par défaut, la session en cours",
    )
    parser.add_argument(
        "--sans-senat",
        action="store_true",
        help="N'ingérer que l'Assemblée nationale",
    )
    args = parser.parse_args()
    asyncio.run(
        _main(args.limit, args.legislature, args.session_senat, not args.sans_senat)
    )


if __name__ == "__main__":
    main()
