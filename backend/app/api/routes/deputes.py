"""Routes « Députés » (§5.2).

Un député y est décrit par des **faits** : son groupe, sa circonscription, ses
votes tels que les scrutins publics les enregistrent. Aucune note, aucun
classement, aucun adjectif (§7.4) — les statistiques du portrait sont des
comptes et des ratios, absents quand ils ne sont pas calculables (§2.5).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_dossier_repository
from app.repositories.base import DossierRepository
from app.schemas import DeputeDetail, DeputeListItem, GroupeListItem, VoteDepute

router = APIRouter(prefix="/deputes", tags=["deputes"])


@router.get("", response_model=list[DeputeListItem], summary="Annuaire des députés")
async def list_deputes(
    q: str = Query("", description="Nom, groupe ou circonscription"),
    groupe: str | None = Query(None, description="Identifiant de groupe (organeRef)"),
    limit: int = Query(600, ge=1, le=1000),
    repo: DossierRepository = Depends(get_dossier_repository),
) -> list[DeputeListItem]:
    """Annuaire complet (ordre alphabétique), filtrable par groupe et par
    recherche libre. La limite par défaut couvre l'effectif de l'Assemblée :
    l'app affiche la liste entière, sans défilement infini."""
    return await repo.list_deputes(q=q, groupe_id=groupe, limit=limit)


@router.get("/{depute_id}", response_model=DeputeDetail, summary="Fiche député")
async def get_depute(
    depute_id: str,
    limit: int = Query(30, ge=1, le=100),
    offset: int = Query(0, ge=0),
    repo: DossierRepository = Depends(get_dossier_repository),
) -> DeputeDetail:
    """Identité, portrait de vote des 12 derniers mois et première page de
    l'historique (les suivantes via `/deputes/{id}/votes`)."""
    depute = await repo.get_depute(depute_id, limit=limit, offset=offset)
    if depute is None:
        raise HTTPException(status_code=404, detail="Député introuvable")
    return depute


@router.get(
    "/{depute_id}/votes",
    response_model=list[VoteDepute],
    summary="Historique de vote paginé",
)
async def votes_depute(
    depute_id: str,
    limit: int = Query(30, ge=1, le=100),
    offset: int = Query(0, ge=0),
    repo: DossierRepository = Depends(get_dossier_repository),
) -> list[VoteDepute]:
    """Votes du député, du plus récent au plus ancien (« charger les votes plus
    anciens »). Une page plus courte que `limit` signale la fin de
    l'historique."""
    return await repo.votes_depute(depute_id, limit=limit, offset=offset)


# Référentiel des groupes, exposé à la racine : il sert le filtre de l'annuaire
# (et n'appartient à aucun député en particulier).
groupes_router = APIRouter(tags=["deputes"])


@groupes_router.get(
    "/groupes", response_model=list[GroupeListItem], summary="Groupes politiques"
)
async def list_groupes(
    repo: DossierRepository = Depends(get_dossier_repository),
) -> list[GroupeListItem]:
    """Groupes politiques (nom, abréviation, couleur) — filtres de l'annuaire."""
    return await repo.list_groupes()
