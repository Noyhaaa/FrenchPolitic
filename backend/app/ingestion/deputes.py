"""Ingestion des députés et de leurs votes nominatifs (§5.1, §5.2).

Deux sources, déjà téléchargées par `AssembleeOpenDataClient` :

- l'archive **AMO** (acteurs + organes) → le référentiel des députés (nom,
  groupe, circonscription, début de mandat) ;
- l'archive des **scrutins publics** → qui a voté quoi
  (`ventilationVotes.organe.groupes.groupe[].vote.decompteNominatif`).

`build_deputes_from_amo` et `votes_du_scrutin` sont des fonctions **pures**
(dict brut → objets du domaine), testables sans réseau ni base — même contrat
que `parse_scrutin`.

Règles produit :
- champ absent de la source → chaîne vide / None, jamais une valeur devinée
  (§2.5) : pas de circonscription reconstituée. La **photo officielle** fait
  exception encadrée : son URL se dérive de l'`acteurRef` (le référentiel AMO ne
  la porte pas), mais elle n'est attachée qu'après avoir été **vérifiée** —
  jamais une image cassée dans l'app ;
- « contre son groupe » est un **fait déduit** du même scrutin (position du
  député ≠ position majoritaire de son groupe), jamais un jugement (§7.4), et
  seulement pour les positions exprimées.

CLI autonome (ne refait QUE cette partie, sans LLM ni dossiers/amendements) :

    python -m app.ingestion.deputes            # toute la législature
    python -m app.ingestion.deputes --limit 300
"""
from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx
from sqlalchemy import delete, insert
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DeputeRow, VoteDeputeRow
from app.domain.enums import PositionVote
from app.ingestion.normalize import as_list, map_position
from app.ingestion.organes import GroupResolver
from app.schemas import Depute
from app.utils.text import fold

# Positions exprimées (les seules qui peuvent diverger de la majorité du
# groupe) et le bloc `decompteNominatif` correspondant dans l'open data.
_BLOCS: tuple[tuple[str, PositionVote], ...] = (
    ("pours", PositionVote.pour),
    ("contres", PositionVote.contre),
    ("abstentions", PositionVote.abstention),
    ("nonVotants", PositionVote.non_votant),
)

_POSITIONS_EXPRIMEES = (
    PositionVote.pour,
    PositionVote.contre,
    PositionVote.abstention,
)

# Lots d'insertion : ~570 lignes par scrutin, ~2,9 M au total sur la
# législature. On insère par paquets (jamais ligne à ligne).
TAILLE_LOT = 5_000


@dataclass(frozen=True)
class VoteActeur:
    """Le vote d'un député sur un scrutin donné."""

    acteur_ref: str
    position: PositionVote
    # None quand le groupe n'a pas de position majoritaire exploitable, ou que
    # le député n'a pas exprimé de vote (§2.5).
    contre_son_groupe: bool | None = None


def _mandats(acteur: dict) -> list[dict]:
    """Mandats de l'acteur (l'open data sérialise 1 mandat comme objet)."""
    mandats = (acteur.get("mandats") or {}).get("mandat")
    return [m for m in as_list(mandats) if isinstance(m, dict)]


def _est_actif(mandat: dict) -> bool:
    return not mandat.get("dateFin")


def _organe_ref(mandat: dict) -> str:
    refs = as_list((mandat.get("organes") or {}).get("organeRef"))
    return str(refs[0]) if refs else ""


def circonscription(mandat: dict | None) -> str:
    """« Pas-de-Calais, 5ᵉ circ. » depuis le mandat ASSEMBLEE.

    Chaîne vide si le mandat ou le lieu d'élection manque : on ne devine pas
    une circonscription (§2.5).
    """
    if not mandat:
        return ""
    lieu = (mandat.get("election") or {}).get("lieu") or {}
    departement = (lieu.get("departement") or "").strip()
    numero = str(lieu.get("numCirco") or "").strip()
    if not departement:
        return ""
    if not numero:
        return departement
    rang = "1re" if numero == "1" else f"{numero}ᵉ"
    return f"{departement}, {rang} circ."


