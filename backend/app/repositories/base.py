"""Interface d'accès aux données.

L'API dépend de ce protocole, pas d'une implémentation concrète. On peut ainsi
passer de l'in-memory (seed) à PostgreSQL (données ingérées) sans toucher aux routes.
"""
from __future__ import annotations

from typing import Protocol

from app.schemas import Dossier, DossierListItem, Scrutin


class DossierRepository(Protocol):
    async def list(self, limit: int = 20, offset: int = 0) -> list[DossierListItem]:
        """Fil des dossiers, du plus récent au plus ancien (§3.1)."""
        ...

    async def get(self, dossier_id: str) -> Dossier | None:
        """Fiche détaillée d'un dossier (§3.2)."""
        ...

    async def get_scrutin(self, scrutin_id: str) -> Scrutin | None:
        """Détail d'un vote : groupes + nominatif si disponible (§3.2, §5.2)."""
        ...

    async def search(self, query: str, limit: int = 20) -> list[DossierListItem]:
        """Recherche plein texte titre clair + titre officiel + thème (§3.3)."""
        ...
