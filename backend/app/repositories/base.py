"""Interface d'accès aux données.

L'API dépend de ce protocole, pas d'une implémentation concrète. On peut ainsi
passer de l'in-memory (V0) à PostgreSQL (Phase 1) sans toucher aux routes.
"""
from __future__ import annotations

from typing import Protocol

from app.schemas import Scrutin, ScrutinListItem


class ScrutinRepository(Protocol):
    async def list(self, limit: int = 20, offset: int = 0) -> list[ScrutinListItem]:
        """Fil des scrutins, du plus récent au plus ancien (§3.1)."""
        ...

    async def get(self, scrutin_id: str) -> Scrutin | None:
        """Fiche détaillée d'un scrutin (§3.2)."""
        ...

    async def search(self, query: str, limit: int = 20) -> list[ScrutinListItem]:
        """Recherche plein texte titre clair + titre officiel + thème (§3.3)."""
        ...
