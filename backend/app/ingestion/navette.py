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

Le module calcule aussi **où en est le texte aujourd'hui** (`etat_du_texte`) :
la frise, à elle seule, ne dit que le passé et laisse le lecteur sans réponse à
« et maintenant ? ». L'état vient des mêmes actes — promulgation, retrait,
saisine du Conseil constitutionnel, résolution conclue, ou simplement la
dernière étape enregistrée. ⚠️ Il ne décrit **jamais** l'étape suivante :
l'inscription à l'ordre du jour est une décision politique, pas une donnée.
"""
from __future__ import annotations

import re

from app.domain.enums import Chambre, StatutScrutin
from app.ingestion.normalize import as_list
from app.schemas import EtatTexte, PhaseScrutin, Scrutin, SourceOfficielle
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


def _etapes_retenues(actes_legislatifs: object) -> list[dict]:
    """Les actes de premier niveau qui sont des étapes de navette, dans l'ordre
    de l'archive — l'ordre procédural officiel."""
    if isinstance(actes_legislatifs, dict):
        actes = as_list(actes_legislatifs.get("acteLegislatif"))
    else:
        actes = as_list(actes_legislatifs)
    return [
        a
        for a in actes
        if isinstance(a, dict) and (a.get("codeActe") or "") in _CHAMBRE_PAR_ACTE
    ]


def phases_depuis_actes(actes_legislatifs: object) -> list[PhaseScrutin]:
    """Étapes de la navette depuis les `actesLegislatifs` du dossier.

    L'ordre est celui de l'archive — l'ordre procédural officiel. On ne trie pas
    par date : les nœuds d'étape n'en portent pas (elle vit dans leurs
    descendants) et un tri les rejetterait arbitrairement en fin de frise."""
    phases: list[PhaseScrutin] = []
    for acte in _etapes_retenues(actes_legislatifs):
        label = (acte.get("libelleActe") or {}).get("nomCanonique")
        if not label:
            continue
        date, statut = _conclusion(acte)
        phases.append(
            PhaseScrutin(
                label=label,
                chambre=_CHAMBRE_PAR_ACTE[acte["codeActe"]],
                statut=statut,
                date=date,
            )
        )
    return phases


# ---------------------------------------------------------------------------
# Où en est le texte aujourd'hui — la clôture de la frise
# ---------------------------------------------------------------------------

# Codes de `procedureParlementaire` dont l'aboutissement est la **résolution**
# et non la loi : elle est conclue dès sa lecture unique — ni transmise à
# l'autre chambre, ni promulguée. Sans ce cas, une résolution adoptée serait
# annoncée « en cours d'examen », ce qui la ferait passer pour un texte en
# attente alors qu'elle est terminée.
_PROCEDURES_RESOLUTION = frozenset({"8", "22"})


def _descendants(noeud: object) -> list[dict]:
    """Tous les nœuds d'acte sous `noeud`, lui compris."""
    trouves: list[dict] = []

    def descendre(courant: object) -> None:
        if isinstance(courant, list):
            for element in courant:
                descendre(element)
        elif isinstance(courant, dict):
            trouves.append(courant)
            for valeur in courant.values():
                descendre(valeur)

    descendre(noeud)
    return trouves


def _premier(noeuds: list[dict], predicat) -> dict | None:
    return next((n for n in noeuds if predicat(n.get("codeActe") or "")), None)


