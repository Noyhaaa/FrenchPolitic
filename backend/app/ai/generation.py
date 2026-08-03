"""Orchestration de la génération d'un résumé de dossier (§4.1).

Un seul chemin : le **gabarit déterministe** (`generer_resume`), sans LLM ni clé
API. Il compose le résumé depuis les faits officiels (RAG) puis le soumet aux
garde-fous (§4.4), qu'il passe par construction ; s'il venait à échouer (bug), on
ne publie rien de douteux — le résumé est laissé vide (§2.5).

⚠️ Le résumé neutre n'est **pas** généré par un modèle, et l'échafaudage qui le
permettait a été retiré : un LLM distord des faits de façon invisible aux
garde-fous lexicaux. Seul ce qui est attribuable à une source unique ET
vérifiable déterministiquement passe par un modèle (thème, publics, questions
citoyennes — cf. `app.ai.questions`).

La génération est faite UNE fois par dossier puis persistée (coût ∝ nombre de
dossiers, pas d'utilisateurs — §6).
"""
from __future__ import annotations

from app.ai.faits import FaitsDossier
from app.ai.gabarit import composer_resume
from app.ai.guardrails import run_guardrails
from app.ai.rag import contexte_depuis_faits
from app.schemas import ResumeScrutin


def _resume_vide(titre_clair: str) -> ResumeScrutin:
    """Résumé non comblé (§2.5) : garde-fou en échec ou aucun fait exploitable."""
    return ResumeScrutin(
        titre_clair=titre_clair,
        resume=[],
        public_concerne=[],
        confiance="faible",
        relu_par_humain=False,
        champs_non_documentes=["resume", "contexte", "objectif", "public_concerne"],
    )


def generer_resume(faits: FaitsDossier) -> ResumeScrutin:
    """Résumé déterministe par gabarit, validé par les garde-fous (§4.4).

    Le gabarit ne devrait jamais violer un garde-fou ; si c'est le cas, on
    préfère un résumé vide à un résumé douteux (jamais de comblement, §2.5)."""
    context = contexte_depuis_faits(faits)
    resume = composer_resume(faits, context)
    report = run_guardrails(
        resume,
        faits.resultat_reference,
        context.source_ids,
        faits.suffrages_requis,
    )
    if report.bloquant:
        return _resume_vide(faits.titre_clair)
    return resume


__all__ = ["generer_resume"]
