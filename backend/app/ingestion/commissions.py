"""Renseigne les amendements de commission sur les dossiers DÉJÀ en base.

    python -m app.ingestion.commissions            # applique
    python -m app.ingestion.commissions --dry-run  # compte sans écrire

Le décompte des amendements tranchés en commission saisie au fond
(`Dossier.amendementsCommission`, cf. `app.ingestion.commission`) est posé à
l'ingestion. Cette commande le rattrape sans réingérer : archive des
amendements (~300 Mo), archive des dossiers (actes de saisine) et annuaires AMO
(libellés des commissions). Ni scrutins, ni PDF, ni LLM. Idempotent.
"""
from __future__ import annotations

import argparse
import asyncio
import zipfile

import httpx
from sqlalchemy import select

from app.db.models import DossierRow
from app.db.session import make_engine, make_session_factory
from app.ingestion.assemblee import AssembleeOpenDataClient
from app.ingestion.commission import (
    amendements_commission,
    commissions_au_fond,
    noms_commissions,
    organes_par_abreviation,
)
from app.schemas import Dossier


async def _actes_par_ref(client: AssembleeOpenDataClient) -> dict[str, object]:
    """dossierRef → actes législatifs, législature courante puis précédente.

    La première copie vue gagne, comme au run complet : la copie de la
    législature précédente d'un dossier reporté est un instantané figé.
    """
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
    actes: dict[str, object] = {}
    for d in dossiers:
        dossier_pa = d.get("dossierParlementaire") or d
        uid = dossier_pa.get("uid")
        if uid and uid not in actes:
            actes[uid] = dossier_pa.get("actesLegislatifs")
    return actes


async def _main(dry_run: bool, legislature: int) -> None:
    client = AssembleeOpenDataClient(legislature=legislature)
    print("Téléchargement des annuaires AMO…")
    organes, _ = await client.download_amo()
    organes_historiques, _ = await client.download_amo_historique()
    noms = noms_commissions(organes, organes_historiques)
    par_abreviation = organes_par_abreviation(organes, organes_historiques)
    print(f"Téléchargement de l'archive des dossiers (législature {legislature})…")
    actes = await _actes_par_ref(client)
    print("Téléchargement de l'archive des amendements (~300 Mo)…")
    compteurs = (await client.download_amendements()).commission

    engine = make_engine()
    session_factory = make_session_factory(engine)
    ecrits = inchanges = sans = 0
    adoptes = rejetes = 0

    async with session_factory() as session:
        for row in (await session.execute(select(DossierRow))).scalars().all():
            # L'id d'un dossier officiel EST son `dossierRef` : les dossiers
            # reconstitués (« TXT-… », « SEN-… ») n'ont ni saisine ni décompte.
            liste = amendements_commission(
                compteurs.get(row.id),
                commissions_au_fond(actes.get(row.id)),
                noms,
                par_abreviation,
            )
            if not liste:
                sans += 1
                continue
            adoptes += sum(c.adoptes for c in liste)
            rejetes += sum(c.rejetes for c in liste)
            dossier = Dossier.model_validate(row.payload)
            if dossier.amendements_commission == liste:
                inchanges += 1
                continue
            dossier.amendements_commission = liste
            row.payload = dossier.model_dump(mode="json", by_alias=True)
            ecrits += 1

        if dry_run:
            await session.rollback()
        else:
            await session.commit()

    await engine.dispose()

    verbe = "seraient mis à jour" if dry_run else "mis à jour"
    print(
        f"\n{ecrits} dossier(s) {verbe}, {inchanges} déjà à jour, {sans} sans "
        f"examen en commission documenté (bloc masqué, §2.5).\n"
        f"En commission saisie au fond : {adoptes} amendements adoptés, "
        f"{rejetes} rejetés."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run", action="store_true", help="compte sans écrire en base"
    )
    parser.add_argument("--legislature", type=int, default=17)
    args = parser.parse_args()
    asyncio.run(_main(args.dry_run, args.legislature))


if __name__ == "__main__":
    main()
