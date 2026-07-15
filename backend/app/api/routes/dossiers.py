"""Routes du cœur produit : fil, fiche, recherche (§3 du MVP).

Unité exposée : le dossier (texte de loi), qui agrège ses scrutins.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_dossier_repository
from app.repositories.base import DossierRepository
from app.schemas import Dossier, DossierListItem, Scrutin

router = APIRouter(prefix="/dossiers", tags=["dossiers"])


@router.get("", response_model=list[DossierListItem], summary="Fil des dossiers")
async def list_dossiers(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    repo: DossierRepository = Depends(get_dossier_repository),
) -> list[DossierListItem]:
    """Derniers dossiers, du plus récent au plus ancien (écran 1)."""
    return await repo.list(limit=limit, offset=offset)


@router.get("/{dossier_id}", response_model=Dossier, summary="Fiche dossier")
async def get_dossier(
    dossier_id: str,
    repo: DossierRepository = Depends(get_dossier_repository),
) -> Dossier:
    """Fiche détaillée : résumé neutre sourcé, scrutins, résultats (écran 2)."""
    dossier = await repo.get(dossier_id)
    if dossier is None:
        raise HTTPException(status_code=404, detail="Dossier introuvable")
    return dossier


# Détail d'un vote — chargé au tap depuis la liste des votes de la fiche dossier.
scrutin_router = APIRouter(prefix="/scrutins", tags=["scrutins"])


@scrutin_router.get("/{scrutin_id}", response_model=Scrutin, summary="Fiche vote")
async def get_scrutin(
    scrutin_id: str,
    repo: DossierRepository = Depends(get_dossier_repository),
) -> Scrutin:
    """Détail d'un vote : résultat, groupes et nominatif si disponible (§5.2)."""
    scrutin = await repo.get_scrutin(scrutin_id)
    if scrutin is None:
        raise HTTPException(status_code=404, detail="Scrutin introuvable")
    return scrutin


# Route de recherche exposée à la racine (/recherche) comme prévu au §6 du MVP.
search_router = APIRouter(tags=["dossiers"])


@search_router.get(
    "/recherche", response_model=list[DossierListItem], summary="Recherche simple"
)
async def search(
    q: str = Query("", description="Mots-clés (titre, thème)"),
    limit: int = Query(20, ge=1, le=100),
    repo: DossierRepository = Depends(get_dossier_repository),
) -> list[DossierListItem]:
    """Recherche plein texte sur titre clair + titre officiel + thème (écran 3)."""
    return await repo.search(q, limit=limit)
