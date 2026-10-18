"""Les mises au point d'un scrutin de l'Assemblée — et leur rattrapage en base.

    python -m app.ingestion.mises_au_point            # applique
    python -m app.ingestion.mises_au_point --dry-run  # compte sans écrire

Après un scrutin public, un député peut faire savoir qu'il voulait voter
autrement que ce qui a été enregistré, ou qu'un dysfonctionnement a empêché la
prise en compte de son vote. L'Assemblée publie ces déclarations avec le
scrutin (`miseAuPoint` dans l'open data) et sur sa page, « sous réserve des
dispositions de l'article 68, alinéa 4, du Règlement » : elles ne modifient ni
le vote enregistré ni le résultat. L'app les affiche donc comme un fait à côté
du vote, sans rien recalculer (« contre son groupe », portrait).

Les phrases reprennent mot pour mot les formules des pages de l'Assemblée
(relevées sur les scrutins 209, 1996, 3985, 4241, 4569, 4643, 8875 de la L17).

La commande rattrape les scrutins déjà en base sans run complet : archive des
scrutins (~27 Mo) et annuaires AMO (noms, civilités). Ni LLM. Idempotent.
"""
from __future__ import annotations

import argparse
import asyncio

from sqlalchemy import select

from app.domain.enums import PositionVote
from app.ingestion.normalize import as_list
from app.schemas import MiseAuPoint

# Clé de l'open data → (position déclarée, verbe entre guillemets ou None pour
# « n'a pas pris part au scrutin »).
_DECLARATIONS = (
    ("pours", PositionVote.pour, "voter pour"),
    ("contres", PositionVote.contre, "voter contre"),
    ("abstentions", PositionVote.abstention, "s'abstenir volontairement"),
    ("nonVotants", PositionVote.non_votant, None),
    ("nonVotantsVolontaires", PositionVote.non_votant, None),
)
# Sous-bloc `dysfonctionnement` : les clés y sont au singulier pour pour/contre.
_DYSFONCTIONNEMENTS = (
    ("pour", PositionVote.pour, "a voté « pour »"),
    ("contre", PositionVote.contre, "a voté « contre »"),
    ("abstentions", PositionVote.abstention, "a voulu « s'abstenir volontairement »"),
    ("nonVotants", PositionVote.non_votant, None),
    ("nonVotantsVolontaires", PositionVote.non_votant, None),
)
_NON_PRISE_EN_COMPTE = "Sa position de vote n'a pas pu être prise en compte."


def _acteurs_du_bloc(bloc: object) -> list[str]:
    refs: list[str] = []
    for element in as_list(bloc):
        if not isinstance(element, dict):
            continue
        for votant in as_list(element.get("votant")):
            if isinstance(votant, dict) and isinstance(votant.get("acteurRef"), str):
                refs.append(votant["acteurRef"])
    return refs


def _designation(nom: str, civ: str | None) -> str:
    return f"{civ} {nom}" if civ else nom


def phrase_mise_au_point(nom: str, civ: str | None, verbe: str | None) -> str:
    """« Mme X a fait savoir qu'elle avait voulu « voter contre ». » Sans
    civilité connue, la forme neutre que l'Assemblée emploie au pluriel
    (« ont indiqué avoir voulu »), au singulier : on ne devine pas le genre."""
    qui = _designation(nom, civ)
    if verbe is None:
        return f"{qui} n'a pas pris part au scrutin."
    if civ in ("M.", "Mme"):
        pronom = "il" if civ == "M." else "elle"
        return f"{qui} a fait savoir qu'{pronom} avait voulu « {verbe} »."
    return f"{qui} a indiqué avoir voulu « {verbe} »."


def phrase_dysfonctionnement(nom: str, civ: str | None, acte: str | None) -> str:
    """« M. X a voté « pour ». Sa position de vote n'a pas pu être prise en
    compte. » — ou « … n'a pas pris part au scrutin. » pour un non-votant."""
    qui = _designation(nom, civ)
    if acte is None:
        return f"{qui} n'a pas pris part au scrutin."
    return f"{qui} {acte}. {_NON_PRISE_EN_COMPTE}"