def etat_du_texte(
    actes_legislatifs: object, procedure: object = None
) -> EtatTexte | None:
    """Où en est le texte aujourd'hui, d'après ses actes officiels.

    Liste fermée d'états, au **premier signal positif rencontré**. Chacun est un
    fait écrit dans l'archive ; aucun ne décrit une étape à venir — le calendrier
    parlementaire est une décision politique, pas une donnée (§2.5).

    `None` quand aucun acte ne documente d'étape (dossiers reconstitués
    « TXT-… », d'origine sénatoriale « SEN-… », motions) : le bloc disparaît."""
    etapes = _etapes_retenues(actes_legislatifs)
    if not etapes:
        return None
    tous = _descendants(actes_legislatifs)

    # 1. Promulguée : l'archive donne le numéro de la loi, sa date, celle du
    #    Journal officiel et l'URL Légifrance — mesuré présents ensemble sur
    #    96/96 des dossiers promulgués, donc rien à combler.
    promulgation = _premier(tous, lambda c: c == "PROM-PUB")
    if promulgation is not None:
        info_jo = promulgation.get("infoJO") or {}
        date_jo = info_jo.get("dateJO")
        return EtatTexte(
            etat="promulgue",
            date=_jour(promulgation.get("dateActe")),
            numero_loi=promulgation.get("codeLoi"),
            date_journal_officiel=date_jo[:10] if isinstance(date_jo, str) else None,
            url_legifrance=info_jo.get("urlLegifrance"),
        )

    derniere = etapes[-1]
    label_dernier = (derniere.get("libelleActe") or {}).get("nomCanonique")
    date_dernier, statut_dernier = _conclusion(derniere)

    # 2. Initiative retirée par son auteur — mais seulement si le retrait est
    #    dans la DERNIÈRE étape : un retrait suivi d'autres actes ne conclut
    #    rien (le dossier a continué sur un autre texte).
    retrait = _premier(_descendants(derniere), lambda c: c.endswith("RTRINI"))
    if retrait is not None:
        return EtatTexte(etat="retire", date=_jour(retrait.get("dateActe")))

    # 3. Devant le Conseil constitutionnel : saisi, sans conclusion publiée. On
    #    dit qu'il est saisi, jamais ce qu'il décidera ni quand.
    saisine = _premier(tous, lambda c: c.startswith("CC-SAISIE"))
    if saisine is not None and _premier(tous, lambda c: c == "CC-CONCLUSION") is None:
        return EtatTexte(
            etat="conseil_constitutionnel", date=_jour(saisine.get("dateActe"))
        )

    code = procedure.get("code") if isinstance(procedure, dict) else None
    # 4. Résolution conclue : son parcours s'arrête là, par nature.
    if code in _PROCEDURES_RESOLUTION and statut_dernier is not None:
        return EtatTexte(
            etat="resolution",
            date=date_dernier,
            etape=label_dernier,
            chambre=_CHAMBRE_PAR_ACTE[derniere["codeActe"]],
            statut=statut_dernier,
        )

    # 5. Sinon : la dernière étape enregistrée, telle quelle. C'est le dernier
    #    point que la source documente — pas une promesse de suite.
    return EtatTexte(
        etat="en_navette",
        date=date_dernier,
        etape=label_dernier,
        chambre=_CHAMBRE_PAR_ACTE[derniere["codeActe"]],
        statut=statut_dernier,
    )


def sources_sans_le_lien_de_la_loi(
    sources: list[SourceOfficielle], etat: EtatTexte | None
) -> list[SourceOfficielle]:
    """Les sources du dossier, **privées du lien vers le texte en vigueur**.

    Ce lien a d'abord été posé parmi les `sources`, avant que la carte « La loi »
    ne l'affiche à côté du texte **voté** — les deux ensemble, parce qu'ils ne
    disent pas la même chose. Il n'a plus rien à faire dans la liste : deux fois
    la même URL sous deux libellés laisserait croire à deux textes.

    ⚠️ On retire **exactement** l'URL que porte l'état, pas « tout ce qui
    ressemble à du Légifrance » : une source légitime pourrait pointer là-bas
    (le seed le fait), et un prédicat approximatif l'emporterait avec.
    `EtatTexte.url_legifrance` reste la seule référence de ce lien.
    """
    url = etat.url_legifrance if etat else None
    if not url:
        return sources
    return [s for s in sources if s.url != url]


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
