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

Deux niveaux de correspondance, du plus strict au plus tolérant :
  1. **fold exact** (casse/accents) — la voie historique ;
  2. **signature** — fold sans espaces ni ponctuation. Elle rattrape la saleté
     de l'archive (apostrophe droite/courbe, fautes de frappe « afin de​garantir »
     avec espace manquant, tirets…) sans jamais confondre deux textes réellement
     différents : deux titres n'ont la même signature que s'ils ne diffèrent que
     par des espaces/ponctuation. La distinction de nature (« organique »…) est
     conservée (ce sont des mots, pas de la ponctuation). Le garde-fou
     d'ambiguïté (un titre → un seul dossier) s'applique aux deux niveaux (§2.5).
"""
from __future__ import annotations

import re
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


# Signature d'un titre : fold, puis on ne garde que les caractères alphanumériques
# (espaces, apostrophes, tirets, ponctuation retirés). Sous ce seuil de longueur,
# une signature est trop courte pour être discriminante — on ne l'indexe pas.
_SIGNATURE_MIN = 20


def signature_titre(titre: str) -> str:
    """Signature normalisée d'un titre (fold sans espaces ni ponctuation)."""
    return re.sub(r"[^a-z0-9]", "", fold(titre))


@dataclass(frozen=True)
class Reconciliation:
    """Table titre → dossierRef pour une législature (fold exact + signature)."""

    _ref_par_titre: dict[str, str]  # fold(titre) -> dossierRef (sans ambiguïté)
    _ref_par_signature: dict[str, str]  # signature -> dossierRef (sans ambiguïté)

    def ref_pour_titre(self, titre: str | None) -> str | None:
        """dossierRef d'un texte à partir de son titre : fold exact d'abord,
        puis signature (tolérante à la saleté de l'archive). None si aucune
        correspondance non ambiguë (§2.5 : on n'infère pas)."""
        if not titre:
            return None
        ref = self._ref_par_titre.get(fold(titre))
        if ref is not None:
            return ref
        return self._ref_par_signature.get(signature_titre(titre))

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
    refs_par_signature: dict[str, set[str]] = defaultdict(set)

    for brut in documents:
        doc = brut.get("document") or brut
        ref = doc.get("dossierRef") or ""
        if not ref.startswith(prefixe_ref):
            continue
        if (doc.get("denominationStructurelle") or "") not in _DENOMINATIONS_TEXTE:
            continue
        titre = ((doc.get("titres") or {}).get("titrePrincipal") or "").strip()
        if not titre:
            continue
        refs_par_titre[fold(titre)].add(ref)
        sig = signature_titre(titre)
        if len(sig) >= _SIGNATURE_MIN:
            refs_par_signature[sig].add(ref)

    def _sans_ambiguite(refs_par_cle: dict[str, set[str]]) -> dict[str, str]:
        return {
            cle: next(iter(refs))
            for cle, refs in refs_par_cle.items()
            if len(refs) == 1
        }

    return Reconciliation(
        _ref_par_titre=_sans_ambiguite(refs_par_titre),
        _ref_par_signature=_sans_ambiguite(refs_par_signature),
    )
