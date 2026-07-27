"""Interface d'accès aux données.

L'API dépend de ce protocole, pas d'une implémentation concrète. On peut ainsi
passer de l'in-memory (seed) à PostgreSQL (données ingérées) sans toucher aux routes.
"""
from __future__ import annotations

from collections import Counter
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
    ThemeListItem,
    VoteDepute,
    VoteDisputeItem,
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

    Pour un **sénateur**, `avec_majorite` vaut toujours 0 : l'ingestion ne pose
    jamais « contre son groupe » au Sénat (délégation de vote par groupe, cf.
    `app.ingestion.senateurs`). La cohésion sort donc `None` par le même chemin
    que pour un député sans référence exploitable — aucun cas particulier ici.
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


# Votes d'un même texte admis dans la rangée « Les votes les plus disputés ».
# Un texte très clivant (l'aide à mourir, le budget) monopoliserait sinon la
# rangée avec ses lectures successives, et l'écran ne montrerait plus qu'un seul
# sujet — alors que la rangée existe pour donner à voir où le Parlement s'est
# divisé, au pluriel.
MAX_DISPUTES_PAR_DOSSIER = 2


def limiter_par_dossier(
    votes: list[VoteDisputeItem], maximum: int
) -> list[VoteDisputeItem]:
    """Plafonne le nombre de votes d'un même dossier, en gardant l'ordre reçu
    (donc les plus disputés de chaque texte). Règle partagée par toutes les
    implémentations, pour que l'écran soit le même quel que soit le backend."""
    retenus: list[VoteDisputeItem] = []
    comptes: Counter[str] = Counter()
    for vote in votes:
        if comptes[vote.dossier_id] >= maximum:
            continue
        comptes[vote.dossier_id] += 1
        retenus.append(vote)
    return retenus


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

    async def search(
        self, query: str, limit: int = 20, theme: str | None = None
    ) -> list[DossierListItem]:
        """Recherche **multi-termes**, classée par pertinence (§3.3).

        Tous les termes doivent apparaître (ET) dans l'index du dossier
        (`app.domain.recherche.index_recherche`) ; le classement suit `score`,
        et à score égal la date décroissante. `theme` restreint au thème exact,
        et fonctionne **seul** (requête vide) pour parcourir un thème.
        """
        ...

    async def list_themes(self) -> list[ThemeListItem]:
        """Thèmes réellement présents + nombre de dossiers (filtre §3.3)."""
        ...

    async def recap_mensuel(self) -> RecapMensuel | None:
        """Activité du dernier mois ayant connu au moins un vote (accueil).

        None si aucune donnée (le client masque alors la carte, §2.5).
        """
        ...

    # --- Parlementaires (§5.2) --------------------------------------------

    async def list_deputes(
        self,
        q: str = "",
        groupe_id: str | None = None,
        limit: int = 600,
        chambre: str | None = None,
    ) -> list[DeputeListItem]:
        """Annuaire des parlementaires, par ordre alphabétique.

        `q` filtre sur nom / groupe / circonscription ; `groupe_id` restreint à
        un groupe politique ; `chambre` à une assemblée (« assemblee » ou
        « senat »). Sans `chambre`, les deux sont servies.
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

    async def list_groupes(self, chambre: str | None = None) -> list[GroupeListItem]:
        """Groupes politiques (filtres de l'annuaire), toutes chambres ou une seule."""
        ...
