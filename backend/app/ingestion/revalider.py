"""Repasse les garde-fous sur les réponses citoyennes DÉJÀ en base.

    python -m app.ingestion.revalider --dry-run   # compte sans écrire
    python -m app.ingestion.revalider             # efface les réponses fautives

Les réponses générées sont réutilisées d'un run à l'autre (on ne repaie pas un
appel LLM déjà validé). Quand un garde-fou est ajouté, les réponses écrites
AVANT lui resteraient donc en base indéfiniment : cette commande leur applique
les contrôles courants et **efface** celles qui ne passent plus. Le run suivant
les régénère avec les consignes à jour ; d'ici là, la section est simplement
absente (§2.5) — jamais une réponse fausse laissée à l'écran.

Aucun réseau, aucun LLM : uniquement `valider_reponse` sur les sources déjà
stockées. Idempotent — relancer ne change plus rien.

⚠️ La Q1 d'un dossier porte l'accroche affichée dans le fil
(`accroche_depuis_q1`) : effacer une Q1 efface l'accroche, recalculée ici même.

⚠️ La Q2 (« principal désaccord ») ne se juge que si l'extrait de compte rendu
qui l'a produite a été conservé (`dossier.desaccord_sources`). Les arguments
écrits avant cette colonne n'ont pas de source : ils sont **invérifiables**, donc
effacés — le run suivant les régénère avec l'ancrage lexical en place.
"""
from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

from app.ai.questions import (
    PREFIXE_AUTEUR,
    PREFIXE_AUTEUR_AMENDEMENT,
    accroche_depuis_q1,
    valider_argument,
    valider_reponse,
)
from app.db.models import DossierRow, ScrutinRow
from app.db.session import make_engine, make_session_factory
from app.domain.recherche import index_recherche
from app.ingestion.normalize import deposant
from app.schemas import Dossier

# Même cap que le prompt de génération : on revalide contre ce que le modèle a
# réellement lu, pas contre un exposé plus long qu'il n'a jamais vu.
_MAX_EXPOSE = 4000


