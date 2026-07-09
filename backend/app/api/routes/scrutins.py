"""Routes du cœur produit : fil, fiche, recherche (§3 du MVP)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_scrutin_repository
from app.repositories.base import ScrutinRepository
from app.schemas import Scrutin, ScrutinListItem

router = APIRouter(prefix="/scrutins", tags=["scrutins"])


@router.get("", response_model=list[ScrutinListItem], summary="Fil des scrutins")
async def list_scrutins(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    repo: ScrutinRepository = Depends(get_scrutin_repository),
) -> list[ScrutinListItem]:
    """Derniers scrutins publics, du plus récent au plus ancien (écran 1)."""
    return await repo.list(limit=limit, offset=offset)


@router.get("/{scrutin_id}", response_model=Scrutin, summary="Fiche scrutin")
async def get_scrutin(
    scrutin_id: str,
    repo: ScrutinRepository = Depends(get_scrutin_repository),
) -> Scrutin:
    """Fiche détaillée avec résumé neutre sourcé + résultats (écran 2)."""
    scrutin = await repo.get(scrutin_id)
    if scrutin is None:
        raise HTTPException(status_code=404, detail="Scrutin introuvable")
    return scrutin


# Route de recherche exposée à la racine (/recherche) comme prévu au §6 du MVP.
search_router = APIRouter(tags=["scrutins"])


@search_router.get(
    "/recherche", response_model=list[ScrutinListItem], summary="Recherche simple"
)
async def search(
    q: str = Query("", description="Mots-clés (titre, thème)"),
    limit: int = Query(20, ge=1, le=100),
    repo: ScrutinRepository = Depends(get_scrutin_repository),
) -> list[ScrutinListItem]:
    """Recherche plein texte sur titre clair + titre officiel + thème (écran 3)."""
    return await repo.search(q, limit=limit)
