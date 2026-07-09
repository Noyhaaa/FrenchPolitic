"""File de revue humaine des résumés (§4.6).

Au lancement, aucun résumé sensible n'est publié sans validation humaine. Cette
file (in-memory pour l'instant, table dédiée en Phase 1) collecte les résumés à
relire, avec le motif (garde-fou déclenché ou confiance faible).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.ai.guardrails import GuardrailReport
from app.schemas import ResumeScrutin


@dataclass
class ReviewItem:
    scrutin_id: str
    resume: ResumeScrutin
    motifs: list[str]
    report: GuardrailReport


@dataclass
class ReviewQueue:
    _items: list[ReviewItem] = field(default_factory=list)

    def enqueue(self, item: ReviewItem) -> None:
        self._items.append(item)

    def pending(self) -> list[ReviewItem]:
        return list(self._items)

    def __len__(self) -> int:
        return len(self._items)
