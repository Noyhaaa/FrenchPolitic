"""Interface d'accès aux données.

L'API dépend de ce protocole, pas d'une implémentation concrète. On peut ainsi
passer de l'in-memory (seed) à PostgreSQL (données ingérées) sans toucher aux routes.
"""
from __future__ import annotations

from typing import Protocol

from app.schemas import (
    Accueil,
    DeputeDetail,
    DeputeListItem,
    Dossier,
    DossierListItem,
    GroupeListItem,
    PortraitVote,
    RecapMensuel,
    Scrutin,
    SectionTheme,
    VoteDepute,
)


def construire_portrait(
    pour: int,
    contre: int,
    abstention: int,
    alignes: int,
    avec_majorite: int,
) -> PortraitVote:
    """Portrait de vote (12 derniers mois) à partir de comptes bruts.

    Règle unique pour les deux implémentations du repository : un ratio dont
    le **dénominateur est nul** reste `None` — le client affiche alors
    « information non disponible » au lieu d'un 0 % trompeur (§2.5).

    `alignes` / `avec_majorite` : votes exprimés dont le groupe avait une
    position majoritaire documentée, et parmi eux ceux qui la suivaient. Aucun
    taux de participation n'est produit ici — cf. `PortraitVote`.
    """
    exprimes = pour + contre + abstention
    return PortraitVote(
        cohesion_groupe=(alignes / avec_majorite) if avec_majorite else None,
        votes=exprimes,
        pour=pour,
        contre=contre,
        abstention=abstention,
    )


def ordonner_sections(sections: list[SectionTheme]) -> list[SectionTheme]:
    """Rangées thématiques de l'accueil : par volume décroissant, « Autre » en
    dernier (règle partagée par toutes les implémentations)."""
    return sorted(
        sections,
        key=lambda s: (s.theme == "Autre", -len(s.dossiers), s.theme),
    )


class DossierRepository(Protocol):
    async def list(self, limit: int = 20, offset: int = 0) -> list[DossierListItem]:
        """Fil des dossiers, du plus récent au plus ancien (§3.1)."""
        ...

    async def accueil(self, par_section: int = 10) -> Accueil:
        """Écran d'accueil complet en une réponse : à la une, aujourd'hui,
        hier, rangées par thème (au plus `par_section` dossiers chacune)."""
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

    async def recap_mensuel(self) -> RecapMensuel | None:
        """Activité du dernier mois ayant connu au moins un vote (accueil).

        None si aucune donnée (le client masque alors la carte, §2.5).
        """
        ...

    # --- Députés (§5.2) ---------------------------------------------------

    async def list_deputes(
        self, q: str = "", groupe_id: str | None = None, limit: int = 600
    ) -> list[DeputeListItem]:
        """Annuaire des députés, par ordre alphabétique.

        `q` filtre sur nom / groupe / circonscription ; `groupe_id` restreint à
        un groupe politique.
        """
        ...

    async def get_depute(
        self, depute_id: str, limit: int = 30, offset: int = 0
    ) -> DeputeDetail | None:
        """Fiche député : identité, portrait de vote (12 mois) et première
        page d'historique. None si le député est inconnu."""
        ...

    async def votes_depute(
        self, depute_id: str, limit: int = 30, offset: int = 0
    ) -> list[VoteDepute]:
        """Historique de vote paginé, du plus récent au plus ancien."""
        ...

    async def list_groupes(self) -> list[GroupeListItem]:
        """Groupes politiques (filtres de l'annuaire)."""
        ...
