"""Routes du cœur produit : fil, fiche, recherche (§3 du MVP).

Unité exposée : le dossier (texte de loi), qui agrège ses scrutins.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_dossier_repository
from app.repositories.base import DossierRepository
from app.schemas import Accueil, Dossier, DossierListItem, RecapMensuel, Scrutin

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


@search_router.get(
    "/accueil",
    response_model=Accueil,
    summary="Écran d'accueil complet",
)
async def accueil(
    par_section: int = Query(10, ge=1, le=30, alias="parSection"),
    repo: DossierRepository = Depends(get_dossier_repository),
) -> Accueil:
    """L'accueil en UNE réponse : à la une, aujourd'hui, hier, rangées par
    thème. Construit côté serveur pour un affichage atomique (pas de
    remplissage progressif des rangées côté client)."""
    return await repo.accueil(par_section=par_section)


@search_router.get(
    "/recap",
    response_model=RecapMensuel | None,
    summary="Activité du dernier mois actif",
)
async def recap(
    repo: DossierRepository = Depends(get_dossier_repository),
) -> RecapMensuel | None:
    """Compte des votes tenus le dernier mois ayant connu de l'activité
    (carte récap de l'accueil). Purement descriptif (§7.8) ; null si aucune
    donnée — le client masque alors la carte (§2.5)."""
    return await repo.recap_mensuel()