def build_deputes_from_amo(
    acteur_wrappers: list[dict], resolver: GroupResolver
) -> list[Depute]:
    """Référentiel des députés depuis l'archive AMO (clé « acteur »).

    Ne retient que les acteurs ayant un mandat ASSEMBLEE **en cours** (les
    anciens députés ne sont pas dans l'annuaire) ; le groupe vient du mandat GP
    en cours, résolu en nom + couleur par le `GroupResolver` (même source que
    la ventilation des scrutins, donc mêmes couleurs qu'ailleurs dans l'app).
    """
    deputes: list[Depute] = []
    for wrapper in acteur_wrappers:
        acteur = wrapper.get("acteur", wrapper)
        uid = acteur.get("uid")
        if isinstance(uid, dict):  # les fichiers acteur sérialisent uid en objet
            uid = uid.get("#text")
        if not uid:
            continue
        ident = (acteur.get("etatCivil") or {}).get("ident") or {}
        nom = " ".join(
            p for p in (ident.get("prenom"), ident.get("nom")) if p
        ).strip()
        if not nom:
            continue

        mandats = _mandats(acteur)
        assemblee = next(
            (
                m
                for m in mandats
                if m.get("typeOrgane") == "ASSEMBLEE" and _est_actif(m)
            ),
            None,
        )
        if assemblee is None:
            continue  # mandat terminé : hors annuaire
        groupe = next(
            (m for m in mandats if m.get("typeOrgane") == "GP" and _est_actif(m)),
            None,
        )
        info = resolver.resolve(_organe_ref(groupe) if groupe else "")
        deputes.append(
            Depute(
                id=str(uid),
                nom=nom,
                groupe_id=info.id,
                groupe_nom=info.nom,
                groupe_couleur=info.couleur,
                circonscription=circonscription(assemblee),
                depuis=(groupe or {}).get("dateDebut") or None,
                # Photo : ajoutée ensuite par `attacher_portraits`, qui vérifie
                # chaque URL avant de l'attacher (fonction pure ici — pas de
                # réseau, et surtout aucune URL posée sans preuve, §2.5).
                portrait_url=None,
            )
        )
    return deputes


# Photo officielle du député sur le site de l'Assemblée. Le référentiel AMO ne
# porte PAS ce champ : l'URL se dérive de l'`acteurRef` (sans le préfixe « PA »)
# et de la législature. Variante « carré », cadrée pour un avatar rond.
GABARIT_PORTRAIT = (
    "https://www.assemblee-nationale.fr/dyn/static/tribun/{leg}/photos/carre/{numero}.jpg"
)

# Requêtes de vérification menées en parallèle (courtoisie envers le serveur AN).
CONCURRENCE_PORTRAITS = 8


def url_portrait(acteur_ref: str, legislature: int) -> str:
    """URL candidate de la photo officielle (fonction pure).

    L'URL n'est qu'une **hypothèse** tant qu'elle n'a pas répondu : c'est
    `attacher_portraits` qui la confirme avant qu'elle n'atteigne l'app.
    """
    return GABARIT_PORTRAIT.format(leg=legislature, numero=acteur_ref.removeprefix("PA"))


async def attacher_portraits(
    deputes: list[Depute], legislature: int, timeout: float = 15.0
) -> int:
    """Attache sa photo officielle à chaque député, **après vérification**.

    L'URL est dérivée de l'`acteurRef`, donc devinée : on ne l'attache que si
    elle répond bien une image (HEAD 200 + `content-type: image/…`). Un député
    sans photo joignable garde `portrait_url = None` et l'app affiche ses
    initiales — jamais une image cassée (§2.5, §7.5 : ce qu'on montre est
    vérifié). Best-effort : une panne réseau laisse simplement les portraits
    non attachés ce run-ci, elle ne fait pas échouer l'ingestion.

    Modifie `deputes` sur place ; renvoie le nombre de photos confirmées.
    """
    semaphore = asyncio.Semaphore(CONCURRENCE_PORTRAITS)
    confirmees = 0

    async def verifier(client: httpx.AsyncClient, depute: Depute) -> None:
        nonlocal confirmees
        url = url_portrait(depute.id, legislature)
        async with semaphore:
            try:
                reponse = await client.head(url, follow_redirects=True)
            except httpx.HTTPError:
                return  # injoignable : pas de photo attachée, pas d'échec
        type_contenu = reponse.headers.get("content-type", "")
        if reponse.status_code == 200 and type_contenu.startswith("image"):
            depute.portrait_url = url
            confirmees += 1

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            await asyncio.gather(*(verifier(client, d) for d in deputes))
    except httpx.HTTPError:
        return confirmees
    return confirmees


def votes_du_scrutin(raw: dict) -> list[VoteActeur]:
    """Votes nominatifs d'un scrutin brut (fonction pure).

    Liste vide si le scrutin ne porte pas de ventilation nominative — le vote
    à main levée n'a pas de détail par député (§5.2), on n'en fabrique pas.
    """
    s = raw.get("scrutin") or {}
    ventilation = (s.get("ventilationVotes") or {}).get("organe") or {}
    votes: dict[str, VoteActeur] = {}
    for groupe in as_list((ventilation.get("groupes") or {}).get("groupe")):
        if not isinstance(groupe, dict):
            continue
        vote = groupe.get("vote") or {}
        brut_majoritaire = vote.get("positionMajoritaire")
        majoritaire = map_position(brut_majoritaire) if brut_majoritaire else None
        # Un groupe majoritairement « non votant » / absent ne fournit pas de
        # référence exploitable : on ne qualifie alors aucune divergence (§2.5).
        if majoritaire not in _POSITIONS_EXPRIMEES:
            majoritaire = None
        nominatif = vote.get("decompteNominatif") or {}
        for cle, position in _BLOCS:
            bloc = nominatif.get(cle)
            if not isinstance(bloc, dict):
                continue
            for votant in as_list(bloc.get("votant")):
                if not isinstance(votant, dict):
                    continue
                ref = str(votant.get("acteurRef") or "")
                if not ref or ref in votes:
                    continue
                contre_son_groupe: bool | None = None
                if position in _POSITIONS_EXPRIMEES and majoritaire is not None:
                    contre_son_groupe = position != majoritaire
                votes[ref] = VoteActeur(
                    acteur_ref=ref,
                    position=position,
                    contre_son_groupe=contre_son_groupe,
                )
    return list(votes.values())


