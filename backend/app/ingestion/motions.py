"""Classe les MOTIONS déjà en base, pour que l'app puisse dire leur inversion.

    python -m app.ingestion.motions            # applique
    python -m app.ingestion.motions --dry-run  # montre la répartition sans écrire

Une motion de rejet préalable propose de rejeter le texte sans discuter ses
articles : voter *pour*, c'est demander sa mort, et l'*adopter*, c'est le
rejeter. Affiché sans mention, le vocabulaire du scrutin dit donc l'inverse du
fait — mesuré avant ce correctif, 8 dossiers annonçaient « Adopté » sur un texte
que la motion venait de rejeter, dont un dont c'était le seul vote.

Cette commande pose `typeMotion` sur la table `scrutin`, le recopie dans les
`ScrutinResume` des dossiers et renseigne `statutMotion` — le type de motion du
vote qui a fixé le statut du dossier, celui que le badge affiche.

⚠️ **Elle ne rattrape pas le Sénat.** Les objets de vote y sont tronqués à
120 caractères et s'ouvrent sur le numéro et l'auteur de la motion (« la motion
n° 278, présentée par Mme… ») : la clause qui dit ce qu'elle est (« tendant à
opposer la question préalable ») arrive vers le 135e caractère et n'est pas en
base. Ces scrutins se classent à l'ingestion, sur l'objet entier —
`python -m app.ingestion.senat` (~10 s) les relit.

Ni réseau, ni LLM : le classement est déterministe. Idempotente.
"""
from __future__ import annotations

import argparse
import asyncio
from collections import Counter, defaultdict

from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

from app.db.models import DossierRow, ScrutinRow
from app.db.session import make_engine, make_session_factory
from app.domain.enums import StatutScrutin, TypeMotion
from app.ingestion.normalize import type_motion
from app.schemas import Dossier


def _vote_du_statut(
    votes: list[tuple[str, StatutScrutin, TypeMotion | None]],
) -> tuple[StatutScrutin, TypeMotion | None] | None:
    """Le vote qui fixe le statut du dossier : (statut, motion) ou None.

    Même règle que `build_dossier` — le plus récent, amendements compris, et à
    date égale un vote sur le TEXTE avant une motion : une motion ne décide
    jamais du sort du texte, elle ne le fixe que faute de mieux. Quand seules des
    motions de types différents restent, on s'abstient (§2.5).
    """
    if not votes:
        return None
    recente = max(date for date, _, _ in votes)
    du_jour = [(statut, motion) for date, statut, motion in votes if date == recente]
    textes = [v for v in du_jour if v[1] is None]
    candidats = textes or du_jour
    statuts = {v[0] for v in candidats}
    motions = {v[1] for v in candidats}
    if len(statuts) > 1 or len(motions) > 1:
        return None
    return candidats[0]


