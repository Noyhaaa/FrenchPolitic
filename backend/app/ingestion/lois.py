"""Attache la **loi finale** aux dossiers DÉJÀ en base, et réécrit leur Q4.

    python -m app.ingestion.lois              # applique (texte voté + Q4)
    python -m app.ingestion.lois --dry-run    # montre la couverture, n'écrit rien
    python -m app.ingestion.lois --sans-llm   # textes votés seuls, aucune Q4

Tout ce que l'app dit d'un texte vient de son **dépôt**. Sur une loi promulguée,
cette version n'existe plus : la navette et les amendements l'ont modifiée. La
fiche d'une loi en vigueur affichait donc le pitch de son auteur, au conditionnel,
sur une proposition — mesuré sur 83 des 96 lois promulguées.

Cette commande récupère le texte **définitivement voté** (la « petite loi », que
l'archive désigne par `PROM-PUB.texteLoiRef`) et, quand son corps est exploitable,
régénère la Q4 depuis lui — à l'**indicatif**, sans attribution.

Ne télécharge que l'archive des dossiers (~10 Mo) et les PDF des petites lois.
⚠️ Le LLM est celui de `.env` (Ollama distant) : **jamais** de repli local. S'il
est injoignable, la commande le dit et s'arrête aux textes.

Idempotent : à rejouer quand les règles de `textes_adoptes` ou le prompt changent.
"""
from __future__ import annotations

import argparse
import asyncio
import zipfile
from collections import Counter

import httpx
from sqlalchemy import select

from app.ai.llm import OllamaLLM, get_llm_client
from app.ai.questions import generer_changement_loi
from app.config import settings
from app.db.models import DossierRow
from app.db.session import make_engine, make_session_factory
from app.domain.sources import documents_du_dossier
from app.ingestion.assemblee import AssembleeOpenDataClient
from app.ingestion.textes_adoptes import (
    construire_index_publications_ta,
    construire_texte_adopte,
    ref_texte_loi,
    urls_texte_adopte,
)
from app.schemas import Dossier


async def _telecharger(
    client: AssembleeOpenDataClient,
) -> tuple[list[dict], list[dict]]:
    """`(documents, dossiers)` de la législature courante + la précédente.

    Même fenêtre que le run complet, et même règle de priorité : la **première**
    copie vue gagne, donc celle de la législature courante — celle de la
    précédente est un instantané figé où 36 dossiers sont sans leur promulgation.
    """
    documents, dossiers = await client.download_dossiers_complet(client.legislature)
    if client.legislature > 1:
        try:
            docs_prec, doss_prec = await client.download_dossiers_complet(
                client.legislature - 1
            )
            documents += docs_prec
            dossiers += doss_prec
        except (httpx.HTTPError, zipfile.BadZipFile) as exc:
            print(
                f"⚠ archive de la législature précédente non téléchargée "
                f"({type(exc).__name__}) : rattrapage limité à la courante."
            )
    return documents, dossiers


async def _main(dry_run: bool, sans_llm: bool, legislature: int) -> None:
    client = AssembleeOpenDataClient(legislature=legislature)
    print(f"Téléchargement de l'archive des dossiers (législature {legislature})…")
    documents, dossiers_pa = await _telecharger(client)
    publications = construire_index_publications_ta(documents)
    actes_par_ref: dict[str, object] = {}
    for brut in dossiers_pa:
        dossier_pa = brut.get("dossierParlementaire") or brut
        uid = dossier_pa.get("uid")
        if uid and uid not in actes_par_ref:
            actes_par_ref[uid] = dossier_pa.get("actesLegislatifs")
    print(
        f"{len(actes_par_ref)} dossiers dans l'archive, "
        f"{len(publications)} textes adoptés indexés."
    )

    llm = None
    if not sans_llm and not dry_run:
        llm = get_llm_client() if settings.llm_provider != "mock" else None
        if isinstance(llm, OllamaLLM) and not await llm.disponible():
            print(
                f"⚠ LLM {settings.llm_provider}:{settings.llm_model} injoignable "
                f"({settings.llm_base_url}) : les textes votés sont écrits, la Q4 "
                f"reste inchangée. Rejouer la commande quand il répond."
            )
            llm = None

    engine = make_engine()
    session_factory = make_session_factory(engine)
    res: Counter[str] = Counter()

    async with session_factory() as session:
        rows = (
            (
                await session.execute(
                    select(DossierRow).where(
                        DossierRow.payload["etat"]["etat"].astext == "promulgue"
                    )
                )
            )
            .scalars()
            .all()
        )
        print(f"{len(rows)} loi(s) promulguée(s) en base.\n")
        for row in rows:
            dossier = Dossier.model_validate(row.payload)
            avant = dossier.model_dump(mode="json", by_alias=True)

            # Une loi promulguée ne change plus : ce qui est en base est repris
            # tel quel, sans réseau.
            if dossier.texte_adopte is None:
                uid = ref_texte_loi(actes_par_ref.get(row.id))
                if not uid:
                    # L'archive ne désigne pas le texte de la loi. Ses dossiers
                    # en portent plusieurs (un par lecture) : en élire un serait
                    # choisir à la place de la source (§2.5).
                    res["sans texteLoiRef → rien"] += 1
                    continue
                urls = urls_texte_adopte(uid, publications.get(uid))
                if urls is None:
                    res["URL non dérivable"] += 1
                    continue
                pdf = await client.download_texte_pdf(urls[1])
                dossier.texte_adopte = construire_texte_adopte(urls[0], pdf)
            res["lien vers le texte voté"] += 1
            if dossier.texte_adopte.texte:
                res["corps lu (Q4 possible)"] += 1
            else:
                res["lien seul (hors cap ou PDF absent)"] += 1

            # Q4 : on ne rappelle le modèle que si la réponse en base ne vient
            # pas déjà du texte voté.
            questions = dossier.resume.questions
            if (
                llm is not None
                and dossier.texte_adopte.texte
                and questions is not None
                and questions.changement_source != dossier.texte_adopte.source
            ):
                reponse = await generer_changement_loi(
                    dossier.titre_officiel, dossier.texte_adopte.texte, llm
                )
                if reponse:
                    questions.changement = reponse
                    questions.changement_source = dossier.texte_adopte.source
                    res["Q4 réécrite depuis la loi"] += 1
                else:
                    # Rejetée par les garde-fous : l'ancienne réponse reste, elle
                    # est validée — mieux qu'un trou (§2.5).
                    res["Q4 rejetée par les garde-fous"] += 1

            # Le texte voté est un document du dossier : la liste le reflète.
            dossier.sources = documents_du_dossier(dossier)
            apres = dossier.model_dump(mode="json", by_alias=True)
            if apres == avant:
                res["déjà à jour"] += 1
                continue
            row.payload = apres
            res["dossiers réécrits"] += 1

        if dry_run:
            await session.rollback()
        else:
            await session.commit()

    await engine.dispose()

    print("Bilan" + (" (à blanc, rien écrit)" if dry_run else "") + " :")
    for cle, valeur in res.most_common():
        print(f"  {valeur:4d}  {cle}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="affiche la couverture sans écrire ni appeler le modèle",
    )
    parser.add_argument(
        "--sans-llm",
        action="store_true",
        help="récupère les textes votés sans régénérer la Q4",
    )
    parser.add_argument("--legislature", type=int, default=17)
    args = parser.parse_args()
    asyncio.run(_main(args.dry_run, args.sans_llm, args.legislature))


if __name__ == "__main__":
    main()
