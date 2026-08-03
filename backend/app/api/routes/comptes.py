"""Routes « Compte » — les seules écritures de l'API.

Le compte est **facultatif** : tout le produit (dossiers, scrutins,
parlementaires, recherche) reste consultable sans lui. Il ne sert qu'à
retrouver ses préférences d'un appareil à l'autre — thèmes suivis, département,
préférence d'alerte. Aucune donnée de navigation, aucun historique de lecture
n'est envoyé ici.

⚠️ Une seule réponse pour tous les échecs de connexion (401, message
identique) : distinguer « adresse inconnue » de « mot de passe faux »
révélerait quelles adresses ont un compte.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_utilisateur_repository, utilisateur_courant
from app.repositories.utilisateurs import Utilisateur, UtilisateurRepository
from app.schemas.utilisateur import (
    Compte,
    ConnexionRequete,
    InscriptionRequete,
    PreferencesUtilisateur,
    SessionOuverte,
)
from app.security import creer_jeton, hacher_mot_de_passe, verifier_mot_de_passe

router = APIRouter(tags=["compte"])

_IDENTIFIANTS_INVALIDES = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Adresse e-mail ou mot de passe incorrect.",
)


def _session(utilisateur: Utilisateur) -> SessionOuverte:
    return SessionOuverte(
        jeton=creer_jeton(utilisateur.id), compte=utilisateur.en_compte()
    )


@router.post(
    "/inscription",
    response_model=SessionOuverte,
    status_code=status.HTTP_201_CREATED,
    summary="Créer un compte",
)
async def inscription(
    requete: InscriptionRequete,
    repo: UtilisateurRepository = Depends(get_utilisateur_repository),
) -> SessionOuverte:
    utilisateur = await repo.creer(
        email=requete.email,
        mot_de_passe_hash=hacher_mot_de_passe(requete.mot_de_passe),
        prenom=requete.prenom,
        nom=requete.nom,
        preferences=requete.preferences,
    )
    if utilisateur is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Un compte existe déjà avec cette adresse e-mail.",
        )
    return _session(utilisateur)


@router.post("/connexion", response_model=SessionOuverte, summary="Ouvrir une session")
async def connexion(
    requete: ConnexionRequete,
    repo: UtilisateurRepository = Depends(get_utilisateur_repository),
) -> SessionOuverte:
    utilisateur = await repo.par_email(requete.email)
    if utilisateur is None or not verifier_mot_de_passe(
        requete.mot_de_passe, utilisateur.mot_de_passe_hash
    ):
        raise _IDENTIFIANTS_INVALIDES
    return _session(utilisateur)


@router.get("/moi", response_model=Compte, summary="Le compte de la session")
async def moi(utilisateur: Utilisateur = Depends(utilisateur_courant)) -> Compte:
    return utilisateur.en_compte()


@router.put(
    "/moi/preferences",
    response_model=Compte,
    summary="Enregistrer les préférences du compte",
)
async def maj_preferences(
    preferences: PreferencesUtilisateur,
    utilisateur: Utilisateur = Depends(utilisateur_courant),
    repo: UtilisateurRepository = Depends(get_utilisateur_repository),
) -> Compte:
    # Remplacement complet : l'app envoie l'état entier de ses préférences,
    # il n'y a pas de fusion partielle à arbitrer côté serveur.
    a_jour = await repo.maj_preferences(utilisateur.id, preferences)
    if a_jour is None:
        # Le compte a disparu entre l'authentification et l'écriture.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session invalide ou expirée.",
        )
    return a_jour.en_compte()
