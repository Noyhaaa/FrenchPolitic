"""Les amendements tranchés en commission saisie au fond, à l'Assemblée.

Avant la séance, la commission saisie **au fond** examine le texte et l'amende :
ce qu'elle adopte entre dans le texte que la séance discute. On en restitue le
seul décompte (adoptés, rejetés), par commission nommée — pas le détail : un
vote de commission n'est pas un vote de l'Assemblée, et le modèle ne le porte
pas (pas de scrutin, pas de nominatif).

Ce qui n'est PAS compté, faute de quoi le chiffre tromperait (§2.5) :
- les amendements d'une commission saisie **pour avis** — elle ne modifie pas
  le texte, elle propose des amendements que la commission au fond ou la
  séance reprendront, ou non (mesuré en L17 : 1 333 adoptés) ;
- un amendement dont l'organe d'examen ne se rattache à aucune saisine
  documentée du dossier (mesuré : 608) ;
- les commissions du **Sénat** : l'archive est celle de l'Assemblée.
"""
from __future__ import annotations

import re
from collections import defaultdict

from app.ingestion.navette import _descendants
from app.schemas import AmendementsCommission

# « EXANR5L17PO420120B2851P0D1 » : examen du texte n° 2851 par l'organe PO420120.
_RE_ORGANE_EXAMEN = re.compile(r"^EXANR5L\d+(PO\d+)")

# Commission permanente, commission spéciale : les seuls organes qu'un texte
# peut saisir au fond à l'Assemblée.
_TYPES_COMMISSION = frozenset({"COMPER", "CNPS"})

# dossierRef → organe d'examen → [adoptés, rejetés]
CompteursCommission = dict[str, dict[str, list[int]]]


def organe_examen(examen_ref: object) -> str | None:
    """L'organe qui a examiné l'amendement, lu dans son `examenRef`."""
    if not isinstance(examen_ref, str):
        return None
    m = _RE_ORGANE_EXAMEN.match(examen_ref)
    return m.group(1) if m else None


def nouveaux_compteurs() -> CompteursCommission:
    return defaultdict(lambda: defaultdict(lambda: [0, 0]))


def compter(
    compteurs: CompteursCommission, dossier_ref: str, organe: str, adopte: bool
) -> None:
    compteurs[dossier_ref][organe][0 if adopte else 1] += 1


def commissions_au_fond(actes_legislatifs: object) -> list[str]:
    """Les commissions saisies au fond à l'Assemblée, dans l'ordre des lectures
    (`AN1-COM-FOND-SAISIE`, `AN2-…`, `ANNLEC-…`…), sans doublon."""
    vues: list[str] = []
    for acte in _descendants(actes_legislatifs):
        code = acte.get("codeActe") or ""
        organe = acte.get("organeRef")
        if (
            isinstance(code, str)
            and code.startswith("AN")
            and code.endswith("-COM-FOND-SAISIE")
            and isinstance(organe, str)
            and organe not in vues
        ):
            vues.append(organe)
    return vues


def noms_commissions(*organes: list[dict]) -> dict[str, str]:
    """uid → libellé officiel (« Commission des affaires sociales »). Les
    archives suivantes complètent les premières sans les écraser."""
    noms: dict[str, str] = {}
    for liste in organes:
        for wrapper in liste:
            organe = wrapper.get("organe") or wrapper
            uid = organe.get("uid")
            libelle = organe.get("libelle")
            if (
                organe.get("codeType") in _TYPES_COMMISSION
                and isinstance(uid, str)
                and isinstance(libelle, str)
                and libelle.strip()
                and uid not in noms
            ):
                noms[uid] = libelle.strip()
    return noms


def amendements_commission(
    par_organe: dict[str, list[int]] | None,
    au_fond: list[str],
    noms: dict[str, str],
) -> list[AmendementsCommission]:
    """Le décompte de chaque commission saisie au fond qui a tranché des
    amendements. Une commission sans nom connu n'est pas affichée : on ne
    montre jamais un identifiant `PO…` en guise de nom (§2.5)."""
    if not par_organe:
        return []
    resultat: list[AmendementsCommission] = []
    for organe in au_fond:
        adoptes, rejetes = par_organe.get(organe, (0, 0))
        nom = noms.get(organe)
        if nom and adoptes + rejetes > 0:
            resultat.append(
                AmendementsCommission(commission=nom, adoptes=adoptes, rejetes=rejetes)
            )
    return resultat
