"""Tests du classement « Qui est concerné ? » (liste fermée, §3.2)."""
from __future__ import annotations

from app.ai.publics import PUBLICS, classifier_publics, valider_publics


class _FakeLLM:
    """LLM factice : rejoue une réponse fixée (aucun réseau)."""

    def __init__(self, reponse: str) -> None:
        self._reponse = reponse

    async def generate_text(self, system: str, user: str) -> str:
        return self._reponse



def test_valider_publics_exact_match():
    assert valider_publics("Locataires, Propriétaires") == [
        "Locataires",
        "Propriétaires",
    ]


def test_valider_publics_tolere_casse_et_accents():
    # Même tolérance que `valider_theme` : la comparaison passe par `fold`.
    assert valider_publics("etudiants, PATIENTS") == ["Étudiants", "Patients"]


def test_valider_publics_ignore_les_entrees_hors_liste():
    # « Jeunes » et « Écoliers » ne sont pas dans la liste fermée : on ne devine
    # pas un public voisin, on les laisse tomber (§2.5).
    assert valider_publics("Jeunes, Écoliers, Familles") == ["Familles"]
    assert valider_publics("aucun") == []
    assert valider_publics("Agriculteurs (car le texte vise les exploitations)") == []


def test_valider_publics_dedoublonne_et_ordonne():
    # Ordre de sortie = ordre de la liste fermée, pas celui du modèle.
    assert valider_publics("Communes, Salariés, communes") == [
        "Salariés",
        "Communes",
    ]


def test_valider_publics_cap_a_trois():
    reponse = ", ".join(PUBLICS)
    retenus = valider_publics(reponse)
    assert len(retenus) == 3
    assert retenus == list(PUBLICS[:3])


async def test_classifier_publics_valide_la_sortie():
    llm = _FakeLLM("Agriculteurs, Entreprises")
    publics = await classifier_publics(
        "Proposition de loi sur les exploitations agricoles",
        llm,
        expose="Le texte vise les exploitants agricoles.",
    )
    assert publics == ["Agriculteurs", "Entreprises"]


async def test_classifier_publics_sortie_invalide_rend_liste_vide():
    # Rien de valide → section « Qui est concerné ? » masquée (§2.5).
    llm = _FakeLLM("Tout le monde est concerné par ce texte important.")
    assert await classifier_publics("Un titre", llm, expose="Un exposé.") == []
