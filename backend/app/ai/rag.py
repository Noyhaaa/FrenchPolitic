"""Construction du contexte ancré (RAG) fourni au générateur de résumé (§4.1).

« Le modèle ne connaît rien : il reformule uniquement un contexte qu'on lui
fournit. » On rassemble ici les **faits officiels** d'un dossier, découpés en
passages identifiés par un `source_id` — la SEULE source autorisée pour le
résumé. Ces passages servent au gabarit déterministe (Phase 2) comme, demain,
à un LLM (le `to_prompt_block` alimente alors le prompt).
"""
from __future__ import annotations

from dataclasses import dataclass

from app.ai.faits import FaitsDossier, date_fr


@dataclass
class Passage:
    """Un fragment de fait officiel, cité par son identifiant."""

    source_id: str  # ex. "vote_ensemble", "positions_groupes"
    contenu: str


@dataclass
class RagContext:
    passages: list[Passage]

    @property
    def source_ids(self) -> set[str]:
        return {p.source_id for p in self.passages}

    def a(self, source_id: str) -> bool:
        return any(p.source_id == source_id for p in self.passages)

    def to_prompt_block(self) -> str:
        """Bloc texte injecté dans le prompt (chaque passage étiqueté)."""
        return "\n\n".join(f"[{p.source_id}]\n{p.contenu}" for p in self.passages)


_STATUT_FR = {"adopte": "adopté", "rejete": "rejeté", "en_cours": "en cours d'examen"}


def contexte_depuis_faits(faits: FaitsDossier) -> RagContext:
    """Passages officiels d'un dossier. Un passage n'est émis que si le fait
    existe (donnée manquante → pas de passage → pas de phrase, §2.5). Les
    `source_id` émis forment l'ensemble autorisé pour le garde-fou d'ancrage."""
    passages: list[Passage] = []

    intitule = faits.nature or "Texte"
    passages.append(
        Passage(
            "nature_theme",
            f"{intitule} rattaché au thème « {faits.theme} ». "
            f"Intitulé : {faits.titre_officiel}.",
        )
    )

    if faits.nb_votes_texte and faits.date_premier and faits.date_dernier:
        if faits.date_premier == faits.date_dernier:
            quand = f"le {date_fr(faits.date_dernier)}"
        else:
            quand = f"du {date_fr(faits.date_premier)} au {date_fr(faits.date_dernier)}"
        passages.append(
            Passage(
                "trajectoire",
                f"{faits.nb_votes_texte} scrutins sur le texte, {quand}.",
            )
        )

    d = faits.decisif
    if d is not None:
        r = d.resultat
        detail = f"{r.pour} pour, {r.contre} contre, {r.abstention} abstentions"
        passages.append(
            Passage(
                "vote_ensemble",
                f"Vote décisif « {d.objet} » : {_STATUT_FR.get(d.statut.value, d.statut.value)} "
                f"({detail}).",
            )
        )
        if faits.groupes_pour or faits.groupes_contre:
            passages.append(
                Passage(
                    "positions_groupes",
                    "Positions majoritaires — pour : "
                    f"{', '.join(faits.groupes_pour) or 'aucun'} ; "
                    f"contre : {', '.join(faits.groupes_contre) or 'aucun'}.",
                )
            )

    if faits.nb_amendements:
        passages.append(
            Passage(
                "amendements",
                f"{faits.nb_amendements} amendements mis aux voix : "
                f"{faits.nb_amendements_adoptes} adoptés, "
                f"{faits.nb_amendements_rejetes} rejetés.",
            )
        )

    return RagContext(passages=passages)
