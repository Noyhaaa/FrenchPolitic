"""Tables PostgreSQL (§5.3, adapté pour servir l'API en lecture).

Choix : approche « document indexé ». Le dossier complet est stocké tel qu'il est
servi (`payload` JSONB, camelCase), avec quelques colonnes indexées pour le tri et
la recherche. C'est suffisant et rapide pour le cœur lecture du MVP.

Exception assumée : les **députés** et leurs **votes nominatifs**
(`depute`, `vote_depute`) sont normalisés. La fiche député croise les votes
dans l'autre sens (« tous les votes d'un député », statistiques sur 12 mois) :
le lire depuis les payloads de scrutins imposerait de tout parcourir à chaque
requête.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, Integer, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DossierRow(Base):
    __tablename__ = "dossier"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    # Date ISO du dernier scrutin ("YYYY-MM-DD" ou datetime ISO) — tri lexicographique OK.
    date: Mapped[str] = mapped_column(String(32), index=True)
    statut: Mapped[str] = mapped_column(String(16))
    theme: Mapped[str] = mapped_column(String(32))
    titre_clair: Mapped[str] = mapped_column(Text)
    titre_officiel: Mapped[str] = mapped_column(Text)
    accroche: Mapped[str] = mapped_column(Text)
    temps_lecture_sec: Mapped[int] = mapped_column(Integer, default=30)
    nombre_scrutins: Mapped[int] = mapped_column(Integer, default=0)
    # Indicateur « mis à jour » (MiseAJourDossier) — null si pas d'évolution.
    mise_a_jour: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    payload: Mapped[dict] = mapped_column(JSONB)  # Dossier complet (camelCase)
    # Texte plié (minuscule, sans accents) pour la recherche ILIKE.
    search_index: Mapped[str] = mapped_column(Text, index=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )


class ScrutinRow(Base):
    """Détail d'un vote (payload `Scrutin` complet, dont le nominatif).

    Séparé du dossier pour garder la fiche dossier légère : la liste des votes
    y est résumée, le détail (groupes + noms des votants) se charge à la demande
    via `GET /scrutins/{id}`.
    """

    __tablename__ = "scrutin"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    dossier_id: Mapped[str] = mapped_column(String(64), index=True)
    date: Mapped[str] = mapped_column(String(32), index=True)
    payload: Mapped[dict] = mapped_column(JSONB)  # Scrutin complet (camelCase)
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


class DeputeRow(Base):
    """Référentiel des députés (archive AMO « acteurs », mandats actifs).

    Un député = un `acteurRef` (PA…), la clé que citent les ventilations
    nominatives des scrutins. Les champs de groupe sont dénormalisés (nom +
    couleur) pour servir l'annuaire sans jointure ; ils suivent le mandat GP
    en cours. Champ non documenté par la source → chaîne vide / NULL, jamais
    une valeur devinée (§2.5).
    """

    __tablename__ = "depute"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)  # acteurRef PA…
    nom: Mapped[str] = mapped_column(Text, index=True)  # « Prénom Nom »
    groupe_id: Mapped[str] = mapped_column(String(32), index=True)  # organeRef PO…
    groupe_nom: Mapped[str] = mapped_column(Text)
    groupe_couleur: Mapped[str] = mapped_column(String(9))
    circonscription: Mapped[str] = mapped_column(Text)
    # Début du mandat dans le groupe (ISO) — NULL si la source ne le donne pas.
    depuis: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # Photo officielle : l'open data ne la fournit pas → NULL (l'app affiche
    # les initiales). On n'invente pas d'URL de portrait (§2.5).
    portrait_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Texte plié (minuscule, sans accents) pour la recherche ILIKE de l'annuaire.
    search_index: Mapped[str] = mapped_column(Text, index=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )


class VoteDeputeRow(Base):
    """Vote d'un député sur un scrutin public (§5.2).

    Une ligne par (député, scrutin) : ~570 députés × ~5 000 scrutins. Table
    volumineuse mais plate, écrite par lots à l'ingestion et lue par l'index
    (acteur_ref, date desc) pour l'historique paginé de la fiche député.

    `contre_son_groupe` est un **fait déduit** (position du député ≠
    `positionMajoritaire` de son groupe sur CE scrutin), calculé seulement pour
    les positions exprimées ; NULL quand le groupe n'a pas de position
    majoritaire exploitable — l'app masque alors l'indication (§2.5, §7.4).
    """

    __tablename__ = "vote_depute"

    acteur_ref: Mapped[str] = mapped_column(String(32), primary_key=True)
    scrutin_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    date: Mapped[str] = mapped_column(String(32), index=True)
    position: Mapped[str] = mapped_column(String(16))
    contre_son_groupe: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    __table_args__ = (
        # Historique d'un député, du plus récent au plus ancien (pagination).
        Index("ix_vote_depute_acteur_date", "acteur_ref", text("date DESC")),
    )


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
    dossiers_upserts: Mapped[int] = mapped_column(Integer, default=0)
    anomalies: Mapped[list] = mapped_column(JSONB, default=list)
