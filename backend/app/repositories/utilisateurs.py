"""Accès aux comptes utilisateurs — protocole et ses deux implémentations.

Volontairement **séparé** de `DossierRepository` : celui-ci est purement lecture
et décrit des données publiques ingérées ; les comptes s'écrivent et portent des
données personnelles. Mélanger les deux obligerait chaque implémentation de
dossier à savoir créer un utilisateur.

Comme pour les dossiers, il y a deux implémentations commutables :
  - `InMemoryUtilisateurRepository` : le défaut (`REPOSITORY_BACKEND=memory`),
    aussi ce sur quoi tourne la suite de tests. ⚠️ Rien n'y survit au
    redémarrage — un compte créé en mode mémoire est perdu à l'arrêt du
    serveur, c'est attendu.
  - `PostgresUtilisateurRepository` : la table `utilisateur`.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import UtilisateurRow
from app.schemas.utilisateur import Compte, PreferencesUtilisateur


@dataclass
class Utilisateur:
    """Un compte tel qu'il vit côté serveur — empreinte du mot de passe incluse.

    Ce n'est pas ce qui est servi : `Compte` (sans empreinte) l'est. La
    conversion est explicite, pour qu'aucune route ne puisse renvoyer
    l'empreinte par distraction.
    """

    id: str
    email: str
    mot_de_passe_hash: str
    prenom: str
    nom: str
    preferences: PreferencesUtilisateur = field(default_factory=PreferencesUtilisateur)

    def en_compte(self) -> Compte:
        return Compte(
            id=self.id,
            email=self.email,
            prenom=self.prenom,
            nom=self.nom,
            preferences=self.preferences,
        )


def normaliser_email(email: str) -> str:
    """Forme canonique : l'unicité d'une adresse ne dépend pas de sa casse."""
    return email.strip().lower()


def nouvel_identifiant() -> str:
    """UUID : ni l'URL ni le jeton n'exposent alors l'adresse e-mail."""
    return str(uuid.uuid4())


class UtilisateurRepository(Protocol):
    async def creer(
        self,
        *,
        email: str,
        mot_de_passe_hash: str,
        prenom: str,
        nom: str,
        preferences: PreferencesUtilisateur,
    ) -> Utilisateur | None:
        """Crée le compte, ou renvoie `None` si l'e-mail est déjà pris."""
        ...

    async def par_email(self, email: str) -> Utilisateur | None: ...

    async def par_id(self, utilisateur_id: str) -> Utilisateur | None: ...

    async def maj_preferences(
        self, utilisateur_id: str, preferences: PreferencesUtilisateur
    ) -> Utilisateur | None: ...


class InMemoryUtilisateurRepository:
    """Comptes en RAM (défaut et tests) — rien ne survit au redémarrage."""

    def __init__(self) -> None:
        self._par_id: dict[str, Utilisateur] = {}
        self._par_email: dict[str, str] = {}  # email normalisé → id

    async def creer(
        self,
        *,
        email: str,
        mot_de_passe_hash: str,
        prenom: str,
        nom: str,
        preferences: PreferencesUtilisateur,
    ) -> Utilisateur | None:
        cle = normaliser_email(email)
        if cle in self._par_email:
            return None
        utilisateur = Utilisateur(
            id=nouvel_identifiant(),
            email=cle,
            mot_de_passe_hash=mot_de_passe_hash,
            prenom=prenom,
            nom=nom,
            preferences=preferences,
        )
        self._par_id[utilisateur.id] = utilisateur
        self._par_email[cle] = utilisateur.id
        return utilisateur

    async def par_email(self, email: str) -> Utilisateur | None:
        identifiant = self._par_email.get(normaliser_email(email))
        return self._par_id.get(identifiant) if identifiant else None

    async def par_id(self, utilisateur_id: str) -> Utilisateur | None:
        return self._par_id.get(utilisateur_id)

    async def maj_preferences(
        self, utilisateur_id: str, preferences: PreferencesUtilisateur
    ) -> Utilisateur | None:
        utilisateur = self._par_id.get(utilisateur_id)
        if utilisateur is None:
            return None
        utilisateur.preferences = preferences
        return utilisateur


class PostgresUtilisateurRepository:
    """Comptes dans la table `utilisateur`."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    @staticmethod
    def _depuis_ligne(ligne: UtilisateurRow) -> Utilisateur:
        return Utilisateur(
            id=ligne.id,
            email=ligne.email,
            mot_de_passe_hash=ligne.mot_de_passe_hash,
            prenom=ligne.prenom,
            nom=ligne.nom,
            preferences=PreferencesUtilisateur.model_validate(ligne.preferences or {}),
        )

    async def creer(
        self,
        *,
        email: str,
        mot_de_passe_hash: str,
        prenom: str,
        nom: str,
        preferences: PreferencesUtilisateur,
    ) -> Utilisateur | None:
        cle = normaliser_email(email)
        async with self._session_factory() as session:
            # Contrôle explicite avant insertion : l'index unique reste le
            # garde-fou, mais on veut un 409 lisible plutôt qu'une erreur SQL.
            existe = await session.scalar(
                select(UtilisateurRow.id).where(UtilisateurRow.email == cle)
            )
            if existe is not None:
                return None
            ligne = UtilisateurRow(
                id=nouvel_identifiant(),
                email=cle,
                mot_de_passe_hash=mot_de_passe_hash,
                prenom=prenom,
                nom=nom,
                preferences=preferences.model_dump(by_alias=True),
            )
            session.add(ligne)
            await session.commit()
            return self._depuis_ligne(ligne)

    async def par_email(self, email: str) -> Utilisateur | None:
        async with self._session_factory() as session:
            ligne = await session.scalar(
                select(UtilisateurRow).where(
                    UtilisateurRow.email == normaliser_email(email)
                )
            )
            return self._depuis_ligne(ligne) if ligne else None

    async def par_id(self, utilisateur_id: str) -> Utilisateur | None:
        async with self._session_factory() as session:
            ligne = await session.get(UtilisateurRow, utilisateur_id)
            return self._depuis_ligne(ligne) if ligne else None

    async def maj_preferences(
        self, utilisateur_id: str, preferences: PreferencesUtilisateur
    ) -> Utilisateur | None:
        async with self._session_factory() as session:
            ligne = await session.get(UtilisateurRow, utilisateur_id)
            if ligne is None:
                return None
            ligne.preferences = preferences.model_dump(by_alias=True)
            await session.commit()
            return self._depuis_ligne(ligne)
