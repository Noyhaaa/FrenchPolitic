"""Utilitaires texte partagés (recherche tolérante aux accents)."""
from __future__ import annotations

import unicodedata


def fold(text: str) -> str:
    """Minuscule + suppression des accents.

    Utilisé pour la recherche (« energie » doit trouver « énergie ») et pour
    construire l'index de recherche stocké en base.
    """
    nfkd = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c))