async def _main(dry_run: bool) -> None:
    engine = make_engine()
    session_factory = make_session_factory(engine)
    repartition: Counter[str] = Counter()
    bilan: Counter[str] = Counter()
    # Objets qui ressemblent à une motion sans qu'on sache laquelle : c'est sur
    # cette liste-là qu'on complète `_MOTIFS_MOTION`, jamais par supposition.
    non_classes: Counter[str] = Counter()
    # Classements que seule l'ingestion pouvait faire (objet entier) et que cette
    # commande se contente de préserver.
    preservees: Counter[str] = Counter()

    async with session_factory() as session:
        # 1) La table `scrutin` — la source de vérité, seule à porter la date de
        #    TOUS les votes (les amendements d'un dossier n'en portent pas dans
        #    son payload, alors qu'ils comptent pour son statut).
        motions: dict[str, TypeMotion | None] = {}
        par_dossier: dict[
            str, list[tuple[str, StatutScrutin, TypeMotion | None]]
        ] = defaultdict(list)
        lignes = (
            await session.execute(
                select(
                    ScrutinRow.id,
                    ScrutinRow.dossier_id,
                    ScrutinRow.date,
                    ScrutinRow.chambre,
                    ScrutinRow.payload,
                )
            )
        ).all()
        for scrutin_id, dossier_id, date_vote, chambre, payload in lignes:
            objet = str(payload.get("objet") or "")
            motion = type_motion(objet)
            # ⚠️ On ne CLASSE que, on ne DÉCLASSE jamais. L'objet stocké est
            # tronqué à 120 caractères : quand l'ingestion a reconnu une motion
            # sur l'objet entier (tout le Sénat est dans ce cas), la relire ici
            # ne retrouve rien — écraser reviendrait à effacer un fait qu'on
            # n'est pas en mesure de vérifier (même doctrine que la préservation
            # de l'exposé et de l'initiative entre runs).
            if motion is None and payload.get("typeMotion"):
                motion = TypeMotion(payload["typeMotion"])
                preservees[motion.value] += 1
            motions[scrutin_id] = motion
            par_dossier[dossier_id].append(
                (date_vote, StatutScrutin(payload["statut"]), motion)
            )
            if motion is not None:
                repartition[motion.value] += 1
            elif objet.lower().lstrip().startswith("la motion"):
                # « la motion de censure » a son propre traitement (art. 49) et
                # n'est pas une motion de rejet : ce n'est pas un manque.
                if "censure" not in objet.lower():
                    non_classes[objet[:88]] += 1
                    if chambre == "senat":
                        bilan["non classés (Sénat, objet tronqué)"] += 1

            if payload.get("typeMotion") == (motion.value if motion else None):
                continue
            row = await session.get(ScrutinRow, scrutin_id)
            assert row is not None
            neuf = dict(row.payload)
            neuf["typeMotion"] = motion.value if motion else None
            row.payload = neuf
            flag_modified(row, "payload")
            bilan["scrutins mis à jour"] += 1

        # 2) Les dossiers : leurs `ScrutinResume` portent le même drapeau, et
        #    `statutMotion` qualifie le vote qui a fixé le statut du dossier.
        for row in (await session.execute(select(DossierRow))).scalars().all():
            dossier = Dossier.model_validate(row.payload)
            avant = dossier.model_dump(mode="json", by_alias=True)
            for resume_scrutin in dossier.scrutins:
                resume_scrutin.type_motion = motions.get(resume_scrutin.id)
            fixe = _vote_du_statut(par_dossier.get(dossier.id, []))
            if fixe is not None:
                statut, motion_du_statut = fixe
                # Le statut aussi peut être faux : quand une motion et le vote
                # sur l'ensemble tombent le même jour, l'ordre d'arrivée
                # tranchait (vécu : « Rejeté » sur une loi promulguée).
                if dossier.statut is not statut:
                    dossier.statut = statut
                    bilan["statuts corrigés (motion passée devant le texte)"] += 1
                dossier.statut_motion = motion_du_statut
            if dossier.statut_motion is not None:
                bilan["dossiers dont le badge nomme la motion"] += 1

            apres = dossier.model_dump(mode="json", by_alias=True)
            if apres == avant:
                continue
            row.payload = apres
            bilan["dossiers mis à jour"] += 1

        if dry_run:
            await session.rollback()
        else:
            await session.commit()

    await engine.dispose()

    verbe = "seraient appliqués" if dry_run else "appliqués"
    print(f"Changements {verbe} :")
    for libelle, n in bilan.most_common():
        print(f"  {n:5d}  {libelle}")
    print("\nMotions classées :")
    for motion_libelle, n in repartition.most_common():
        print(f"  {n:5d}  {motion_libelle}")
    if preservees:
        print("\nClassements préservés (posés à l'ingestion, objet entier) :")
        for motion_libelle, n in preservees.most_common():
            print(f"  {n:5d}  {motion_libelle}")
    if non_classes:
        print(
            "\nObjets commençant par « la motion » et NON classés "
            f"({sum(non_classes.values())}) — à examiner avant d'élargir la "
            "liste fermée :"
        )
        for objet, n in non_classes.most_common(15):
            print(f"  {n:3d}  {objet}")
        print(
            "\n  ⚠️ Les objets du Sénat sont tronqués à 120 caractères : la "
            "clause qui\n     nomme la motion n'est pas en base. Relancer "
            "`python -m app.ingestion.senat`,\n     qui classe sur l'objet "
            "entier."
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run", action="store_true", help="affiche le bilan sans écrire"
    )
    args = parser.parse_args()
    asyncio.run(_main(args.dry_run))


if __name__ == "__main__":
    main()
