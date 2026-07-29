"""Renseigne « qui porte le texte » sur les dossiers DÉJÀ en base.

    python -m app.ingestion.initiatives            # applique
    python -m app.ingestion.initiatives --dry-run  # montre la répartition sans écrire

L'initiative (Gouvernement, parlementaire nommé, Sénat) est posée à l'ingestion,
mais les dossiers ingérés avant son introduction ne la portent pas. Cette commande
les rattrape sans réingérer : elle ne télécharge que l'archive des **dossiers
législatifs** (~10 Mo) et lit l'identité des auteurs dans le référentiel des
parlementaires déjà en base. Ni scrutins, ni PDF, ni LLM — quelques secondes au
lieu d'un run complet.

À rejouer quand les règles de `app/ingestion/initiative.py` changent : c'est le
seul moyen de faire suivre la base sans run complet. Idempotent.
"""
from __future__ import annotations

import argparse
import asyncio
import zipfile
from collections import Counter

import httpx
from sqlalchemy import select

from app.db.models import DeputeRow, DossierRow
from app.db.session import make_engine, make_session_factory
from app.ingestion.assemblee import AssembleeOpenDataClient
from app.ingestion.initiative import (
    IdentiteAuteur,
    construire_index_initiatives,
    resoudre_initiative,
)
from app.schemas import Dossier

# Libellés d'affichage du récapitulatif, dans l'ordre où on les montre.
_ORDRE = ("gouvernement", "parlementaire", "senat")


async def _telecharger_documents(client: AssembleeOpenDataClient) -> list[dict]:
    """Documents de l'archive, législature courante + précédente (best-effort).

    Même fenêtre que le run complet : un dossier reporté après une dissolution
    garde son `dossierRef` d'origine, donc son document de dépôt est dans
    l'archive de la législature précédente.
    """
    documents = await client.download_dossiers(client.legislature)
    if client.legislature > 1:
        try:
            documents += await client.download_dossiers(client.legislature - 1)
        except (httpx.HTTPError, zipfile.BadZipFile) as exc:
            print(
                f"⚠ archive de la législature précédente non téléchargée "
                f"({type(exc).__name__}) : rattrapage limité à la courante."
            )
    return documents


async def _main(dry_run: bool, legislature: int) -> None:
    client = AssembleeOpenDataClient(legislature=legislature)
    print(f"Téléchargement de l'archive des dossiers (législature {legislature})…")
    documents = await _telecharger_documents(client)
    legislatures = (
        (legislature, legislature - 1) if legislature > 1 else (legislature,)
    )
    index = construire_index_initiatives(documents, legislatures)
    print(f"{len(index)} dossier(s) de l'archive portent une initiative lisible.")

    engine = make_engine()
    session_factory = make_session_factory(engine)
    ecrits = inchanges = sans = 0
    repartition: Counter[str] = Counter()
    nommes = 0

    async with session_factory() as session:
        # Identité des parlementaires servis par l'API : un auteur absent d'ici
        # garde son origine mais pas son nom (§2.5), et surtout pas de lien.
        identites = {
            row.id: IdentiteAuteur(
                row.nom, row.groupe_nom, row.groupe_couleur, row.portrait_url
            )
            for row in (await session.execute(select(DeputeRow))).scalars().all()
        }
        for row in (await session.execute(select(DossierRow))).scalars().all():
            # L'identifiant d'un dossier officiel EST son `dossierRef` ; les
            # dossiers reconstitués (« TXT-… »), sénatoriaux (« SEN-… ») et les
            # événements autonomes n'y figurent simplement pas.
            initiative = resoudre_initiative(index.get(row.id), identites)
            if initiative is None:
                sans += 1
                continue
            repartition[initiative.origine] += 1
            if initiative.nom:
                nommes += 1
            payload = dict(row.payload)
            nouveau = initiative.model_dump(mode="json", by_alias=True)
            if payload.get("initiative") == nouveau:
                inchanges += 1
                continue
            dossier = Dossier.model_validate(payload)
            dossier.initiative = initiative
            row.payload = dossier.model_dump(mode="json", by_alias=True)
            ecrits += 1

        if dry_run:
            await session.rollback()
        else:
            await session.commit()

    await engine.dispose()

    verbe = "seraient mis à jour" if dry_run else "mis à jour"
    print(
        f"\n{ecrits} dossier(s) {verbe}, {inchanges} déjà à jour, "
        f"{sans} sans initiative (masquée sur la fiche, §2.5)."
    )
    total = sum(repartition.values())
    if total:
        print(f"\nRépartition ({total} dossiers, dont {nommes} avec un nom) :")
        for origine in _ORDRE:
            if repartition[origine]:
                print(f"  {repartition[origine]:4d}  {origine}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="affiche la répartition sans écrire en base",
    )
    parser.add_argument("--legislature", type=int, default=17)
    args = parser.parse_args()
    asyncio.run(_main(args.dry_run, args.legislature))


if __name__ == "__main__":
    main()
