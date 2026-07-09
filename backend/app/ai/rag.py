"""Construction du contexte ancré (RAG) fourni au modèle (§4.1).

« Le modèle ne connaît rien : il reformule uniquement un contexte qu'on lui
fournit. » On rassemble ici les documents officiels d'un scrutin, découpés en
passages identifiés par un `source_id` — la SEULE source autorisée pour le résumé.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Passage:
    """Un fragment de document officiel, cité par son identifiant."""

    source_id: str  # ex. "expose_motifs", "texte_article_2"
    contenu: str


@dataclass
class RagContext:
    scrutin_id: str
    passages: list[Passage]

    @property
    def source_ids(self) -> set[str]:
        return {p.source_id for p in self.passages}

    def to_prompt_block(self) -> str:
        """Bloc texte injecté dans le prompt, chaque passage étiqueté."""
        return "\n\n".join(
            f"[{p.source_id}]\n{p.contenu}" for p in self.passages
        )


class RagContextBuilder:
    """Récupère et découpe les documents officiels d'un scrutin.

    Stub : renvoie un contexte vide tant que l'ingestion (Phase 1) et les
    embeddings pgvector ne sont pas branchés. L'interface, elle, est stable.
    """

    async def build(self, scrutin_id: str) -> RagContext:
        # TODO(Phase 1/2) : lire les documents ingérés (exposé des motifs, texte,
        # débats), les découper, récupérer les passages pertinents via pgvector.
        return RagContext(scrutin_id=scrutin_id, passages=[])
