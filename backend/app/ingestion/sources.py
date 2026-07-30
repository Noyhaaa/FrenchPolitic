"""Recompose « les documents du dossier » sur les dossiers DÉJÀ en base.

    python -m app.ingestion.sources            # applique
    python -m app.ingestion.sources --dry-run  # montre le bilan sans écrire

La fiche d'un dossier n'affichait qu'**une** source, la page du dossier
législatif : mesuré, 313 dossiers sur 328 n'en avaient pas d'autre. Les autres
documents existaient pourtant déjà dans le payload, chacun enfermé dans la carte
qui s'en sert (texte déposé, compte rendu, texte voté, Légifrance) — et le
rapport de commission, lui, n'était pas ingéré du tout.

Cette commande rattrape les deux sans réingérer : elle télécharge la seule
archive des **dossiers législatifs** (~10 Mo) pour y lire les rapports, vérifie
leurs URLs (HEAD), puis recompose la liste de tous les dossiers. Ni scrutins, ni
PDF, ni LLM.

À rejouer quand l'ordre ou les libellés de `app.domain.sources` changent. La
composition étant idempotente, un second passage ne change rien.
"""
from __future__ import annotations

import argparse
import asyncio
import zipfile
from collections import Counter

import httpx
from sqlalchemy import select

from app.db.models import DossierRow
from app.db.session import make_engine, make_session_factory
from app.domain.enums import TypeSource
from app.domain.sources import documents_du_dossier
from app.ingestion.assemblee import AssembleeOpenDataClient
from app.ingestion.rapports import construire_index_rapports, verifier_rapports
from app.schemas import Dossier


async def _telecharger_documents(
    client: AssembleeOpenDataClient,
) -> tuple[list[dict], tuple[int, ...]]:
    """Documents des dossiers, législature courante + précédente (best-effort).

    Même fenêtre que le run complet : un dossier reporté après une dissolution
    garde son `dossierRef` d'origine, donc ses rapports vivent dans l'archive de
    la législature précédente."""
    documents, _ = await client.download_dossiers_complet(client.legislature)
    legislatures = (client.legislature,)
    if client.legislature > 1:
        try:
            precedents, _ = await client.download_dossiers_complet(
                client.legislature - 1
            )
            documents += precedents
            legislatures = (client.legislature, client.legislature - 1)
        except (httpx.HTTPError, zipfile.BadZipFile) as exc:
            print(
                f"⚠ archive de la législature précédente non téléchargée "
                f"({type(exc).__name__}) : rapports limités à la courante."
            )
    return documents, legislatures


async def _main(dry_run: bool, legislature: int, sans_rapports: bool) -> None:
    index_rapports: dict[str, list[str]] = {}
    if not sans_rapports:
        client = AssembleeOpenDataClient(legislature=legislature)
        print(f"Téléchargement de l'archive des dossiers (législature {legislature})…")
        documents, legislatures = await _telecharger_documents(client)
        index_rapports = construire_index_rapports(documents, legislatures)
        print(
            f"{sum(len(v) for v in index_rapports.values())} rapport(s) de "
            f"commission sur {len(index_rapports)} dossier(s) dans l'archive."
        )

    engine = make_engine()
    session_factory = make_session_factory(engine)
    bilan: Counter[str] = Counter()
    liens_par_dossier: list[int] = []

    async with session_factory() as session:
        rows = (await session.execute(select(DossierRow))).scalars().all()
        for i, row in enumerate(rows, start=1):
            dossier = Dossier.model_validate(row.payload)
            avant = dossier.model_dump(mode="json", by_alias=True)

            # Les rapports : vérifiés une fois, réutilisés ensuite. Un dossier
            # dont l'archive ne cite aucun rapport garde ceux déjà en base — ne
            # rien trouver n'est pas la preuve qu'ils n'existent plus (§2.5).
            uids = index_rapports.get(row.id)
            if uids and len(uids) != len(dossier.rapports_commission):
                print(f"  [{i}/{len(rows)}] {row.id} — {len(uids)} rapport(s)…")
                dossier.rapports_commission = await verifier_rapports(uids)
                bilan["rapports vérifiés"] += len(dossier.rapports_commission)
                bilan["rapports non résolus"] += len(uids) - len(
                    dossier.rapports_commission
                )
            if dossier.rapports_commission:
                bilan["dossiers avec rapport"] += 1

            # Le compte rendu de séance était typé `texte` faute d'y avoir
            # regardé de près ; c'est un débat, et l'app lui associe 💬. Sans
            # cette reprise, la liste alignerait six 📄 identiques.
            questions = dossier.resume.questions
            if questions and questions.desaccord_source is not None:
                if questions.desaccord_source.type is not TypeSource.debats:
                    questions.desaccord_source.type = TypeSource.debats
                    bilan["comptes rendus retypés"] += 1

            dossier.sources = documents_du_dossier(dossier)
            liens_par_dossier.append(len(dossier.sources))

            apres = dossier.model_dump(mode="json", by_alias=True)
            if apres == avant:
                bilan["déjà à jour"] += 1
                continue
            row.payload = apres
            bilan["dossiers mis à jour"] += 1

        if dry_run:
            await session.rollback()
        else:
            await session.commit()

    await engine.dispose()

    total = len(liens_par_dossier)
    verbe = "seraient" if dry_run else "ont été"
    print(f"\n{total} dossier(s) parcouru(s) ; les listes {verbe} recomposées.")
    for libelle, n in bilan.most_common():
        print(f"  {n:5d}  {libelle}")
    if total:
        liens = sum(liens_par_dossier)
        seuls = sum(1 for n in liens_par_dossier if n <= 1)
        print(
            f"\n{liens} lien(s) au total, soit {liens / total:.2f} par dossier "
            f"({seuls} dossier(s) encore réduits à une seule source)."
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run", action="store_true", help="affiche le bilan sans écrire"
    )
    parser.add_argument(
        "--sans-rapports",
        action="store_true",
        help="recompose depuis la base seule (ni archive, ni vérification HEAD)",
    )
    parser.add_argument("--legislature", type=int, default=17)
    args = parser.parse_args()
    asyncio.run(_main(args.dry_run, args.legislature, args.sans_rapports))


if __name__ == "__main__":
    main()
