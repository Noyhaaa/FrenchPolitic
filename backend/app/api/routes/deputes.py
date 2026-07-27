"""Routes « Parlementaires » (§5.2).

Un parlementaire y est décrit par des **faits** : son groupe, sa
circonscription, ses votes tels que les scrutins publics les enregistrent.
Aucune note, aucun classement, aucun adjectif (§7.4) — les statistiques du
portrait sont des comptes et des ratios, absents quand ils ne sont pas
calculables (§2.5), ce qui est systématiquement le cas de la cohésion au Sénat
(délégation de vote par groupe, cf. `app.ingestion.senateurs`).

Le préfixe de route reste `/deputes` : c'est le contrat publié, et le
discriminant `chambre` suffit à servir les deux assemblées.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_dossier_repository
from app.domain.enums import Chambre
from app.repositories.base import DossierRepository
from app.schemas import DeputeDetail, DeputeListItem, GroupeListItem, VoteDepute

router = APIRouter(prefix="/deputes", tags=["deputes"])


@router.get(
    "", response_model=list[DeputeListItem], summary="Annuaire des parlementaires"
)
async def list_deputes(
    q: str = Query("", description="Nom, groupe ou circonscription"),
    groupe: str | None = Query(
        None, description="Identifiant de groupe (organeRef PO… ou SEN-…)"
    ),
    chambre: Chambre | None = Query(
        None, description="Restreindre à une chambre ; par défaut, les deux"
    ),
    limit: int = Query(1000, ge=1, le=2000),
    repo: DossierRepository = Depends(get_dossier_repository),
) -> list[DeputeListItem]:
    """Annuaire complet (ordre alphabétique), filtrable par chambre, par groupe
    et par recherche libre. La limite par défaut couvre l'effectif des deux
    assemblées (577 + 348) : l'app affiche la liste entière, sans défilement
    infini."""
    return await repo.list_deputes(
        q=q,
        groupe_id=groupe,
        limit=limit,
        chambre=chambre.value if chambre else None,
    )


@router.get("/{depute_id}", response_model=DeputeDetail, summary="Fiche parlementaire")
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
        raise HTTPException(status_code=404, detail="Parlementaire introuvable")
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
    chambre: Chambre | None = Query(
        None, description="Restreindre à une chambre ; par défaut, les deux"
    ),
    repo: DossierRepository = Depends(get_dossier_repository),
) -> list[GroupeListItem]:
    """Groupes politiques (nom, abréviation, couleur) — filtres de l'annuaire."""
    return await repo.list_groupes(chambre=chambre.value if chambre else None)
