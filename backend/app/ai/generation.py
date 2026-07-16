"""Orchestration de la génération d'un résumé de dossier (§4.1).

Deux chemins, un même contrat (RAG des faits → résumé → garde-fous) :

- **gabarit** (`generer_resume`) : déterministe, sans LLM ni clé API — le défaut
  de Phase 2. Il passe les garde-fous par construction ; s'il venait à échouer
  (bug), on ne publie rien de douteux (§4.4) — le résumé est laissé vide (§2.5).
- **LLM** (`ResumeGenerator`) : reformulation par un modèle (MockLLM aujourd'hui,
  AnthropicLLM demain), soumise aux mêmes garde-fous et à la file de revue.

La génération est faite UNE fois par dossier puis persistée (coût ∝ nombre de
dossiers, pas d'utilisateurs — §6).
"""
from __future__ import annotations

from dataclasses import dataclass

from app.ai.faits import FaitsDossier
from app.ai.gabarit import composer_resume
from app.ai.guardrails import GuardrailReport, doit_passer_en_revue, run_guardrails
from app.ai.llm import LLMClient, dumps, get_llm_client
from app.ai.prompts import SYSTEM_RESUME, build_user_prompt
from app.ai.rag import RagContext, contexte_depuis_faits
from app.ai.review_queue import ReviewItem, ReviewQueue
from app.domain.enums import StatutRevue
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
    report = run_guardrails(resume, faits.resultat_reference, context.source_ids)
    if report.bloquant:
        return _resume_vide(faits.titre_clair)
    return resume


@dataclass
class GenerationResult:
    resume: ResumeScrutin
    statut_revue: StatutRevue
    report: GuardrailReport


class ResumeGenerator:
    """Chemin LLM (Phase 2+) : reformulation d'un modèle, garde-fous et revue.

    Non branché à l'ingestion pour l'instant (le gabarit fait foi) ; l'interface
    est dossier-niveau pour accueillir AnthropicLLM sans refonte.
    """

    def __init__(
        self,
        llm: LLMClient | None = None,
        review_queue: ReviewQueue | None = None,
    ) -> None:
        self._llm = llm or get_llm_client()
        self._queue = review_queue or ReviewQueue()

    async def generate(self, faits: FaitsDossier) -> GenerationResult:
        context = contexte_depuis_faits(faits)
        raw = await self._llm.generate_json(
            system=SYSTEM_RESUME,
            user=build_user_prompt(faits.titre_officiel, context.to_prompt_block()),
        )
        resume = self._parse(raw, faits.titre_clair)
        return self._apply_guardrails(faits, resume, context)

    def _parse(self, raw: dict, titre_clair: str) -> ResumeScrutin:
        # Le LLM ne renseigne ni relu_par_humain (décidé par le pipeline) ni un
        # titre fiable : on impose le titre clair du dossier.
        raw = {**raw, "relu_par_humain": False, "titre_clair": titre_clair}
        return ResumeScrutin.model_validate(raw)

    def _apply_guardrails(
        self,
        faits: FaitsDossier,
        resume: ResumeScrutin,
        context: RagContext,
    ) -> GenerationResult:
        report = run_guardrails(resume, faits.resultat_reference, context.source_ids)
        if doit_passer_en_revue(report, resume.confiance):
            motifs = [v.message for v in report.violations]
            if resume.confiance.value == "faible":
                motifs.append("Confiance faible.")
            self._queue.enqueue(
                ReviewItem(
                    scrutin_id=faits.titre_officiel,
                    resume=resume,
                    motifs=motifs,
                    report=report,
                )
            )
            return GenerationResult(resume, StatutRevue.en_attente, report)
        return GenerationResult(resume, StatutRevue.publie, report)

    @property
    def review_queue(self) -> ReviewQueue:
        return self._queue


__all__ = ["generer_resume", "ResumeGenerator", "GenerationResult", "dumps"]
