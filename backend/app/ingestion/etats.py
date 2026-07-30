"""Renseigne « où en est le texte » sur les dossiers DÉJÀ en base.

    python -m app.ingestion.etats            # applique
    python -m app.ingestion.etats --dry-run  # montre la répartition sans écrire

La frise, seule, ne raconte que le passé. L'état (promulgué, devant le Conseil
constitutionnel, retiré, résolution conclue, ou simplement la dernière étape
enregistrée) est posé à l'ingestion, mais les dossiers ingérés avant son
introduction ne le portent pas. Cette commande les rattrape sans réingérer :
elle ne télécharge que l'archive des **dossiers législatifs** (~10 Mo). Ni
scrutins, ni PDF, ni LLM — quelques secondes au lieu d'un run complet.

L'état porte le lien Légifrance (le texte en vigueur) : la liste des documents
du dossier est donc recomposée dans la foulée, pour qu'elle le reflète (§7.5).

À rejouer quand les règles de `etat_du_texte` changent. Idempotent.
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
from app.ingestion.assemblee import AssembleeOpenDataClient
from app.domain.sources import documents_du_dossier
from app.ingestion.navette import etat_du_texte
from app.schemas import Dossier

# Libellés d'affichage du récapitulatif, dans l'ordre où on les montre.
_ORDRE = (
    "promulgue",
    "en_navette",
    "resolution",
    "conseil_constitutionnel",
    "retire",
)


async def _telecharger_dossiers(client: AssembleeOpenDataClient) -> list[dict]:
    """Dossiers parlementaires, législature courante + précédente (best-effort).

    Même fenêtre que le run complet : un dossier reporté après une dissolution
    garde son `dossierRef` d'origine, donc ses actes vivent dans l'archive de la
    législature précédente."""
    _, dossiers = await client.download_dossiers_complet(client.legislature)
    if client.legislature > 1:
        try:
            _, precedents = await client.download_dossiers_complet(
                client.legislature - 1
            )
            dossiers += precedents
        except (httpx.HTTPError, zipfile.BadZipFile) as exc:
            print(
                f"⚠ archive de la législature précédente non téléchargée "
                f"({type(exc).__name__}) : rattrapage limité à la courante."
            )
    return dossiers


async def _main(dry_run: bool, legislature: int) -> None:
    client = AssembleeOpenDataClient(legislature=legislature)
    print(f"Téléchargement de l'archive des dossiers (législature {legislature})…")
    dossiers_pa = await _telecharger_dossiers(client)
    # L'identifiant d'un dossier officiel EST son `dossierRef` : c'est la clé de
    # jointure avec la base, sans traitement intermédiaire.
    #
    # ⚠️ La **première** copie vue gagne, et la liste commence par la législature
    # courante : 193 dossiers figurent dans les deux archives, et celle de la
    # législature précédente est un instantané figé (36 y sont sans leur
    # promulgation, pourtant documentée par l'archive courante).
    par_ref: dict[str, dict] = {}
    for d in dossiers_pa:
        dossier_pa = d.get("dossierParlementaire") or d
        uid = dossier_pa.get("uid")
        if uid and uid not in par_ref:
            par_ref[uid] = dossier_pa
    print(f"{len(par_ref)} dossier(s) dans l'archive.")

    engine = make_engine()
    session_factory = make_session_factory(engine)
    ecrits = inchanges = sans = 0
    repartition: Counter[str] = Counter()
    sources_recomposees = 0

    async with session_factory() as session:
        for row in (await session.execute(select(DossierRow))).scalars().all():
            # Les dossiers reconstitués (« TXT-… ») et sénatoriaux (« SEN-… »)
            # n'ont pas d'actes législatifs : pas d'état, bloc masqué (§2.5).
            source_archive = par_ref.get(row.id)
            etat = etat_du_texte(
                (source_archive or {}).get("actesLegislatifs"),
                (source_archive or {}).get("procedureParlementaire"),
            )
            if etat is None:
                sans += 1
                continue
            repartition[etat.etat] += 1

            dossier = Dossier.model_validate(row.payload)
            avant = dossier.model_dump(mode="json", by_alias=True)
            dossier.etat = etat
            # L'état porte le lien Légifrance, donc la liste des documents du
            # dossier change avec lui : on la recompose (§7.5). Idempotent.
            avant_sources = list(dossier.sources)
            dossier.sources = documents_du_dossier(dossier)
            if dossier.sources != avant_sources:
                sources_recomposees += 1
            apres = dossier.model_dump(mode="json", by_alias=True)
            if apres == avant:
                inchanges += 1
                continue
            row.payload = apres
            ecrits += 1

        if dry_run:
            await session.rollback()
        else:
            await session.commit()

    await engine.dispose()

    verbe = "seraient mis à jour" if dry_run else "mis à jour"
    print(
        f"\n{ecrits} dossier(s) {verbe}, {inchanges} déjà à jour, "
        f"{sans} sans état (bloc masqué, §2.5)."
    )
    total = sum(repartition.values())
    if total:
        print(f"\nRépartition ({total} dossiers) :")
        for etat in _ORDRE:
            if repartition[etat]:
                print(f"  {repartition[etat]:4d}  {etat}")
        print(
            f"\n{sources_recomposees} liste(s) de documents recomposée(s) "
            f"(le texte en vigueur en fait partie)."
        )


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