@dataclass
class Bilan:
    amendements_pourquoi: int = 0
    amendements_changement: int = 0
    dossiers_pourquoi: int = 0
    dossiers_changement: int = 0
    accroches_retirees: int = 0
    # Q2 : un argument = la paraphrase d'un groupe ; un désaccord vidé de tous
    # ses arguments fait disparaître la section entière.
    arguments_desaccord: int = 0
    desaccords_vides: int = 0
    exemples: list[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return (
            self.amendements_pourquoi
            + self.amendements_changement
            + self.dossiers_pourquoi
            + self.dossiers_changement
            + self.arguments_desaccord
        )

    def noter(self, quoi: str, identifiant: str, reponse: str) -> None:
        if len(self.exemples) < 10:
            self.exemples.append(f"{quoi} {identifiant} : {reponse[:110]}…")


async def _revalider_scrutins(session, bilan: Bilan) -> None:
    """Questions d'un vote d'amendement (`Scrutin.questions`)."""
    for row in (await session.execute(select(ScrutinRow))).scalars().all():
        payload = dict(row.payload or {})
        questions = dict(payload.get("questions") or {})
        if not questions:
            continue
        objet = payload.get("objet", "")
        qui_depose = deposant(objet)
        modifie = False

        pourquoi = questions.get("pourquoi")
        expose = payload.get("exposeSommaire")
        if pourquoi and expose:
            if valider_reponse(
                pourquoi,
                f"{objet}\n{expose}",
                prefixe=PREFIXE_AUTEUR_AMENDEMENT,
                deposant=qui_depose,
            ) is None:
                questions["pourquoi"] = None
                bilan.amendements_pourquoi += 1
                bilan.noter("amendement/pourquoi", row.id, pourquoi)
                modifie = True

        changement = questions.get("changement")
        dispositif = payload.get("dispositif")
        if changement and dispositif:
            if valider_reponse(
                changement,
                f"{objet}\n{dispositif}",
                lexique_de_la_source_admis=True,
                deposant=qui_depose,
            ) is None:
                questions["changement"] = None
                bilan.amendements_changement += 1
                bilan.noter("amendement/changement", row.id, changement)
                modifie = True

        if modifie:
            payload["questions"] = questions
            row.payload = payload
            flag_modified(row, "payload")


async def _revalider_dossiers(session, bilan: Bilan) -> None:
    """Q1 / Q4 d'un dossier (`resume.questions`) + accroche dérivée de la Q1."""
    for row in (await session.execute(select(DossierRow))).scalars().all():
        payload = dict(row.payload or {})
        resume = dict(payload.get("resume") or {})
        questions = dict(resume.get("questions") or {})
        expose = (payload.get("exposeMotifs") or {}).get("texte")
        if not questions or not expose:
            continue
        titre = payload.get("titreOfficiel", "")
        sources = f"{titre}\n{expose[:_MAX_EXPOSE]}"
        modifie = False

        pourquoi = questions.get("pourquoi")
        if pourquoi and valider_reponse(pourquoi, sources) is None:
            questions["pourquoi"] = None
            bilan.dossiers_pourquoi += 1
            bilan.noter("dossier/Q1", row.id, pourquoi)
            modifie = True

        # Seule la Q4 tirée de l'EXPOSÉ est revalidable ici : celle tirée du
        # dispositif (fait, sans attribution) a pour source le texte officiel,
        # que le dossier ne stocke pas toujours — on n'y touche pas plutôt que
        # de la juger sur une source qui n'est pas la sienne.
        changement = questions.get("changement")
        if changement and changement.startswith(PREFIXE_AUTEUR):
            if valider_reponse(
                changement,
                sources,
                prefixe=PREFIXE_AUTEUR,
                deposant=deposant(titre),
            ) is None:
                questions["changement"] = None
                bilan.dossiers_changement += 1
                bilan.noter("dossier/Q4", row.id, changement)
                modifie = True

        if not modifie:
            continue

        resume["questions"] = questions
        payload["resume"] = resume
        # L'accroche n'est qu'un extrait de la Q1 : sans Q1, plus d'accroche.
        accroche = accroche_depuis_q1(questions.get("pourquoi"))
        if row.accroche and not accroche:
            bilan.accroches_retirees += 1
        payload["accroche"] = accroche
        row.accroche = accroche or ""
        row.payload = payload
        flag_modified(row, "payload")
        # L'index de recherche couvre les réponses Q1/Q4 : il doit suivre.
        row.search_index = index_recherche(Dossier.model_validate(payload))


async def _revalider_desaccord(session, bilan: Bilan) -> None:
    """Q2 d'un dossier, jugée contre l'extrait de compte rendu qui l'a produite.

    Un argument met une opinion dans la bouche d'un groupe : il n'a le droit
    d'exister que si l'on peut montrer la phrase prononcée dont il est la
    paraphrase (§7.4, §7.5). Deux cas d'effacement :

    - **source absente** (`dossier.desaccord_sources` NULL ou sans ce groupe) :
      l'argument est invérifiable — c'est le cas de toutes les Q2 écrites avant
      que la colonne existe ;
    - **source présente mais contrôles en échec** : notamment l'ancrage lexical,
      qui rejette une phrase sans rapport avec ce que le groupe a dit.

    Le désaccord vidé de tous ses arguments est retiré en entier (objet et source
    compris : la source suit sa réponse), et les extraits orphelins avec lui — le
    run suivant régénère alors depuis les débats.
    """
    for row in (await session.execute(select(DossierRow))).scalars().all():
        payload = dict(row.payload or {})
        resume = dict(payload.get("resume") or {})
        questions = dict(resume.get("questions") or {})
        desaccord = questions.get("desaccord")
        if not isinstance(desaccord, list) or not desaccord:
            continue

        sources: dict = row.desaccord_sources or {}
        retenus = []
        for argument in desaccord:
            prononce = sources.get(argument.get("groupe", ""))
            if prononce and valider_argument(argument.get("argument", ""), prononce):
                retenus.append(argument)
            else:
                bilan.arguments_desaccord += 1
                bilan.noter(
                    "dossier/Q2", row.id, argument.get("argument", "") or "(vide)"
                )
        if len(retenus) == len(desaccord):
            continue

        if retenus:
            questions["desaccord"] = retenus
            gardes = {a.get("groupe") for a in retenus}
            row.desaccord_sources = {
                g: t for g, t in sources.items() if g in gardes
            } or None
        else:
            questions["desaccord"] = None
            questions["desaccordObjet"] = None
            questions["desaccordSource"] = None
            row.desaccord_sources = None
            bilan.desaccords_vides += 1

        resume["questions"] = questions
        payload["resume"] = resume
        row.payload = payload
        flag_modified(row, "payload")
        # L'index de recherche ne couvre PAS la Q2 (cf. `domain/recherche.py`) et
        # l'accroche vient de la Q1 : rien d'autre à recalculer ici.


async def _main(dry_run: bool) -> None:
    engine = make_engine()
    session_factory = make_session_factory(engine)
    bilan = Bilan()

    async with session_factory() as session:
        await _revalider_scrutins(session, bilan)
        await _revalider_dossiers(session, bilan)
        await _revalider_desaccord(session, bilan)
        if dry_run:
            await session.rollback()
        else:
            await session.commit()

    await engine.dispose()

    verbe = "seraient effacées" if dry_run else "effacées"
    print(
        f"{bilan.total} réponse(s) {verbe} : "
        f"{bilan.amendements_pourquoi} « pourquoi » d'amendement, "
        f"{bilan.amendements_changement} « ce que ça change » d'amendement, "
        f"{bilan.dossiers_pourquoi} Q1 de dossier "
        f"({bilan.accroches_retirees} accroche(s) retirée(s)), "
        f"{bilan.dossiers_changement} Q4 de dossier, "
        f"{bilan.arguments_desaccord} argument(s) de Q2 "
        f"({bilan.desaccords_vides} désaccord(s) retiré(s) en entier)."
    )
    if bilan.exemples:
        print("Exemples :")
        for exemple in bilan.exemples:
            print(f"  - {exemple}")
    if bilan.total and not dry_run:
        print("Le prochain run d'ingestion les régénérera (consignes à jour).")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="compte et montre les réponses fautives sans écrire en base",
    )
    args = parser.parse_args()
    asyncio.run(_main(args.dry_run))


if __name__ == "__main__":
    main()
