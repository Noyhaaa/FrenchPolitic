"""Orchestration de la génération d'un résumé (§4.1).

Pipeline : RAG (contexte officiel) → LLM (reformulation ancrée, JSON) →
garde-fous → décision publier / revue humaine. La génération est faite UNE fois
par scrutin puis mise en cache (§6 : coût ∝ nombre de scrutins, pas d'utilisateurs).
"""
from __future__ import annotations

from dataclasses import dataclass

from app.ai.guardrails import (
    GuardrailReport,
    doit_passer_en_revue,
    run_guardrails,
)
from app.ai.llm import LLMClient, dumps, get_llm_client
from app.ai.prompts import SYSTEM_RESUME, build_user_prompt
from app.ai.rag import RagContext, RagContextBuilder
from app.ai.review_queue import ReviewItem, ReviewQueue
from app.domain.enums import StatutRevue
from app.schemas import ResultatGlobal, ResumeScrutin


@dataclass
class GenerationResult:
    resume: ResumeScrutin
    statut_revue: StatutRevue
    report: GuardrailReport


class ResumeGenerator:
    def __init__(
        self,
        llm: LLMClient | None = None,
        rag: RagContextBuilder | None = None,
        review_queue: ReviewQueue | None = None,
    ) -> None:
        self._llm = llm or get_llm_client()
        self._rag = rag or RagContextBuilder()
        self._queue = review_queue or ReviewQueue()

    async def generate(
        self,
        scrutin_id: str,
        titre_officiel: str,
        resultat: ResultatGlobal,
    ) -> GenerationResult:
        context = await self._rag.build(scrutin_id)
        raw = await self._llm.generate_json(
            system=SYSTEM_RESUME,
            user=build_user_prompt(titre_officiel, context.to_prompt_block()),
        )
        resume = self._parse(raw)
        return self._apply_guardrails(scrutin_id, resume, resultat, context)

    def _parse(self, raw: dict) -> ResumeScrutin:
        # Le LLM ne renseigne pas relu_par_humain : c'est le pipeline qui décide.
        raw = {**raw, "relu_par_humain": False}
        return ResumeScrutin.model_validate(raw)

    def _apply_guardrails(
        self,
        scrutin_id: str,
        resume: ResumeScrutin,
        resultat: ResultatGlobal,
        context: RagContext,
    ) -> GenerationResult:
        report = run_guardrails(resume, resultat, context.source_ids)
        if doit_passer_en_revue(report, resume.confiance):
            motifs = [v.message for v in report.violations]
            if resume.confiance.value == "faible":
                motifs.append("Confiance faible.")
            self._queue.enqueue(
                ReviewItem(
                    scrutin_id=scrutin_id,
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


# Ré-export pratique pour d'éventuels logs/débogage.
__all__ = ["ResumeGenerator", "GenerationResult", "dumps"]
