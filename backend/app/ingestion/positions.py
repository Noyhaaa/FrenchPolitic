"""Recalcule la position majoritaire des groupes DÉJÀ en base, et ce qui en dépend.

    python -m app.ingestion.positions            # applique
    python -m app.ingestion.positions --dry-run  # compte sans écrire

La position d'un groupe se déduit de ses décomptes (`position_par_decompte`) : le
champ `positionMajoritaire` de l'AN les contredit sur 3 % des groupes. Les
scrutins ingérés avant cette règle portent le champ publié ; cette commande les
rattrape sans réingérer, puis recompose ce qui lit la position :

- le résumé neutre (phrase « Les groupes … ont majoritairement voté pour ») ;
- le **sens** des arguments de la Q2, recomposé depuis le scrutin d'ancrage
  comme à chaque run (l'argument validé est gardé, seul le sens est un fait).

Ni réseau, ni LLM. À enchaîner avec `divisions` (l'indice lit les positions) et
`deputes` (« contre son groupe »). Idempotent.
"""
from __future__ import annotations

import argparse
import asyncio
from collections import defaultdict

from sqlalchemy import select

from app.ai.faits import construire_faits
from app.ai.generation import generer_resume
from app.db.models import DossierRow, ScrutinRow
from app.db.session import make_engine, make_session_factory
from app.ingestion.normalize import position_par_decompte
from app.ingestion.sync import _ancre_du_desaccord, _positions_documentees
from app.schemas import Dossier, Scrutin


def _recaler(scrutin: Scrutin) -> int:
    """Pose sur chaque groupe la position tirée de ses décomptes ; renvoie le
    nombre de groupes changés."""
    changes = 0
    for g in scrutin.positions_groupes:
        juste = position_par_decompte(g.pour, g.contre, g.abstention)
        if g.position_majoritaire is not juste:
            g.position_majoritaire = juste
            changes += 1
    return changes


async def _main(dry_run: bool) -> None:
    engine = make_engine()
    session_factory = make_session_factory(engine)

    groupes = scrutins_changes = resumes = desaccords = arguments_retires = 0

    async with session_factory() as session:
        par_dossier: dict[str, dict[str, Scrutin]] = defaultdict(dict)
        for row in (await session.execute(select(ScrutinRow))).scalars().all():
            scrutin = Scrutin.model_validate(row.payload)
            n = _recaler(scrutin)
            if n:
                groupes += n
                scrutins_changes += 1
                row.payload = scrutin.model_dump(mode="json", by_alias=True)
            par_dossier[row.dossier_id][scrutin.id] = scrutin

        for row in (await session.execute(select(DossierRow))).scalars().all():
            dossier = Dossier.model_validate(row.payload)
            votes = par_dossier.get(dossier.id, {})
            # Même ordre que `build_dossier` (le plus récent d'abord) : le vote
            # décisif et le vote d'ancrage en dépendent.
            votes_texte = [votes[s.id] for s in dossier.scrutins if s.id in votes]
            ids_texte = {s.id for s in votes_texte}
            votes_amendement = [s for i, s in votes.items() if i not in ids_texte]
            change = False

            if not dossier.resume.relu_par_humain:
                neuf = generer_resume(
                    construire_faits(
                        titre_clair=dossier.titre_clair,
                        titre_officiel=dossier.titre_officiel,
                        theme=dossier.theme,
                        votes_texte=votes_texte,
                        votes_amendement=votes_amendement,
                    )
                )
                if neuf.resume != dossier.resume.resume:
                    dossier.resume.resume = neuf.resume
                    resumes += 1
                    change = True

            q = dossier.resume.questions
            if q is not None and q.desaccord:
                ancre = _ancre_du_desaccord(votes_texte, q.desaccord_objet)
                realignes = _positions_documentees(q.desaccord, ancre) if ancre else []
                if realignes != q.desaccord:
                    arguments_retires += len(q.desaccord) - len(realignes)
                    desaccords += 1
                    change = True
                    if realignes:
                        q.desaccord = realignes
                        q.desaccord_objet = ancre.objet
                    else:
                        # Plus aucun groupe documenté : la Q2 disparaît (§2.5),
                        # comme au run qui la recomposerait.
                        q.desaccord = None
                        q.desaccord_objet = None
                        q.desaccord_source = None

            if change:
                row.payload = dossier.model_dump(mode="json", by_alias=True)

        if dry_run:
            await session.rollback()
        else:
            await session.commit()

    await engine.dispose()

    verbe = "seraient" if dry_run else "ont été"
    print(
        f"{groupes} position(s) de groupe {verbe} corrigée(s) sur "
        f"{scrutins_changes} scrutin(s) ; {resumes} résumé(s) et "
        f"{desaccords} Q2 {verbe} recomposé(s) ({arguments_retires} argument(s) "
        "retiré(s) faute de vote exprimé)."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run", action="store_true", help="compte sans écrire en base"
    )
    args = parser.parse_args()
    asyncio.run(_main(args.dry_run))


if __name__ == "__main__":
    main()
