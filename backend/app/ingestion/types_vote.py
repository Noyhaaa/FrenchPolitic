"""Renseigne la FORME de chaque scrutin sur les votes DÉJÀ en base.

    python -m app.ingestion.types_vote            # applique
    python -m app.ingestion.types_vote --dry-run  # montre la répartition sans écrire

« 42 voix contre 0 » : pourquoi seulement 42 ? L'archive répond depuis toujours —
`typeVote.codeTypeVote` — et l'ingestion ne le lisait pas. Un *scrutin public
ordinaire* se tient en séance parmi les députés alors présents (médiane
132 votants), un *scrutin public solennel* est annoncé à l'avance (médiane 528).

Et surtout : une **motion de censure** ne recense que les voix FAVORABLES
(art. 49 de la Constitution). La formule générale, qui met le camp gagnant en
premier, écrivait donc « rejeté par 0 voix contre 267 » — l'inverse du fait,
puisque 267 députés avaient voté POUR la censure. Cette commande recompose donc
aussi les deux phrases qui citaient ce décompte : la Q3 et la phrase 3 du résumé.

Elle ne télécharge que l'archive des **scrutins**. Ni dossiers, ni PDF, ni LLM :
tout ce qu'elle recompose est déterministe. Idempotente.
"""
from __future__ import annotations

import argparse
import asyncio
from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

from app.ai.gabarit import phrase_vote_decisif
from app.ai.questions import _vote_decisif, phrase_resultat
from app.db.models import DossierRow, ScrutinRow
from app.db.session import make_engine, make_session_factory
from app.ingestion.assemblee import AssembleeOpenDataClient
from app.domain.enums import TypeVote
from app.ingestion.normalize import to_int, type_vote
from app.schemas import Dossier, Scrutin

# Le `source_id` de la phrase du résumé qui cite le décompte du vote décisif.
_SOURCE_VOTE = "vote_ensemble"


def _formes_par_uid(
    bruts: list[dict],
) -> dict[str, tuple[TypeVote | None, int | None]]:
    """uid de scrutin → (forme du scrutin, suffrages requis), depuis l'archive."""
    formes: dict[str, tuple[TypeVote | None, int | None]] = {}
    for brut in bruts:
        s = brut.get("scrutin") or brut
        uid = s.get("uid")
        if not uid:
            continue
        forme = type_vote((s.get("typeVote") or {}).get("codeTypeVote"))
        requis = to_int((s.get("syntheseVote") or {}).get("nbrSuffragesRequis")) or None
        formes[str(uid)] = (forme, requis)
    return formes


async def _main(dry_run: bool, legislature: int) -> None:
    client = AssembleeOpenDataClient(legislature=legislature)
    print(f"Téléchargement de l'archive des scrutins (législature {legislature})…")
    formes = _formes_par_uid(await client.download_scrutins())
    print(f"{len(formes)} scrutin(s) dans l'archive.")

    engine = make_engine()
    session_factory = make_session_factory(engine)
    repartition: Counter[str] = Counter()
    bilan: Counter[str] = Counter()

    async with session_factory() as session:
        # 1) La table `scrutin` : le détail servi par la fiche vote.
        for row in (await session.execute(select(ScrutinRow))).scalars().all():
            forme, requis = formes.get(row.id, (None, None))
            repartition[forme.value if forme else "inconnu (Sénat, hors archive)"] += 1
            if forme is None and requis is None:
                continue
            scrutin = Scrutin.model_validate(row.payload)
            if scrutin.type_vote is forme and scrutin.suffrages_requis == requis:
                bilan["scrutins déjà à jour"] += 1
                continue
            payload = dict(row.payload)
            payload["typeVote"] = forme.value if forme else None
            payload["suffragesRequis"] = requis
            row.payload = payload
            flag_modified(row, "payload")
            bilan["scrutins mis à jour"] += 1

        # 2) Les dossiers : leurs `ScrutinResume` portent la même forme, et deux
        #    phrases en dépendent — la Q3 et la phrase 3 du résumé. Les deux sont
        #    déterministes, donc simplement recomposées (aucun appel au modèle).
        for row in (await session.execute(select(DossierRow))).scalars().all():
            dossier = Dossier.model_validate(row.payload)
            avant = dossier.model_dump(mode="json", by_alias=True)
            for resume_scrutin in dossier.scrutins:
                forme, requis = formes.get(resume_scrutin.id, (None, None))
                if forme is not None:
                    resume_scrutin.type_vote = forme
                if requis is not None:
                    resume_scrutin.suffrages_requis = requis

            if dossier.resume.questions is not None:
                dossier.resume.questions.resultat = phrase_resultat(dossier.scrutins)

            # La phrase 3 du résumé, et elle seule : régénérer tout le résumé
            # emporterait les publics concernés et les questions acquis par
            # ailleurs. `phrase_vote_decisif` n'a besoin que de l'objet, du
            # statut, du résultat et de la forme — tous portés par le résumé de
            # scrutin, donc sans une lecture de plus dans la table `scrutin`.
            decisif = _vote_decisif(dossier.scrutins)
            for phrase in dossier.resume.resume:
                if phrase.source_id != _SOURCE_VOTE or decisif is None:
                    continue
                recomposee = phrase_vote_decisif(decisif)
                if recomposee and recomposee != phrase.phrase:
                    phrase.phrase = recomposee
                    bilan["phrases de résumé recomposées"] += 1

            apres = dossier.model_dump(mode="json", by_alias=True)
            if apres == avant:
                bilan["dossiers déjà à jour"] += 1
                continue
            row.payload = apres
            bilan["dossiers mis à jour"] += 1

        if dry_run:
            await session.rollback()
        else:
            await session.commit()

    await engine.dispose()

    verbe = "seraient appliqués" if dry_run else "appliqués"
    print(f"\nChangements {verbe} :")
    for libelle, n in bilan.most_common():
        print(f"  {n:5d}  {libelle}")
    print("\nRépartition des formes de scrutin :")
    for forme, n in repartition.most_common():
        print(f"  {n:5d}  {forme}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run", action="store_true", help="affiche le bilan sans écrire"
    )
    parser.add_argument("--legislature", type=int, default=17)
    args = parser.parse_args()
    asyncio.run(_main(args.dry_run, args.legislature))


if __name__ == "__main__":
    main()
