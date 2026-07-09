"""Dépendances FastAPI (injection).

Le repository est construit une fois au démarrage (voir app.main) et exposé via
`app.state`. Les routes le récupèrent par `Depends(get_scrutin_repository)`, ce
qui permet de le remplacer (Postgres, ou un faux en test) sans toucher aux routes.
"""
from __future__ import annotations

from fastapi import Request

from app.repositories.base import ScrutinRepository


def get_scrutin_repository(request: Request) -> ScrutinRepository:
    return request.app.state.scrutin_repository
