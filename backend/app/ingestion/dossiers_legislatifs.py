"""Enrichissement depuis l'archive « dossiers législatifs » de l'AN (§5.1).

Cette archive (open data, sans clé) ne contient PAS le texte des lois ni
l'exposé des motifs (ça, c'est Légifrance/PISTE — Phase B). Mais elle fournit,
par `dossierRef`, le **titre officiel canonique** du texte. On s'en sert pour :

**Réconcilier** les scrutins dépourvus de `dossierRef` : beaucoup citent leur
texte dans leur objet (« … de la proposition de loi visant à… »). Si ce titre
correspond **exactement** (à l'accent/la casse près) à un titre officiel de la
législature, on récupère le vrai `dossierRef` — le vote rejoint alors le vrai
dossier (au lieu d'un dossier reconstitué `TXT-…`) et gagne le lien vers la page
officielle du dossier (§7.5). Correspondance exacte uniquement : en cas
d'ambiguïté (un titre → plusieurs dossiers), on s'abstient (§2.5).

On n'importe PAS les titres de l'archive : ils sont en minuscules et truffés de
variantes/fragments, moins propres que le libellé déjà porté par le scrutin.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from app.utils.text import fold

# Types de documents portant le titre du texte lui-même (hors rapports, avis,
# motions…), tels que classés par l'open data (`denominationStructurelle`).
_DENOMINATIONS_TEXTE = frozenset(
    {
        "Proposition de loi",
        "Projet de loi",
        "Proposition de résolution",
        "Résolution",
    }
)


@dataclass(frozen=True)
class Reconciliation:
    """Table titre → dossierRef pour une législature (correspondance exacte)."""

    _ref_par_titre: dict[str, str]  # fold(titre) -> dossierRef (sans ambiguïté)

    def ref_pour_titre(self, titre: str | None) -> str | None:
        """dossierRef d'un texte à partir de son titre, si correspondance
        exacte et non ambiguë ; None sinon (on n'infère pas)."""
        if not titre:
            return None
        return self._ref_par_titre.get(fold(titre))

    def __len__(self) -> int:
        return len(self._ref_par_titre)


def construire_reconciliation(
    documents: list[dict], legislature: int
) -> Reconciliation:
    """Construit la table depuis les documents de l'archive, restreinte à la
    législature (pour ne pas raccorder un texte à un dossier d'une autre
    législature) et aux seuls textes de loi (pas les rapports). Un titre porté
    par plusieurs dossiers est écarté (ambiguïté → on ne devine pas, §2.5)."""
    prefixe_ref = f"DLR5L{legislature}"
    refs_par_titre: dict[str, set[str]] = defaultdict(set)

    for brut in documents:
        doc = brut.get("document") or brut
        ref = doc.get("dossierRef") or ""
        if not ref.startswith(prefixe_ref):
            continue
        if (doc.get("denominationStructurelle") or "") not in _DENOMINATIONS_TEXTE:
            continue
        titre = ((doc.get("titres") or {}).get("titrePrincipal") or "").strip()
        if titre:
            refs_par_titre[fold(titre)].add(ref)

    ref_par_titre = {
        titre: next(iter(refs))
        for titre, refs in refs_par_titre.items()
        if len(refs) == 1
    }
    return Reconciliation(_ref_par_titre=ref_par_titre)
