"""Trajectoire d'un texte au Parlement — la frise de la fiche dossier (§3.2).

Cette frise était jusqu'ici dérivée côté app des **objets des votes AN**, ce qui
la condamnait à ne montrer qu'une seule chambre : rien dans un scrutin de
l'Assemblée ne dit que le Sénat a examiné le texte entre-temps. Elle est donc
calculée ici, à l'ingestion, depuis la meilleure source disponible.

Deux voies, dans cet ordre :

1. **Les actes législatifs officiels** du dossier (`actesLegislatifs` de
   l'archive « dossiers législatifs » de l'AN). Ils décrivent l'enchaînement
   complet — lectures à l'Assemblée ET au Sénat, commission mixte paritaire,
   Conseil constitutionnel, promulgation — chaque étape portant sa date et,
   quand elle est conclue, son `statutConclusion` officiel. C'est un fait, pas
   une déduction.
2. **Repli** pour les dossiers sans actes (dossiers reconstitués `TXT-…`,
   dossiers d'origine sénatoriale `SEN-…`, motions) : les mentions de navette
   portées par les objets des votes eux-mêmes, tous scrutins confondus. Moins
   complet, mais toujours factuel.

Règle d'or (§2.5) : une étape n'apparaît que si la source la documente, et son
statut n'est posé que si la source le dit. Un libellé de conclusion inconnu
laisse l'étape **sans** statut plutôt que de la ranger au jugé.
"""
from __future__ import annotations

import re

from app.domain.enums import Chambre, StatutScrutin
from app.ingestion.normalize import as_list
from app.schemas import PhaseScrutin, Scrutin
from app.utils.text import fold

# ---------------------------------------------------------------------------
# Voie 1 — les actes législatifs officiels
# ---------------------------------------------------------------------------

# Étapes de la navette retenues, par `codeActe` de premier niveau (liste fermée,
# relevée sur l'archive : 16 codes existent, on écarte ceux qui ne sont pas des
# étapes de navette — « Travaux » (AN20), « Débat » (AN21) et « Mise en
# application de la loi » (AN-APPLI), qui encombreraient la frise sans décrire
# le parcours du texte).
_CHAMBRE_PAR_ACTE: dict[str, Chambre | None] = {
    "AN1": Chambre.assemblee,
    "AN2": Chambre.assemblee,
    "ANLUNI": Chambre.assemblee,
    "ANNLEC": Chambre.assemblee,
    "ANLDEF": Chambre.assemblee,
    "SN1": Chambre.senat,
    "SN2": Chambre.senat,
    "SNNLEC": Chambre.senat,
    # Étapes sans chambre propre : la CMP réunit les deux assemblées, le Conseil
    # constitutionnel et la promulgation sont hors Parlement.
    "CMP": None,
    "CC": None,
    "PROM": None,
}


def _statut_conclusion(libelle: str | None) -> StatutScrutin | None:
    """Statut d'une étape depuis le `statutConclusion` officiel de sa décision.

    Le vocabulaire de l'archive est riche et parfois circonstancié (« adoptée,
    dans les conditions prévues à l'article 45, alinéa 3, de la Constitution »,
    « considérée comme définitive en application de l'article 151-7 du
    Règlement », « rejet du texte par la commission préalable »). On ne retient
    que ce qui est sans ambiguïté ; tout le reste — dont les avis du Conseil
    constitutionnel (« Conforme », « Partiellement conforme »), qui ne sont ni
    une adoption ni un rejet — laisse l'étape sans statut (§2.5)."""
    if not libelle:
        return None
    t = fold(libelle)
    # « rejet » d'abord : « considéré comme rejeté », « rejet du texte par la
    # commission préalable »… sinon « adopté » l'emporterait dans les formules
    # qui contiennent les deux (« rejeté … adopté par l'Assemblée »).
    if "rejet" in t or t.startswith("desaccord"):
        return StatutScrutin.rejete
    if t.startswith("adopt") or t.startswith("accord"):
        return StatutScrutin.adopte
    # « modifié / modifiée » : la chambre a bien adopté le texte, en le
    # modifiant — c'est la navette qui continue, pas un rejet.
    if t.startswith("modifi"):
        return StatutScrutin.adopte
    if t.startswith("consideree comme definitive") or "comme adopte" in t:
        return StatutScrutin.adopte
    return None


def _jour(date_acte: object) -> str | None:
    """Jour ISO (« 2026-06-02 ») d'un `dateActe` horodaté, sinon None."""
    if not isinstance(date_acte, str) or len(date_acte) < 10:
        return None
    return date_acte[:10]


