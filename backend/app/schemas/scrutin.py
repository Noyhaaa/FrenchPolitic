"""Contrat d'API — miroir exact du type `Scrutin` du frontend (src/types/index.ts).

Sérialisé en camelCase pour que l'app mobile puisse remplacer `@/data` par un
client API sans transformation. Le §5.3 du MVP décrit ce modèle de données.
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from app.domain.enums import (
    NiveauConfiance,
    PositionVote,
    SortAmendement,
    StatutScrutin,
    TypeSource,
)


class CamelModel(BaseModel):
    """Base : champs Python en snake_case, JSON en camelCase."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )


class PhraseSourcee(CamelModel):
    """Une phrase du résumé, systématiquement rattachée à une source (§4)."""

    phrase: str
    source_id: str


class ResultatGlobal(CamelModel):
    pour: int
    contre: int
    abstention: int
    non_votants: int


class PositionGroupe(CamelModel):
    groupe_id: str
    groupe_nom: str
    couleur: str
    position_majoritaire: PositionVote
    pour: int
    contre: int
    abstention: int
    cohesion: float | None = None


class Amendement(CamelModel):
    id: str
    objet: str
    auteur: str | None = None
    sort: SortAmendement


class SourceOfficielle(CamelModel):
    type: TypeSource
    libelle: str
    url: str


class ChangementTexte(CamelModel):
    avant: str
    apres: str


class PhaseScrutin(CamelModel):
    label: str
    statut: StatutScrutin


class ResumeScrutin(CamelModel):
    titre_clair: str
    resume: list[PhraseSourcee]
    contexte: str | None = None
    objectif: str | None = None
    historique: str | None = None
    changement: ChangementTexte | None = None
    public_concerne: list[str] = []
    confiance: NiveauConfiance
    relu_par_humain: bool
    champs_non_documentes: list[str] = []


class Scrutin(CamelModel):
    id: str
    date: str  # ISO 8601
    titre_officiel: str
    titre_clair: str
    accroche: str
    statut: StatutScrutin
    phase: PhaseScrutin | None = None
    theme: str
    scrutin_public: bool
    temps_lecture_sec: int
    resultat: ResultatGlobal
    positions_groupes: list[PositionGroupe] = []
    amendements: list[Amendement] = []
    sources: list[SourceOfficielle] = []
    resume: ResumeScrutin


class ScrutinListItem(CamelModel):
    """Version allégée pour le fil et la recherche (§3.1 / §3.3).

    Suffit à afficher une carte sans transférer tout le détail.
    """

    id: str
    date: str
    titre_clair: str
    accroche: str
    statut: StatutScrutin
    theme: str
    temps_lecture_sec: int
    resultat: ResultatGlobal

    @classmethod
    def from_scrutin(cls, s: Scrutin) -> "ScrutinListItem":
        return cls(
            id=s.id,
            date=s.date,
            titre_clair=s.titre_clair,
            accroche=s.accroche,
            statut=s.statut,
            theme=s.theme,
            temps_lecture_sec=s.temps_lecture_sec,
            resultat=s.resultat,
        )
