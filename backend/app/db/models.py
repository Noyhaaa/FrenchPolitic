"""Tables PostgreSQL (§5.3, adapté pour servir l'API en lecture).

Choix : approche « document indexé ». Le scrutin complet est stocké tel qu'il est
servi (`payload` JSONB, camelCase), avec quelques colonnes indexées pour le tri et
la recherche. C'est suffisant et rapide pour le cœur lecture du MVP ; une
normalisation relationnelle plus fine (votes nominatifs, députés) viendra si des
besoins analytiques l'exigent.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ScrutinRow(Base):
    __tablename__ = "scrutin"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    # Date ISO du scrutin ("YYYY-MM-DD" ou datetime ISO) — tri lexicographique OK.
    date: Mapped[str] = mapped_column(String(32), index=True)
    statut: Mapped[str] = mapped_column(String(16))
    theme: Mapped[str] = mapped_column(String(32))
    titre_clair: Mapped[str] = mapped_column(Text)
    titre_officiel: Mapped[str] = mapped_column(Text)
    accroche: Mapped[str] = mapped_column(Text)
    scrutin_public: Mapped[bool] = mapped_column(Boolean, default=True)
    temps_lecture_sec: Mapped[int] = mapped_column(Integer, default=30)
    resultat: Mapped[dict] = mapped_column(JSONB)  # ResultatGlobal (snake_case)
    payload: Mapped[dict] = mapped_column(JSONB)  # Scrutin complet (camelCase)
    # Texte plié (minuscule, sans accents) pour la recherche ILIKE.
    search_index: Mapped[str] = mapped_column(Text, index=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )


class GroupeRow(Base):
    """Référentiel des groupes politiques (issu de l'archive AMO organes)."""

    __tablename__ = "groupe"

    id: Mapped[str] = mapped_column(String(16), primary_key=True)  # organeRef PO...
    nom: Mapped[str] = mapped_column(Text)
    abrev: Mapped[str] = mapped_column(String(32))
    couleur: Mapped[str] = mapped_column(String(9))


class SyncRunRow(Base):
    """Journal des synchronisations (observabilité, §8)."""

    __tablename__ = "sync_run"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    legislature: Mapped[int] = mapped_column(Integer)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    scrutins_vus: Mapped[int] = mapped_column(Integer, default=0)
    scrutins_upserts: Mapped[int] = mapped_column(Integer, default=0)
    anomalies: Mapped[list] = mapped_column(JSONB, default=list)
