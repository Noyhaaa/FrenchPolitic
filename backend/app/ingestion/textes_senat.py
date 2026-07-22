"""Exposé des motifs des textes d'origine sénatoriale (complément de textes_an).

Certains dossiers AN ne portent qu'un texte de **transmission** du Sénat : le
dispositif seul, sans exposé (« PROPOSITION DE LOI ADOPTÉE PAR LE SÉNAT,
TRANSMISE PAR M. LE PRÉSIDENT DU SÉNAT »). L'exposé des motifs vit alors sur
senat.fr. Le texte de transmission cite les numéros Sénat (« Voir les numéros :
Sénat : 452, 584, 585 et T.A. 121 (2024-2025). ») : on en dérive l'URL du PDF
Sénat et on y extrait l'exposé avec le **même découpage** que pour l'AN.

Comme pour l'AN, l'exposé reste **non neutre** (point de vue de l'auteur, §4.3) :
stocké dans un bloc `ExposeMotifs` cité et attribué (source « Texte déposé au
Sénat »), jamais fondu dans le résumé neutre. Best-effort (§2.5).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.ingestion.textes_an import decouper_expose, lire_pdf
from app.schemas import ExposeMotifs, SourceOfficielle

# Signature d'un texte de transmission Sénat (le PDF AN n'a alors pas d'exposé).
_RE_TRANSMISSION = re.compile(
    r"transmise?\s+par|adopt[eé]e?\s+par\s+le\s+s[eé]nat", re.I
)
# « Sénat : 452, 584, 585 et T.A. 121 (2024-2025). » — on prend le PREMIER
# numéro (le dépôt initial, porteur de l'exposé) et la session (« 2024-2025 »).
_RE_NUMERO = re.compile(r"s[eé]nat\s*:\s*(\d+)[^()]*\((\d{4})-\d{4}\)", re.I)

_BASE = "https://www.senat.fr/leg"


@dataclass(frozen=True)
class ReferenceSenat:
    """Référence d'un texte déposé au Sénat : session (2 chiffres) + numéro."""

    annee: str  # 2 derniers chiffres de la 1re année de session (« 24 »)
    numero: int


def reference_senat(texte_transmission: str) -> ReferenceSenat | None:
    """Référence Sénat citée dans un PDF de transmission AN.

    None si le texte n'est pas une transmission Sénat, ou si aucun numéro n'est
    citable sans ambiguïté (§2.5)."""
    if not _RE_TRANSMISSION.search(texte_transmission):
        return None
    m = _RE_NUMERO.search(texte_transmission)
    if not m:
        return None
    return ReferenceSenat(annee=m.group(2)[2:], numero=int(m.group(1)))


def urls_pdf_senat(ref: ReferenceSenat, *, projet: bool) -> list[str]:
    """URLs candidates du PDF Sénat, dérivées de la référence.

    Le préfixe dépend de la nature (`pjl` projet / `ppl` proposition) ; on tente
    l'autre en repli car l'en-tête du PDF de transmission n'est pas toujours
    fiable (projet transmis annoncé « proposition »…). Le **numéro doit être
    zéro-paddé sur 3 chiffres** (« pjl25-024.pdf », pas « pjl25-24.pdf » → 404) —
    même piège que les zéros de tête obligatoires côté AN (`textes_an.py`),
    vérifié en pratique sur plusieurs références réelles (senat.fr)."""
    numero = f"{ref.numero:03d}"
    primaire, secondaire = ("pjl", "ppl") if projet else ("ppl", "pjl")
    return [
        f"{_BASE}/{primaire}{ref.annee}-{numero}.pdf",
        f"{_BASE}/{secondaire}{ref.annee}-{numero}.pdf",
    ]


def source_senat(url_pdf: str) -> SourceOfficielle:
    """Source lisible (§7.5) : la page Sénat (même URL sans « .pdf »)."""
    page = url_pdf[:-4] if url_pdf.endswith(".pdf") else url_pdf
    return SourceOfficielle(type="texte", libelle="Texte déposé au Sénat", url=page)


def construire_expose_senat(url_pdf: str, pdf: bytes) -> ExposeMotifs | None:
    """Bloc `ExposeMotifs` (texte + source Sénat) ; None si non exploitable."""
    texte_pdf = lire_pdf(pdf)
    if not texte_pdf:
        return None
    texte = decouper_expose(texte_pdf)
    if not texte:
        return None
    return ExposeMotifs(texte=texte, source=source_senat(url_pdf))
