"""Contrat d'API des comptes — miroir de `src/types/index.ts` côté app.

⚠️ Ce sont les **premiers schémas d'entrée** du dépôt : jusqu'ici l'API ne
servait que des réponses. Deux conséquences tenues ici :

  - on ne renvoie **jamais** l'empreinte du mot de passe (`Compte` ne la porte
    pas, et c'est le seul modèle exposé) ;
  - on ne collecte que ce dont l'app se sert. Le parcours d'inscription de la
    maquette demandait aussi un téléphone et une date de naissance : rien dans
    le produit ne les utilise, ils ne sont donc pas demandés (minimisation).
"""
from __future__ import annotations

import re
from typing import Annotated

from pydantic import AfterValidator, Field, field_validator

from app.schemas.scrutin import CamelModel

# Longueur minimale du mot de passe, partagée par le schéma et l'app mobile
# (`MOT_DE_PASSE_MIN` dans src/screens/OnboardingScreen.tsx).
MOT_DE_PASSE_MIN = 8

# ⚠️ Volontairement **pas** `pydantic.EmailStr` : il exige `email-validator`,
# une dépendance qui n'apporterait ici qu'un contrôle de forme — nous ne
# vérifions ni le domaine, ni la délivrabilité. Elle a surtout un défaut :
# `EmailStr` échoue à l'**import** du module si le paquet manque, donc toute
# l'API tombe (pas seulement les comptes) sur un environnement pas réinstallé
# après un `git pull`. Ce contrôle-ci est le miroir exact de celui de l'app
# (`RE_EMAIL` dans src/utils/validation.ts).
_RE_EMAIL = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]{2,}$")


def _valider_email(valeur: str) -> str:
    nettoye = valeur.strip()
    if not _RE_EMAIL.match(nettoye):
        raise ValueError("adresse e-mail invalide")
    return nettoye


AdresseEmail = Annotated[str, AfterValidator(_valider_email)]


class PreferencesUtilisateur(CamelModel):
    """Ce que le parcours d'inscription recueille.

    Aucun champ n'est obligatoire : l'inscription est passable, et un compte
    créé sans préférence est un compte valide. Les thèmes sont des libellés de
    `ThemeScrutin` ; le département est celui d'une circonscription de
    parlementaire, tel que l'annuaire l'écrit.
    """

    themes: list[str] = []
    departement: str | None = None
    # Préférence d'alerte, mémorisée pour le jour où les alertes existeront.
    # ⚠️ Aucune notification n'est envoyée aujourd'hui (hors périmètre V1).
    alertes: bool = False


class Compte(CamelModel):
    """Le compte tel qu'il est renvoyé — sans rien de secret."""

    id: str
    email: str
    prenom: str
    nom: str
    preferences: PreferencesUtilisateur


class SessionOuverte(CamelModel):
    """Réponse d'une inscription ou d'une connexion réussie."""

    jeton: str
    compte: Compte


class InscriptionRequete(CamelModel):
    prenom: str = Field(min_length=1, max_length=100)
    nom: str = Field(min_length=1, max_length=100)
    email: AdresseEmail
    mot_de_passe: str = Field(min_length=MOT_DE_PASSE_MIN, max_length=200)
    preferences: PreferencesUtilisateur = PreferencesUtilisateur()

    @field_validator("prenom", "nom")
    @classmethod
    def _nettoyer(cls, valeur: str) -> str:
        nettoye = valeur.strip()
        if not nettoye:
            raise ValueError("ne peut pas être vide")
        return nettoye


class ConnexionRequete(CamelModel):
    # Ni contrôle de forme sur l'adresse, ni longueur minimale sur le mot de
    # passe : une adresse malformée est un identifiant faux, pas une requête
    # malformée. Elle ne correspondra à aucun compte et recevra donc le même
    # 401 que n'importe quel autre échec — une seule réponse pour tous les cas,
    # sans quoi la validation dirait déjà quelque chose à qui sonde l'API.
    email: str
    mot_de_passe: str
