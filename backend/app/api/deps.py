"""Dépendances FastAPI (injection).

Le repository est construit une fois au démarrage (voir app.main) et exposé via
`app.state`. Les routes le récupèrent par `Depends(get_dossier_repository)`, ce
qui permet de le remplacer (Postgres, ou un faux en test) sans toucher aux routes.
"""
from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.repositories.base import DossierRepository
from app.repositories.utilisateurs import Utilisateur, UtilisateurRepository
from app.security import JetonInvalide, lire_jeton


def get_dossier_repository(request: Request) -> DossierRepository:
    return request.app.state.dossier_repository


def get_utilisateur_repository(request: Request) -> UtilisateurRepository:
    return request.app.state.utilisateur_repository


# `auto_error=False` : c'est nous qui formulons le 401, avec le même message
# quelle que soit la cause (en-tête absent, jeton expiré, compte disparu).
_porteur = HTTPBearer(auto_error=False)


async def utilisateur_courant(
    justificatif: HTTPAuthorizationCredentials | None = Depends(_porteur),
    repo: UtilisateurRepository = Depends(get_utilisateur_repository),
) -> Utilisateur:
    """Le compte porteur du jeton, ou 401.

    Aucune route publique ne dépend de ceci : le produit reste consultable sans
    compte. Seules les routes de `/moi` l'exigent.
    """
    non_authentifie = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Session invalide ou expirée.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if justificatif is None:
        raise non_authentifie
    try:
        utilisateur_id = lire_jeton(justificatif.credentials)
    except JetonInvalide:
        raise non_authentifie from None
    utilisateur = await repo.par_id(utilisateur_id)
    if utilisateur is None:
        raise non_authentifie
    return utilisateur
