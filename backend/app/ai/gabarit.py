"""Générateur de résumé par gabarit déterministe (Phase 2, sans LLM).

Compose un résumé neutre **uniquement** à partir des faits officiels du dossier
(§2.5). Chaque phrase porte le `source_id` du passage qui l'étaie, si bien que
le résultat passe les garde-fous par construction : ancrage (source_id connu),
lexique (vocabulaire figé, neutre) et chiffres (seuls les décomptes officiels
du vote décisif sont cités, jamais un comptage de scrutins/amendements accolé à
un mot de vote). Zéro clé API, zéro hallucination.

Un LLM (AnthropicLLM) pourra fluidifier ce style plus tard derrière la même
interface, sans changer ce contrat.
"""
from __future__ import annotations

from app.ai.faits import FaitsDossier, date_fr
from app.ai.rag import RagContext
from app.schemas import PhraseSourcee, ResumeScrutin

_STATUT_FR = {"adopte": "adopté", "rejete": "rejeté"}


def _et(noms: list[str]) -> str:
    """« A, B et C » — énumération française lisible."""
    if len(noms) <= 1:
        return noms[0] if noms else ""
    return f"{', '.join(noms[:-1])} et {noms[-1]}"


# Au-delà, on n'énumère pas tous les groupes (phrase illisible) : on cite les
# premiers puis « d'autres groupes » — sans chiffre (le garde-fou des décomptes
# n'accepte de nombre que s'il correspond au résultat officiel).
_MAX_GROUPES = 3


def _liste_groupes(noms: list[str]) -> str:
    if len(noms) <= _MAX_GROUPES:
        return _et(noms)
    return ", ".join(noms[:_MAX_GROUPES]) + " et d'autres groupes"


def _s(n: int) -> str:
    """Marque du pluriel (« s » si n > 1)."""
    return "s" if n > 1 else ""


def composer_resume(faits: FaitsDossier, context: RagContext) -> ResumeScrutin:
    """Compose le résumé (jusqu'à 5 phrases) à partir des faits et du contexte.

    Une phrase n'est émise que si son passage existe dans le contexte : les
    `source_id` sont donc toujours valides (ancrage garanti)."""
    phrases: list[PhraseSourcee] = []

    # 1. Nature + thème du texte. On ne recopie PAS le titre officiel (déjà
    #    affiché en tête de fiche, et il peut contenir un terme que le garde-fou
    #    du lexique jugerait orienté) : la nature en tête suffit et évite aussi
    #    le souci d'accord (« un projet » / « une proposition »).
    intitule = faits.nature or "Texte"
    p1 = f"{intitule} relevant du thème « {faits.theme} »."
    phrases.append(PhraseSourcee(phrase=p1, source_id="nature_theme"))

    # 2. Trajectoire (nombre de scrutins sur le texte, période).
    if context.a("trajectoire") and faits.date_premier and faits.date_dernier:
        if faits.date_premier == faits.date_dernier:
            quand = f"le {date_fr(faits.date_dernier)}"
        else:
            quand = f"du {date_fr(faits.date_premier)} au {date_fr(faits.date_dernier)}"
        if faits.nb_votes_texte == 1:
            p2 = f"Il a fait l'objet d'un scrutin sur le texte, {quand}."
        else:
            p2 = f"Il a fait l'objet de {faits.nb_votes_texte} scrutins sur le texte, {quand}."
        phrases.append(PhraseSourcee(phrase=p2, source_id="trajectoire"))

    # 3. Vote décisif : résultat chiffré officiel.
    d = faits.decisif
    if context.a("vote_ensemble") and d is not None:
        sujet = (
            "Le vote sur l'ensemble du texte"
            if "ensemble" in d.objet.lower()
            else "Le dernier scrutin sur le texte"
        )
        statut = _STATUT_FR.get(d.statut.value)
        if statut:
            r = d.resultat
            p3 = f"{sujet} a été {statut} par {r.pour} voix contre {r.contre}"
            if r.abstention:
                p3 += f", avec {r.abstention} abstention{_s(r.abstention)}"
            p3 += "."
            phrases.append(PhraseSourcee(phrase=p3, source_id="vote_ensemble"))

    # 4. Positions des groupes sur le vote décisif (noms seulement, pas de
    #    chiffre — factuel et sûr pour le garde-fou des décomptes).
    if context.a("positions_groupes"):
        pour, contre = faits.groupes_pour, faits.groupes_contre
        morceaux: list[str] = []
        if pour:
            morceaux.append(f"{_liste_groupes(pour)} ont majoritairement voté pour")
        if contre:
            morceaux.append(f"{_liste_groupes(contre)} contre")
        if morceaux:
            p4 = "Les groupes " + " ; ".join(morceaux) + "."
            phrases.append(PhraseSourcee(phrase=p4, source_id="positions_groupes"))

    # 5. Amendements mis aux voix (comptes, sans mot de vote accolé).
    if context.a("amendements"):
        na, nr = faits.nb_amendements_adoptes, faits.nb_amendements_rejetes
        p5 = (
            f"Le texte a reçu {faits.nb_amendements} amendement{_s(faits.nb_amendements)}, "
            f"dont {na} adopté{_s(na)} et {nr} rejeté{_s(nr)}."
        )
        phrases.append(PhraseSourcee(phrase=p5, source_id="amendements"))

    # Champs non documentés à partir des seuls scrutins (§2.5) : le contexte
    # éditorial (exposé des motifs, public concerné…) viendra avec Légifrance.
    non_documentes = ["contexte", "objectif", "historique", "public_concerne"]

    return ResumeScrutin(
        titre_clair=faits.titre_clair,
        resume=phrases,
        public_concerne=[],
        confiance="moyenne",
        relu_par_humain=False,
        champs_non_documentes=non_documentes,
    )
