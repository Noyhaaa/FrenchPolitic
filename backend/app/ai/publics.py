"""Publics concernés par un texte, choisis dans une **liste fermée** (§3.2).

Même doctrine que la classification de thème (`app.ai.theme`) : le modèle ne
produit aucune prose affichée, il **range** le texte sous des étiquettes
prédéfinies, et toute sortie hors-liste est rejetée. Le risque éditorial (§4.3)
ne porte donc pas sur la formulation — il ne reste que le risque de mauvais
rangement, borné par la liste et par le cap de 3 étiquettes.

Rien de valide → liste vide → la section « Qui est concerné ? » reste masquée
(§2.5 : on n'affiche pas un public deviné).
"""
from __future__ import annotations

from collections.abc import Sequence

from app.ai.llm import LLMClient
from app.utils.text import fold

# Liste fermée des publics. ⚠️ Contrat : tout ajout ici doit l'être aussi dans
# `publicEmoji` (src/screens/DossierDetailScreen.tsx), sinon la pastille tombe
# sur l'emoji générique. Ordre = ordre d'affichage des chips.
PUBLICS: tuple[str, ...] = (
    "Salariés",
    "Employeurs",
    "Locataires",
    "Propriétaires",
    "Agriculteurs",
    "Étudiants",
    "Familles",
    "Enfants",
    "Patients",
    "Soignants",
    "Personnes handicapées",
    "Consommateurs",
    "Retraités",
    "Automobilistes",
    "Fonctionnaires",
    "Élus locaux",
    "Entreprises",
    "Communes",
    "Associations",
)

# Au-delà, l'étiquetage ne trie plus rien (« ce texte concerne tout le monde »).
_MAX_PUBLICS = 3

# Cap des extraits injectés : le public concerné se lit dans l'amorce du texte.
_MAX_EXTRAIT = 1500


def _system_prompt(publics: Sequence[str]) -> str:
    return (
        "Tu indiques QUI est concerné par un texte de loi français, en "
        "choisissant STRICTEMENT dans cette liste : " + ", ".join(publics) + ".\n"
        f"Réponds par 1 à {_MAX_PUBLICS} entrées de la liste, séparées par des "
        "virgules, recopiées EXACTEMENT telles qu'écrites, sans explication.\n"
        "Ne choisis que les publics que le texte vise DIRECTEMENT, jamais ceux "
        "qui pourraient l'être indirectement ou par ricochet, et n'en ajoute "
        "aucun par précaution.\n"
        "Réponds « aucun » uniquement si le texte ne vise personne en "
        "particulier — texte institutionnel, procédural ou symbolique."
    )


def _user_prompt(titre: str, expose: str | None, dispositif: str | None) -> str:
    lignes = [f"Titre : {titre}"]
    if dispositif:
        lignes.append(f"Dispositif (extrait) : {dispositif[:_MAX_EXTRAIT]}")
    if expose:
        lignes.append(f"Exposé des motifs (extrait) : {expose[:_MAX_EXTRAIT]}")
    return "\n".join(lignes)


def valider_publics(
    reponse: str, publics: Sequence[str] = PUBLICS
) -> list[str]:
    """Les publics valides d'une réponse LLM, dans l'ordre de la liste fermée.

    Découpe sur les virgules et ne retient que les entrées correspondant
    **exactement** à la liste (à la casse et aux accents près, comme
    `valider_theme`). Entrée hors-liste, réponse verbeuse ou « aucun » →
    ignorées ; doublons écartés ; au plus `_MAX_PUBLICS` étiquettes.
    """
    proposes = {
        fold(p.strip().strip(".").strip())
        for p in reponse.replace("\n", ",").split(",")
        if p.strip()
    }
    retenus = [p for p in publics if fold(p) in proposes]
    return retenus[:_MAX_PUBLICS]


async def classifier_publics(
    titre: str,
    llm: LLMClient,
    *,
    expose: str | None = None,
    dispositif: str | None = None,
    publics: Sequence[str] = PUBLICS,
) -> list[str]:
    """Publics proposés par le LLM, validés exact-match ; liste vide si rien de
    valide (la section reste alors masquée).

    Le dispositif est donné en premier quand il existe : c'est le texte
    officiel, il dit qui est visé plus sûrement que l'argumentaire de l'auteur.
    """
    reponse = await llm.generate_text(
        _system_prompt(publics), _user_prompt(titre, expose, dispositif)
    )
    return valider_publics(reponse, publics)
