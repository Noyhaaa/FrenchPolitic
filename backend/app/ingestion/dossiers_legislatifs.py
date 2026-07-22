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

Trois niveaux de correspondance, du plus strict au plus tolérant :
  1. **fold exact** (casse/accents) — la voie historique ;
  2. **signature** — fold sans espaces ni ponctuation. Elle rattrape la saleté
     de l'archive (apostrophe droite/courbe, fautes de frappe « afin de​garantir »
     avec espace manquant, tirets…) sans jamais confondre deux textes réellement
     différents : deux titres n'ont la même signature que s'ils ne diffèrent que
     par des espaces/ponctuation. La distinction de nature (« organique »…) est
     conservée (ce sont des mots, pas de la ponctuation) ;
  3. **préfixe** — le titre cité par l'objet du vote est un préfixe strict d'un
     titre officiel plus long. L'objet d'un scrutin, côté open data AN, est
     parfois tronqué aux alentours de 90 caractères (vérifié en pratique sur
     plusieurs dossiers `TXT-` réels) : le titre cité s'arrête net en plein mot,
     bien avant la fin du titre officiel. Seul le sens de comparaison
     query-préfixe-de-archive est tenté (jamais l'inverse : on ne devine pas la
     fin d'un titre officiel court à partir d'une citation plus longue).
Le garde-fou d'ambiguïté (un titre → un seul dossier) s'applique aux trois
niveaux (§2.5) : à signature égale ou en préfixe, si plusieurs `dossierRef`
sont candidats, on s'abstient plutôt que de deviner.
"""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field

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

# Longueur minimale de la signature du titre CITÉ (côté vote) pour tenter une
# correspondance par préfixe. Plus haute que `_SIGNATURE_MIN` : la troncature
# observée sur l'objet des votes tombe autour de 90 caractères bruts, un
# préfixe plus court serait trop générique (risque de préfixes communs entre
# textes réellement différents — mitigé de toute façon par le garde-fou
# d'ambiguïté, mais inutile de le solliciter sur des cas non pertinents).
_PREFIXE_MIN = 40


def signature_titre(titre: str) -> str:
    """Signature normalisée d'un titre (fold sans espaces ni ponctuation)."""
    return re.sub(r"[^a-z0-9]", "", fold(titre))


@dataclass(frozen=True)
class Reconciliation:
    """Table titre → dossierRef pour une législature (fold exact + signature +
    préfixe)."""

    _ref_par_titre: dict[str, str]  # fold(titre) -> dossierRef (sans ambiguïté)
    _ref_par_signature: dict[str, str]  # signature -> dossierRef (sans ambiguïté)
    # signature brute (NON filtrée par ambiguïté) -> dossierRefs candidats ;
    # sert uniquement au repli préfixe, qui doit voir toutes les collisions
    # potentielles pour s'abstenir correctement (§2.5).
    _refs_par_signature_brute: dict[str, frozenset[str]] = field(default_factory=dict)

    def ref_pour_titre(self, titre: str | None) -> str | None:
        """dossierRef d'un texte à partir de son titre : fold exact d'abord,
        puis signature (tolérante à la saleté de l'archive), puis préfixe
        (objet de vote tronqué côté open data). None si aucune correspondance
        non ambiguë (§2.5 : on n'infère pas)."""
        if not titre:
            return None
        ref = self._ref_par_titre.get(fold(titre))
        if ref is not None:
            return ref
        sig = signature_titre(titre)
        ref = self._ref_par_signature.get(sig)
        if ref is not None:
            return ref
        return self._ref_par_prefixe(sig)

    def _ref_par_prefixe(self, sig: str) -> str | None:
        if len(sig) < _PREFIXE_MIN:
            return None
        refs: set[str] = set()
        for cle, candidats in self._refs_par_signature_brute.items():
            if cle.startswith(sig):
                refs |= candidats
                if len(refs) > 1:
                    return None
        return next(iter(refs)) if len(refs) == 1 else None

    def __len__(self) -> int:
        return len(self._ref_par_titre)


def construire_reconciliation(
    documents: list[dict], legislatures: tuple[int, ...]
) -> Reconciliation:
    """Construit la table depuis les documents de l'archive, restreinte aux
    législatures données (typiquement la courante + la précédente — un dossier
    peut être **reporté** d'une législature à l'autre après une dissolution,
    sous le même `dossierRef` ; sans ce repli, un tel texte n'est jamais
    retrouvé par titre et se fragmente en dossier reconstitué `TXT-…`) et aux
    seuls textes de loi (pas les rapports). Le garde-fou d'ambiguïté (un titre
    → un seul dossier) protège déjà contre une collision de titre entre deux
    législatures différentes : élargir la fenêtre ne l'affaiblit pas (§2.5)."""
    prefixes = tuple(f"DLR5L{leg}" for leg in legislatures)
    refs_par_titre: dict[str, set[str]] = defaultdict(set)
    refs_par_signature: dict[str, set[str]] = defaultdict(set)

    for brut in documents:
        doc = brut.get("document") or brut
        ref = doc.get("dossierRef") or ""
        if not ref.startswith(prefixes):
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
        _refs_par_signature_brute={
            cle: frozenset(refs) for cle, refs in refs_par_signature.items()
        },
    )
