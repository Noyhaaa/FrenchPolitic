"""Recalcule l'indice de division des scrutins DÉJÀ en base.

    python -m app.ingestion.divisions            # applique
    python -m app.ingestion.divisions --dry-run  # montre le classement sans écrire

L'indice ordonne la rangée « Les votes les plus disputés » de l'accueil. Il est
posé à l'ingestion (`_upsert_scrutin`), mais les scrutins ingérés avant son
introduction ont la colonne à `NULL` — donc absents de la rangée. Cette commande
les rattrape sans réingérer : le calcul (`app/domain/division.py`) ne lit que les
décomptes déjà stockés dans le payload. Ni réseau, ni LLM.

À rejouer aussi quand les poids du calcul changent : c'est le seul moyen de faire
suivre la base sans un run complet. Idempotent.
"""
from __future__ import annotations

import argparse
import asyncio

from sqlalchemy import select

from app.db.models import ScrutinRow
from app.db.session import make_engine, make_session_factory
from app.domain.division import division
from app.schemas import Scrutin

# Aperçu affiché en fin de commande : de quoi vérifier d'un coup d'œil que le
# haut du classement est bien composé de votes réellement serrés.
_APERCU = 8


async def _main(dry_run: bool) -> None:
    engine = make_engine()
    session_factory = make_session_factory(engine)

    classes = non_classables = inchanges = 0
    tete: list[tuple[float, str, str, str]] = []

    async with session_factory() as session:
        for row in (await session.execute(select(ScrutinRow))).scalars().all():
            scrutin = Scrutin.model_validate(row.payload)
            mesure = division(
                scrutin.resultat,
                scrutin.positions_groupes,
                scrutin.chambre,
                objet=scrutin.objet,
                scrutin_public=scrutin.scrutin_public,
            )
            indice = mesure.indice if mesure else None
            if mesure is None:
                non_classables += 1
            else:
                classes += 1
                resultat = scrutin.resultat
                tete.append(
                    (
                        mesure.indice,
                        scrutin.date,
                        f"{resultat.pour}/{resultat.contre}/{resultat.abstention}",
                        scrutin.objet[:64],
                    )
                )
            if row.indice_division == indice:
                inchanges += 1
            row.indice_division = indice

        if dry_run:
            await session.rollback()
        else:
            await session.commit()

    await engine.dispose()

    verbe = "seraient classés" if dry_run else "classés"
    print(
        f"{classes} scrutin(s) {verbe}, {non_classables} non classable(s) "
        f"(main levée ou trop peu de votants), {inchanges} déjà à jour."
    )
    tete.sort(reverse=True)
    if tete:
        print(f"\nTête du classement (pour/contre/abstention) :")
        for indice, jour, decomptes, objet in tete[:_APERCU]:
            print(f"  {indice:.3f}  {jour}  {decomptes:>14}  {objet}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="calcule et affiche le classement sans écrire en base",
    )
    args = parser.parse_args()
    asyncio.run(_main(args.dry_run))


if __name__ == "__main__":
    main()
