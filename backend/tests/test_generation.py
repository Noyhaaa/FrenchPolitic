"""Test du pipeline de génération avec le LLM mock (§4.1)."""
from __future__ import annotations

from app.ai.generation import ResumeGenerator
from app.domain.enums import StatutRevue
from app.schemas import ResultatGlobal

RESULTAT = ResultatGlobal(pour=310, contre=231, abstention=24, non_votants=12)


async def test_contexte_vide_part_en_revue():
    """Sans contexte, le mock renvoie une confiance faible ⇒ revue humaine.

    C'est la règle d'or (§2.5) : jamais de comblement, on préfère la revue.
    """
    gen = ResumeGenerator()
    result = await gen.generate(
        scrutin_id="scr-test",
        titre_officiel="Un texte",
        resultat=RESULTAT,
    )
    assert result.statut_revue == StatutRevue.en_attente
    assert len(gen.review_queue) == 1
