"""Reformatage du titre d'affichage et de l'accroche des dossiers déjà en base.

    python -m app.ingestion.reformater            # applique
    python -m app.ingestion.reformater --dry-run  # montre sans écrire

Recalcule, depuis le payload déjà stocké :
  - `titre_clair` (colonne, payload, et `resume.titreClair` qui porte le titre de
    la fiche) via `titre_court` ;
  - `accroche` (colonne + payload) via `accroche_depuis_q1`, depuis la Q1 déjà
    validée — aucune génération, aucun appel LLM, aucun réseau ;
  - `search_index`, qui dérive des deux.

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
from app.ingestion.normalize import titre_court
from app.utils.text import fold


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
            row.search_index = fold(
                f"{titre} {row.titre_officiel} {accroche or ''} {row.theme}"
            )

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