def extraire_mises_au_point(
    bloc: object,
    acteurs: dict[str, str] | None,
    civilites: dict[str, str] | None = None,
    deputes_connus: frozenset[str] | None = None,
) -> list[MiseAuPoint]:
    """Les déclarations du bloc `miseAuPoint` d'un scrutin (fonction pure).

    Un député absent de l'annuaire est omis : sa référence `PA…` n'est pas un
    nom (§2.5). `depute_id` n'est posé que s'il siège encore.
    """
    if not isinstance(bloc, dict) or not acteurs:
        return []
    civilites = civilites or {}
    connus = deputes_connus or frozenset()
    resultat: list[MiseAuPoint] = []

    def ajouter(ref: str, nature: str, position: PositionVote, phrase: str) -> None:
        resultat.append(
            MiseAuPoint(
                nom=acteurs[ref],
                depute_id=ref if ref in connus else None,
                nature=nature,
                position=position,
                phrase=phrase,
            )
        )

    for cle, position, verbe in _DECLARATIONS:
        for ref in _acteurs_du_bloc(bloc.get(cle)):
            if ref in acteurs:
                ajouter(
                    ref,
                    "mise_au_point",
                    position,
                    phrase_mise_au_point(acteurs[ref], civilites.get(ref), verbe),
                )
    pannes = bloc.get("dysfonctionnement")
    if isinstance(pannes, dict):
        for cle, position, acte in _DYSFONCTIONNEMENTS:
            for ref in _acteurs_du_bloc(pannes.get(cle)):
                if ref in acteurs:
                    ajouter(
                        ref,
                        "dysfonctionnement",
                        position,
                        phrase_dysfonctionnement(acteurs[ref], civilites.get(ref), acte),
                    )
    return resultat


# --- Rattrapage des scrutins déjà en base -----------------------------------


async def _main(dry_run: bool, legislature: int) -> None:
    from app.db.models import DeputeRow, ScrutinRow
    from app.db.session import make_engine, make_session_factory
    from app.ingestion.assemblee import AssembleeOpenDataClient
    from app.ingestion.organes import build_acteurs_from_amo, build_civ_from_amo
    from app.schemas import Scrutin

    client = AssembleeOpenDataClient(legislature=legislature)
    print("Téléchargement des annuaires AMO…")
    _, acteurs_bruts = await client.download_amo()
    _, historiques = await client.download_amo_historique()
    acteurs = build_acteurs_from_amo(historiques)
    acteurs.update(build_acteurs_from_amo(acteurs_bruts))
    civilites = build_civ_from_amo(historiques)
    civilites.update(build_civ_from_amo(acteurs_bruts))
    print("Téléchargement de l'archive des scrutins…")
    blocs: dict[str, object] = {}
    for brut in await client.download_scrutins():
        s = brut.get("scrutin") or {}
        if s.get("uid") and s.get("miseAuPoint"):
            blocs[s["uid"]] = s["miseAuPoint"]

    engine = make_engine()
    session_factory = make_session_factory(engine)
    ecrits = declarations = pannes = 0
    async with session_factory() as session:
        connus = frozenset(
            r for (r,) in (await session.execute(select(DeputeRow.id))).all()
        )
        lignes = (
            await session.execute(
                select(ScrutinRow).where(ScrutinRow.chambre == "assemblee")
            )
        ).scalars().all()
        for row in lignes:
            liste = extraire_mises_au_point(
                blocs.get(row.id), acteurs, civilites, connus
            )
            declarations += sum(1 for m in liste if m.nature == "mise_au_point")
            pannes += sum(1 for m in liste if m.nature == "dysfonctionnement")
            scrutin = Scrutin.model_validate(row.payload)
            if scrutin.mises_au_point == liste:
                continue
            scrutin.mises_au_point = liste
            row.payload = scrutin.model_dump(mode="json", by_alias=True)
            ecrits += 1
        if dry_run:
            await session.rollback()
        else:
            await session.commit()
    await engine.dispose()

    verbe = "seraient mis à jour" if dry_run else "mis à jour"
    print(
        f"{ecrits} scrutin(s) {verbe} : {declarations} mise(s) au point et "
        f"{pannes} dysfonctionnement(s) publiés par l'Assemblée."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="compte sans écrire en base")
    parser.add_argument("--legislature", type=int, default=17)
    args = parser.parse_args()
    asyncio.run(_main(args.dry_run, args.legislature))


if __name__ == "__main__":
    main()
