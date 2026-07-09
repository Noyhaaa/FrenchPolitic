"""Référentiel des groupes politiques (organes de type « GP »).

Construit à partir de l'archive AMO (acteurs/mandats/organes) de l'Assemblée :
mappe un `organeRef` (PO…) vers un nom lisible + une couleur. La ventilation des
votes ne cite que des `organeRef` ; ce résolveur leur donne un nom pour l'UI.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.utils.text import fold

# Couleurs par abréviation de groupe (17e législature). Purement cosmétique
# (la neutralité §7 porte sur le contenu, pas sur la couleur des groupes).
GROUP_COLORS: dict[str, str] = {
    "RN": "#1B3A5C",
    "LFI-NFP": "#C0392B",
    "EPR": "#F5A623",
    "DR": "#2E6FB5",
    "SOC": "#E24A6E",
    "ECOS": "#2F8F4E",
    "DEM": "#F58220",
    "HOR": "#6EC1E4",
    "GDR": "#A8324A",
    "LIOT": "#F2C94C",
    "UDR": "#123A5A",
    "UDDPLR": "#123A5A",
    "NI": "#9AA0A6",
}
_COULEUR_DEFAUT = "#9AA0A6"


@dataclass(frozen=True)
class GroupInfo:
    id: str
    nom: str
    abrev: str
    couleur: str


class GroupResolver:
    def __init__(self, groups: dict[str, GroupInfo]) -> None:
        self._groups = groups

    def resolve(self, organe_ref: str) -> GroupInfo:
        info = self._groups.get(organe_ref)
        if info is not None:
            return info
        # Groupe inconnu : on garde la référence comme nom plutôt que d'inventer.
        return GroupInfo(id=organe_ref, nom=organe_ref, abrev="?", couleur=_COULEUR_DEFAUT)

    def all(self) -> list[GroupInfo]:
        return list(self._groups.values())

    def __len__(self) -> int:
        return len(self._groups)


def _couleur_pour(abrev: str) -> str:
    return GROUP_COLORS.get(fold(abrev).upper(), GROUP_COLORS.get(abrev, _COULEUR_DEFAUT))


def build_resolver_from_organes(organe_wrappers: list[dict]) -> GroupResolver:
    """Construit le résolveur à partir des JSON d'organes (clé « organe »).

    Ne retient que les groupes politiques actifs (codeType == 'GP' sans date de
    fin). Fonction pure : testable avec quelques organes en entrée.
    """
    groups: dict[str, GroupInfo] = {}
    for wrapper in organe_wrappers:
        organe = wrapper.get("organe", wrapper)
        if organe.get("codeType") != "GP":
            continue
        vie = organe.get("viMoDe") or {}
        if vie.get("dateFin"):
            continue  # groupe dissous
        uid = organe.get("uid")
        if not uid:
            continue
        abrev = organe.get("libelleAbrev") or organe.get("libelleAbrege") or "?"
        groups[uid] = GroupInfo(
            id=uid,
            nom=organe.get("libelle") or uid,
            abrev=abrev,
            couleur=_couleur_pour(abrev),
        )
    return GroupResolver(groups)