def _depute_row_values(d: Depute) -> dict:
    return {
        "id": d.id,
        "nom": d.nom,
        "groupe_id": d.groupe_id,
        "groupe_nom": d.groupe_nom,
        "groupe_couleur": d.groupe_couleur,
        "circonscription": d.circonscription,
        "depuis": d.depuis,
        "portrait_url": d.portrait_url,
        "search_index": fold(f"{d.nom} {d.groupe_nom} {d.circonscription}"),
    }


async def upsert_deputes(session: AsyncSession, deputes: list[Depute]) -> int:
    """Upsert du référentiel (idempotent entre runs : un changement de groupe
    en cours de législature met simplement la ligne à jour)."""
    total = 0
    for debut in range(0, len(deputes), TAILLE_LOT):
        lot = [_depute_row_values(d) for d in deputes[debut : debut + TAILLE_LOT]]
        if not lot:
            continue
        stmt = pg_insert(DeputeRow).values(lot)
        update = {k: getattr(stmt.excluded, k) for k in lot[0] if k != "id"}
        await session.execute(
            stmt.on_conflict_do_update(index_elements=["id"], set_=update)
        )
        total += len(lot)
    return total


async def remplacer_votes_du_scrutin(
    session: AsyncSession, scrutin_id: str, date: str, votes: list[VoteActeur]
) -> int:
    """Réécrit les votes nominatifs d'un scrutin (delete + insert par lots).

    Remplacer plutôt qu'upserter ligne à ligne rend le run idempotent à coût
    constant : un scrutin rejoué écrase exactement sa ventilation précédente.
    """
    await session.execute(
        delete(VoteDeputeRow).where(VoteDeputeRow.scrutin_id == scrutin_id)
    )
    lignes = [
        {
            "acteur_ref": v.acteur_ref,
            "scrutin_id": scrutin_id,
            "date": date,
            "position": v.position.value,
            "contre_son_groupe": v.contre_son_groupe,
        }
        for v in votes
    ]
    for debut in range(0, len(lignes), TAILLE_LOT):
        await session.execute(insert(VoteDeputeRow).values(lignes[debut : debut + TAILLE_LOT]))
    return len(lignes)


# --------------------------------------------------------------------------
# CLI autonome : référentiel + votes nominatifs UNIQUEMENT.
# --------------------------------------------------------------------------


async def _main(limit: int | None, legislature: int) -> None:
    from app.db.session import init_models, make_engine, make_session_factory
    from app.ingestion.assemblee import AssembleeOpenDataClient
    from app.ingestion.organes import build_resolver_from_organes

    debut = datetime.now(timezone.utc)
    engine = make_engine()
    await init_models(engine)
    sf = make_session_factory(engine)
    client = AssembleeOpenDataClient(legislature=legislature)

    print(f"Députés (législature {legislature}, limit={limit})…")
    organes, acteurs_bruts = await client.download_amo()
    resolver = build_resolver_from_organes(organes)
    deputes = build_deputes_from_amo(acteurs_bruts, resolver)
    nb_photos = await attacher_portraits(deputes, legislature)
    async with sf() as session:
        nb_deputes = await upsert_deputes(session, deputes)
        await session.commit()
    print(
        f"  {nb_deputes} députés (référentiel AMO, {len(resolver)} groupes), "
        f"{nb_photos} photos officielles vérifiées."
    )

    bruts = await client.download_scrutins(limit=limit)
    total_scrutins = len(bruts)
    nb_votes = 0
    async with sf() as session:
        for i, brut in enumerate(bruts, start=1):
            s = brut.get("scrutin") or {}
            uid = s.get("uid")
            if not uid:
                continue
            nb_votes += await remplacer_votes_du_scrutin(
                session, str(uid), str(s.get("dateScrutin", "")), votes_du_scrutin(brut)
            )
            # Commit régulier : un run interrompu ne perd que le lot en cours.
            if i % 200 == 0:
                await session.commit()
                print(f"  [{i}/{total_scrutins}] {nb_votes} votes nominatifs écrits")
        await session.commit()
    await engine.dispose()

    duree = (datetime.now(timezone.utc) - debut).total_seconds()
    print(
        f"Terminé en {duree:.0f} s : {nb_deputes} députés, "
        f"{nb_votes} votes nominatifs sur {total_scrutins} scrutins."
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ingestion des députés et de leurs votes nominatifs"
    )
    parser.add_argument("--limit", type=int, default=None, help="Nb de scrutins récents")
    parser.add_argument("--legislature", type=int, default=17)
    args = parser.parse_args()
    asyncio.run(_main(args.limit, args.legislature))


if __name__ == "__main__":
    main()
