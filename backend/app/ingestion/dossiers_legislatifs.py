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

La même archive sert enfin à **joindre les deux chambres** (`JointureSenat`) :
ses `dossierParlementaire` portent le chemin du dossier Sénat correspondant, ce
qui permet de ranger un scrutin sénatorial dans le dossier où vivent déjà les
votes de l'Assemblée — sans quoi un même texte apparaîtrait deux fois dans le fil.
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


# Un `dossierRef` porte lui-même sa législature : « DLR5L17N54085 » → 17.
_RE_LEGISLATURE_REF = re.compile(r"^DLR\d+L(\d+)N", re.I)


def legislature_du_ref(dossier_ref: str | None) -> str | None:
    """Législature encodée dans un `dossierRef`, sinon None.

    C'est la seule source fiable pour bâtir l'URL du dossier sur
    assemblee-nationale.fr : la législature portée par un scrutin dépend de la
    chambre qui l'a émis (le Sénat numérote par **session**, pas par
    législature), et un dossier peut n'avoir que des votes sénatoriaux sur un
    run donné. La déduire du `dossierRef` la rend indépendante de l'ordre des
    votes vus.
    """
    if not dossier_ref:
        return None
    m = _RE_LEGISLATURE_REF.match(dossier_ref)
    return m.group(1) if m else None


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


# ---------------------------------------------------------------------------
# Jointure Assemblée ↔ Sénat
# ---------------------------------------------------------------------------

# Slug d'un dossier Sénat dans une URL senat.fr : « …/dossier-legislatif/pjl25-689.html ».
_RE_SLUG_SENAT = re.compile(r"/dossier-legislatif/([\w.-]+?)(?:\.html?)?$", re.I)
# Slug d'un dossier AN dans une URL assemblee-nationale.fr :
# « …/17/dossiers/projet_loi_urgence_….asp » (ancienne forme, celle que cite le
# Sénat) ou « …/dyn/17/dossiers/DLR5L17N54085 » (forme actuelle).
_RE_SLUG_AN = re.compile(r"/dossiers/([\w.-]+?)(?:\.asp)?$", re.I)


def slug_dossier_senat(url_ou_slug: str | None) -> str | None:
    """Slug Sénat (« pjl25-689 ») extrait d'une URL de dossier, sinon None.

    Tolère qu'on lui passe déjà un slug nu : c'est la forme que porte la page
    d'un scrutin Sénat comme le champ `senatChemin` de l'archive AN."""
    if not url_ou_slug:
        return None
    valeur = url_ou_slug.strip()
    m = _RE_SLUG_SENAT.search(valeur)
    if m:
        return m.group(1).lower()
    return valeur.lower() if "/" not in valeur and valeur else None


@dataclass(frozen=True)
class JointureSenat:
    """Table de correspondance entre un dossier Sénat et son `dossierRef` AN.

    Construite depuis les `dossierParlementaire` de l'archive AN, qui portent
    **eux-mêmes** les deux clés — aucune source tierce, aucune requête réseau :

    - `titreDossier.senatChemin` → l'URL du dossier Sénat. C'est la voie
      directe : le scrutin Sénat cite son dossier, on remonte au `dossierRef`.
    - `titreDossier.titreChemin` → le slug AN. Il sert au **repli inverse** :
      quand l'AN n'a pas (encore) renseigné `senatChemin`, la page du dossier
      Sénat, elle, cite l'URL du dossier AN — dont on extrait ce slug. La casse
      diffère entre les deux sources (« PJL_relance_… » côté Sénat, tout en
      minuscules dans l'archive) : la clé est donc repliée en minuscules.

    Comme pour `Reconciliation`, un slug qui désignerait plusieurs `dossierRef`
    est écarté plutôt que départagé au hasard (§2.5).
    """

    _ref_par_slug_senat: dict[str, str]
    _ref_par_slug_an: dict[str, str]

    def ref_pour_slug_senat(self, url_ou_slug: str | None) -> str | None:
        slug = slug_dossier_senat(url_ou_slug)
        return self._ref_par_slug_senat.get(slug) if slug else None

    def ref_pour_url_an(self, url: str | None) -> str | None:
        """`dossierRef` derrière une URL de dossier AN citée par le Sénat.

        L'URL peut déjà porter le `dossierRef` (forme `/dyn/17/dossiers/DLR…`) :
        on le reconnaît alors directement, sans passer par l'index des slugs."""
        if not url:
            return None
        m = _RE_SLUG_AN.search(url.strip())
        if not m:
            return None
        slug = m.group(1)
        if slug.upper().startswith("DLR"):
            return slug.upper()
        return self._ref_par_slug_an.get(slug.lower())

    def __len__(self) -> int:
        return len(self._ref_par_slug_senat)


def construire_jointure_senat(dossiers: list[dict]) -> JointureSenat:
    """Construit la jointure depuis les `dossierParlementaire` de l'archive AN.

    Contrairement à `construire_reconciliation`, on ne filtre pas par
    législature : un dossier reporté d'une législature à l'autre garde son
    `dossierRef`, et le garde-fou d'ambiguïté suffit à écarter une éventuelle
    collision de slug (§2.5)."""
    refs_par_slug_senat: dict[str, set[str]] = defaultdict(set)
    refs_par_slug_an: dict[str, set[str]] = defaultdict(set)

    for brut in dossiers:
        dp = brut.get("dossierParlementaire") or brut
        uid = dp.get("uid") or ""
        if not uid:
            continue
        titres = dp.get("titreDossier") or {}
        slug_senat = slug_dossier_senat(titres.get("senatChemin"))
        if slug_senat:
            refs_par_slug_senat[slug_senat].add(uid)
        slug_an = (titres.get("titreChemin") or "").strip().lower()
        if slug_an:
            refs_par_slug_an[slug_an].add(uid)

    def _sans_ambiguite(refs_par_cle: dict[str, set[str]]) -> dict[str, str]:
        return {
            cle: next(iter(refs))
            for cle, refs in refs_par_cle.items()
            if len(refs) == 1
        }

    return JointureSenat(
        _ref_par_slug_senat=_sans_ambiguite(refs_par_slug_senat),
        _ref_par_slug_an=_sans_ambiguite(refs_par_slug_an),
    )