def _conclusion(acte: dict) -> tuple[str | None, StatutScrutin | None]:
    """Date et statut d'une étape, cherchés dans ses actes descendants.

    On privilégie le nœud de **décision** (`statutConclusion` : c'est lui qui
    conclut l'étape) ; à défaut, la date la plus ancienne rencontrée sous
    l'étape, qui situe au moins son début."""
    date_decision: str | None = None
    statut: StatutScrutin | None = None
    dates: list[str] = []

    def descendre(noeud: object) -> None:
        nonlocal date_decision, statut
        if isinstance(noeud, list):
            for element in noeud:
                descendre(element)
            return
        if not isinstance(noeud, dict):
            return
        jour = _jour(noeud.get("dateActe"))
        if jour:
            dates.append(jour)
        conclusion = noeud.get("statutConclusion")
        if isinstance(conclusion, dict):
            trouve = _statut_conclusion(conclusion.get("libelle"))
            # La dernière décision de l'étape fait foi (une étape peut en porter
            # plusieurs : motion rejetée puis vote sur l'ensemble).
            if trouve is not None:
                statut = trouve
                date_decision = jour or date_decision
        for valeur in noeud.values():
            descendre(valeur)

    for valeur in acte.values():
        descendre(valeur)
    return date_decision or (min(dates) if dates else None), statut


def phases_depuis_actes(actes_legislatifs: object) -> list[PhaseScrutin]:
    """Étapes de la navette depuis les `actesLegislatifs` du dossier.

    L'ordre est celui de l'archive — l'ordre procédural officiel. On ne trie pas
    par date : les nœuds d'étape n'en portent pas (elle vit dans leurs
    descendants) et un tri les rejetterait arbitrairement en fin de frise."""
    if isinstance(actes_legislatifs, dict):
        actes = as_list(actes_legislatifs.get("acteLegislatif"))
    else:
        actes = as_list(actes_legislatifs)

    phases: list[PhaseScrutin] = []
    for acte in actes:
        if not isinstance(acte, dict):
            continue
        code = acte.get("codeActe") or ""
        if code not in _CHAMBRE_PAR_ACTE:
            continue
        label = (acte.get("libelleActe") or {}).get("nomCanonique")
        if not label:
            continue
        date, statut = _conclusion(acte)
        phases.append(
            PhaseScrutin(
                label=label,
                chambre=_CHAMBRE_PAR_ACTE[code],
                statut=statut,
                date=date,
            )
        )
    return phases


# ---------------------------------------------------------------------------
# Voie 2 — repli sur les mentions portées par les objets des votes
# ---------------------------------------------------------------------------

# Phases reconnues dans les objets officiels des votes. Reprise à l'identique de
# ce que faisait `phasesNavette` côté app (les « parties » du budget ne sont pas
# des phases de navette — exclues).
_PHASES_OBJET: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"premiere lecture"), "Première lecture"),
    (re.compile(r"deuxieme lecture"), "Deuxième lecture"),
    (re.compile(r"troisieme lecture"), "Troisième lecture"),
    (re.compile(r"commission mixte paritaire"), "Commission mixte paritaire"),
    (re.compile(r"nouvelle lecture"), "Nouvelle lecture"),
    (re.compile(r"lecture definitive"), "Lecture définitive"),
)


def phases_depuis_votes(votes: list[Scrutin]) -> list[PhaseScrutin]:
    """Étapes déduites des mentions de navette portées par les objets de vote.

    Une phase n'apparaît que si un vote la mentionne, et son statut ne vient que
    du **vote sur l'ensemble** de cette phase. Chaque phase est distinguée par
    sa chambre : « Première lecture » à l'Assemblée et au Sénat sont deux
    étapes, pas une."""
    ordonnes = sorted(votes, key=lambda s: s.date)
    par_cle: dict[tuple[str, Chambre], tuple[int, PhaseScrutin]] = {}
    for ordre, vote in enumerate(ordonnes):
        objet = fold(vote.objet)
        for motif, label in _PHASES_OBJET:
            if not motif.search(objet):
                continue
            cle = (label, vote.chambre)
            est_ensemble = "ensemble" in objet
            connu = par_cle.get(cle)
            if connu is None:
                par_cle[cle] = (
                    ordre,
                    PhaseScrutin(
                        label=label,
                        chambre=vote.chambre,
                        statut=vote.statut if est_ensemble else None,
                        date=vote.date[:10],
                    ),
                )
            else:
                phase = connu[1]
                phase.date = vote.date[:10]
                if est_ensemble:
                    phase.statut = vote.statut
    return [phase for _, phase in sorted(par_cle.values(), key=lambda p: p[0])]


def trajectoire(
    actes_legislatifs: object, votes: list[Scrutin]
) -> list[PhaseScrutin]:
    """Trajectoire du texte : les actes officiels, sinon les objets des votes.

    Vide quand aucune des deux sources ne documente d'étape — la frise est alors
    masquée côté app plutôt que remplie d'à-peu-près (§2.5)."""
    phases = phases_depuis_actes(actes_legislatifs)
    if phases:
        return phases
    return phases_depuis_votes(votes)
