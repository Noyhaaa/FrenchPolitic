"""Reformatage du titre d'affichage et de l'accroche des dossiers déjà en base.

    python -m app.ingestion.reformater            # applique
    python -m app.ingestion.reformater --dry-run  # montre sans écrire

Recalcule, depuis le payload déjà stocké :
  - `titre_clair` (colonne, payload, et `resume.titreClair` qui porte le titre de
    la fiche) via `titre_court` ;
  - `accroche` (colonne + payload) via `accroche_depuis_q1`, depuis la Q1 déjà
    validée — aucune génération, aucun appel LLM, aucun réseau ;
  - `search_index` via `index_recherche` — la MÊME fonction qu'à l'ingestion,
    donc titres + accroche + thème **et** les réponses Q1/Q4 et les publics
    concernés (§3.3 : c'est là que vit le vocabulaire du lecteur).

Sans cette commande, le nouveau format n'apparaîtrait qu'après une ingestion
complète (plusieurs heures). Idempotent : relancer ne change plus rien.
"""
from __future__ import annotations

import argparse
import asyncio

from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

from app.ai.questions import accroche_depuis_q1
from app.db.models import DossierRow
from app.db.session import make_engine, make_session_factory
from app.domain.recherche import index_recherche
from app.ingestion.normalize import titre_court
from app.schemas import Dossier


async def _main(dry_run: bool) -> None:
    engine = make_engine()
    session_factory = make_session_factory(engine)

    titres, accroches, masquees = 0, 0, 0
    async with session_factory() as session:
        rows = (await session.execute(select(DossierRow))).scalars().all()
        for row in rows:
            payload = dict(row.payload or {})
            resume = dict(payload.get("resume") or {})

            titre = titre_court(row.titre_officiel)
            if titre != row.titre_clair:
                titres += 1
            questions = resume.get("questions") or {}
            accroche = accroche_depuis_q1(questions.get("pourquoi"))
            if accroche:
                accroches += 1
            else:
                masquees += 1

            payload["titreClair"] = titre
            payload["accroche"] = accroche
            if resume:
                resume["titreClair"] = titre
                payload["resume"] = resume

            row.titre_clair = titre
            row.accroche = accroche or ""
            row.payload = payload
            flag_modified(row, "payload")
            # Même fonction qu'à l'ingestion : l'index ne peut pas diverger
            # selon la porte d'entrée (c'était le cas quand la chaîne était
            # recopiée ici et dans `sync.py`).
            row.search_index = index_recherche(Dossier.model_validate(payload))

        if dry_run:
            await session.rollback()
        else:
            await session.commit()

    await engine.dispose()
    print(
        f"{len(rows)} dossiers {'analysés (dry-run)' if dry_run else 'reformatés'} : "
        f"{titres} titres raccourcis, {accroches} accroches posées, "
        f"{masquees} sans accroche (pas de Q1)."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="calcule et affiche le bilan sans écrire en base",
    )
    args = parser.parse_args()
    asyncio.run(_main(args.dry_run))


if __name__ == "__main__":
    main()
