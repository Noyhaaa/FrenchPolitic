"""Contrat d'API des députés — miroir exact des types du frontend
(`src/types/index.ts`).

Le sens de vote d'un député n'existe que pour les **scrutins publics**
(nominatifs, §5.2) : c'est la seule source de l'historique. « Contre son
groupe » est un **fait déduit** (position du député ≠ `positionMajoritaire` de
son groupe sur le MÊME scrutin), jamais une interprétation (§7.4). Toute
statistique non calculable reste `None` — le client masque alors la donnée
plutôt que de la combler (§2.5).
"""
from __future__ import annotations

from app.domain.enums import ObjetVote, PositionVote
from app.schemas.scrutin import CamelModel


class Depute(CamelModel):
    """Un député (organe « acteur » de l'open data AN)."""

    id: str  # acteurRef AMO (PA…)
    nom: str
    groupe_id: str
    groupe_nom: str
    groupe_couleur: str
    circonscription: str
    depuis: str | None = None  # début de mandat (ISO), None si non documenté
    portrait_url: str | None = None  # photo officielle, sinon initiales côté app


class DeputeListItem(CamelModel):
    """Version allégée pour l'annuaire (photo comprise : c'est elle qui rend la
    liste identifiable d'un coup d'œil)."""

    id: str
    nom: str
    groupe_nom: str
    groupe_couleur: str
    circonscription: str
    portrait_url: str | None = None

    @classmethod
    def from_depute(cls, d: Depute) -> "DeputeListItem":
        return cls(
            id=d.id,
            nom=d.nom,
            groupe_nom=d.groupe_nom,
            groupe_couleur=d.groupe_couleur,
            circonscription=d.circonscription,
            portrait_url=d.portrait_url,
        )


class PortraitVote(CamelModel):
    """Statistiques agrégées sur les 12 derniers mois.

    PAS de taux de participation : l'open data ne recense que les votants
    physiques d'un scrutin public (268 en moyenne sur 577), si bien que tout
    ratio de présence se lirait comme un score d'absentéisme que la source ne
    soutient pas (§7.4 — on décrit, on ne juge pas). Restent des faits
    vérifiables : ce qu'il a voté, et son alignement sur son groupe.

    `cohesion_groupe` est un ratio 0..1, absent quand il n'est pas calculable
    (aucun vote exprimé dont le groupe avait une position majoritaire) —
    « information non disponible » plutôt qu'un zéro trompeur (§2.5).
    """

    cohesion_groupe: float | None = None
    votes: int  # scrutins publics où le député a exprimé un vote
    pour: int
    contre: int
    abstention: int


class VoteDepute(CamelModel):
    """Une entrée de l'historique de vote d'un député."""

    scrutin_id: str
    date: str
    objet_type: ObjetVote
    titre: str  # titre clair du dossier / objet du vote d'amendement
    dossier_id: str | None = None
    position: PositionVote
    # True si la position diffère de la majorité de son groupe sur ce scrutin.
    # None quand le groupe n'a pas de position majoritaire documentée (§2.5).
    contre_son_groupe: bool | None = None


class DeputeDetail(Depute):
    """Fiche complète — `GET /deputes/{id}`.

    `historique` est paginé (du plus récent au plus ancien) : une page plus
    courte que la limite demandée signale la fin de l'historique.
    """

    portrait: PortraitVote
    historique: list[VoteDepute] = []


class GroupeListItem(CamelModel):
    """Groupe politique tel qu'exposé par les filtres de l'annuaire."""

    id: str
    nom: str
    abrev: str
    couleur: str
