from __future__ import annotations

from fastapi import APIRouter

from app import __version__
from app.config import settings

router = APIRouter(tags=["système"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__, "env": settings.app_env}
