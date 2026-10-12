"""Décisions de séance prises SANS scrutin public (§5.2).

Jusqu'ici, un dossier n'existait dans l'app que si un **scrutin public** le
créait. Or l'essentiel de ce que le Parlement décide ne passe pas par là : un
texte s'adopte d'ordinaire à main levée, une convention internationale en
procédure simplifiée, une résolution européenne sans même venir en séance.
Mesuré en 17e législature : 103 textes absents de l'app (dont des conventions
promulguées) et 219 décisions de séance sans trace, dans les deux chambres.

La source est la même archive que la frise : les **actes de décision** des
dossiers législatifs (`…-DEBATS-DEC`), qui portent la chambre, la date, l'étape
et la conclusion officielle (`statutConclusion`). C'est un fait écrit par
l'Assemblée, pas une déduction.

Ce module ne fait que des fonctions pures :

- `extraire_decisions` lit ces actes ;
- `rattacher_par_decisions` range sous leur dossier officiel les votes publics
  qu'une correspondance de titre avait laissés dans un dossier reconstitué
  (`TXT-…`, `SEN-…`), quand une décision du même jour, dans la même chambre,
  sur un titre concordant, les désigne sans ambiguïté ;
- `decisions_sans_scrutin` écarte les décisions qu'un scrutin public raconte
  déjà (le vote est alors en base, avec ses chiffres) ;
- `parse_decision` en fait un `ScrutinParse` sans décompte, que le reste du
  pipeline traite comme n'importe quel vote.

Règle d'or (§2.5) : une conclusion non reconnue ne produit **aucune** décision,
et un appariement ambigu n'en déplace aucune.
"""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import date

from app.domain.enums import Chambre, ModaliteVote, StatutScrutin
from app.ingestion.assemblee import ScrutinParse, dossier_source
from app.ingestion.dossiers_legislatifs import (
    _DENOMINATIONS_TEXTE,
    _refs_de_votes,
    legislature_du_ref,
    slug_dossier_senat,
)
from app.ingestion.normalize import est_amendement, guess_theme
from app.schemas import ResultatGlobal, Scrutin, SourceOfficielle
from app.utils.text import fold

# Une décision de SÉANCE : « AN1-DEBATS-DEC », « SN2-DEBATS-DEC »,
# « CMP-DEBATS-AN-DEC » (lecture des conclusions de la CMP dans une chambre).
# Les décisions de commission (« …-COM-…-DEC ») et celle de la CMP elle-même
# (« CMP-DEC » : accord ou désaccord des quatorze membres) ne sont pas des votes
# d'une assemblée — et « CMP-DEBATS-DEC », sans chambre, ne se situe pas.
_RE_DECISION_SEANCE = re.compile(r"^(?:AN|SN)\w*-DEBATS-DEC$|^CMP-DEBATS-(?:AN|SN)-DEC$")

# Une décision et un scrutin public du même texte, dans la même chambre, se
# couvrent s'ils tombent le même jour ; à défaut, à deux jours près (séance
# levée après minuit, date d'acte arrondie) — sauf si une AUTRE décision du
# dossier tombe ce jour-là, auquel cas le scrutin est le sien.
_FENETRE_JOURS = 2

# Concordance de titre (cf. `titres_concordants`) : part des mots du titre
# cité par le vote qu'on doit retrouver dans les titres du dossier officiel.
# Mesuré sur les cas réels : ≥ 0,87 pour un même texte (une coquille de date
# ou un titre tronqué ne coûte qu'un mot), ≤ 0,3 pour deux textes votés le
# même jour.
_SEUIL_CONCORDANCE = 0.8
_MOTS_MIN = 4
# Mots qui ne distinguent aucun texte d'un autre : la nature, la tournure.
_MOTS_VIDES = frozenset(
    {
        "projet", "proposition", "resolution", "europeenne", "visant", "tendant",
        "portant", "relative", "relatif", "relatives", "relatifs", "application",
        "article", "constitution", "dans", "pour", "avec", "sans", "entre",
        "leur", "leurs", "cette", "plus", "autres", "sous", "loi", "organique",
    }
)


@dataclass(frozen=True)
class VotePublic:
    """Un scrutin public déjà connu (de ce run ou de la base) : ce qu'il faut
    pour dire qu'une décision ou un amendement a eu son scrutin."""

    dossier_id: str
    chambre: Chambre
    date: str
    objet: str


@dataclass(frozen=True)
class DecisionSeance:
    """Un acte de décision de séance, tel que l'archive le publie."""

    uid: str                # uid de l'acte : devient l'id du « vote »
    dossier_ref: str
    chambre: Chambre
    jour: str               # ISO « AAAA-MM-JJ »
    etape: str              # « 1ère lecture (2ème assemblée saisie) »…
    conclusion: str         # statutConclusion, verbatim
    statut: StatutScrutin
    modalite: ModaliteVote
    # Scrutins publics que l'acte cite lui-même (`voteRefs`).
    votes_cites: tuple[str, ...] = ()


def lire_conclusion(
    libelle: object,
) -> tuple[StatutScrutin, ModaliteVote] | None:
    """Sort et modalité d'une décision, d'après sa conclusion officielle.

    Liste fermée (§2.5) — tout le reste ne produit rien : « rejet du texte par
    la commission préalable », une conclusion vide, un libellé inconnu.
    « adoptée, dans les conditions prévues à l'article 45, alinéa 3 » est une
    adoption ordinaire (texte de CMP) ; « modifié » aussi (la chambre a adopté
    le texte en le modifiant).
    """
    if not isinstance(libelle, str) or not libelle.strip():
        return None
    t = fold(libelle).strip()
    if t.startswith("consideree comme definitive") and "151-7" in t:
        return StatutScrutin.adopte, ModaliteVote.article_151_7
    if "article 49" in t and "alinea 3" in t:
        if "comme adopte" in t:
            return StatutScrutin.adopte, ModaliteVote.article_49_3
        if "comme rejete" in t:
            return StatutScrutin.rejete, ModaliteVote.article_49_3
        return None
    if t.startswith(("adopte", "modifie")):
        return StatutScrutin.adopte, ModaliteVote.main_levee
    if t.startswith("rejete"):
        return StatutScrutin.rejete, ModaliteVote.main_levee
    return None


def _chambre(code: str) -> Chambre | None:
    if code.startswith("SN") or "-SN-" in code:
        return Chambre.senat
    if code.startswith("AN") or "-AN-" in code:
        return Chambre.assemblee
    return None


def _noeuds(acte: object) -> list[dict]:
    """Tous les actes sous `acte` (lui compris), dans l'ordre de l'archive."""
    trouves: list[dict] = []

    def descendre(noeud: object) -> None:
        if isinstance(noeud, list):
            for element in noeud:
                descendre(element)
        elif isinstance(noeud, dict):
            trouves.append(noeud)
            sous = (noeud.get("actesLegislatifs") or {}).get("acteLegislatif")
            if sous:
                descendre(sous)

    descendre(acte)
    return trouves


def extraire_decisions(
    dossiers: list[dict], legislatures: tuple[int, ...], depuis: str
) -> list[DecisionSeance]:
    """Les décisions de séance des dossiers, à partir de `depuis` (ISO).

    Restreint aux dossiers des législatures données, comme les `voteRefs`. La
    **première copie vue** d'un dossier gagne : l'archive courante passe avant
    la précédente, dont la copie est un instantané figé (cf. `sync`).
    `depuis` écarte les décisions d'une législature antérieure : elles portent
    sur des votes que l'app ne couvre pas.
    """
    prefixes = tuple(f"DLR5L{leg}N" for leg in legislatures)
    vus: set[str] = set()
    decisions: list[DecisionSeance] = []
    for brut in dossiers:
        dp = brut.get("dossierParlementaire") or brut
        ref = dp.get("uid") or ""
        if not ref.startswith(prefixes) or ref in vus:
            continue
        vus.add(ref)
        etapes = (dp.get("actesLegislatifs") or {}).get("acteLegislatif")
        for etape in etapes if isinstance(etapes, list) else [etapes]:
            if not isinstance(etape, dict):
                continue
            label = (etape.get("libelleActe") or {}).get("nomCanonique") or ""
            for noeud in _noeuds(etape):
                code = noeud.get("codeActe") or ""
                if not _RE_DECISION_SEANCE.match(code):
                    continue
                chambre = _chambre(code)
                jour = str(noeud.get("dateActe") or "")[:10]
                libelle = (noeud.get("statutConclusion") or {}).get("libelle")
                lu = lire_conclusion(libelle)
                if chambre is None or len(jour) < 10 or jour < depuis or lu is None:
                    continue
                statut, modalite = lu
                decisions.append(
                    DecisionSeance(
                        uid=str(noeud.get("uid") or ""),
                        dossier_ref=ref,
                        chambre=chambre,
                        jour=jour,
                        etape=label.strip(),
                        conclusion=str(libelle).strip(),
                        statut=statut,
                        modalite=modalite,
                        votes_cites=tuple(_refs_de_votes(noeud)),
                    )
                )
    return [d for d in decisions if d.uid and d.etape]


# ---------------------------------------------------------------------------
# Titres officiels d'un dossier (nommer un dossier neuf, vérifier un titre)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TitresDossiers:
    """Titres de chaque dossier de l'archive.

    `titre` est celui du dossier (`titreDossier.titre`), bien casé : c'est lui
    que l'app affiche pour un dossier qu'aucun scrutin public ne nomme. `mots`
    réunit les mots de ce titre et de ceux des textes du dossier — c'est contre
    eux qu'on vérifie qu'un titre cité par un vote désigne bien ce dossier.
    `slug_senat` est le dossier du Sénat que l'archive associe (`senatChemin`).
    """

    titre: dict[str, str]
    mots: dict[str, frozenset[str]]
    url_senat: dict[str, str]

    def slug_senat(self, ref: str) -> str | None:
        return slug_dossier_senat(self.url_senat.get(ref))


def _mots(titre: str) -> set[str]:
    return {
        m
        for m in re.split(r"[^a-z0-9]+", fold(titre))
        if len(m) >= 4 and m not in _MOTS_VIDES
    }


def construire_titres(dossiers: list[dict], documents: list[dict]) -> TitresDossiers:
    """Index des titres par `dossierRef` (première copie vue gagne)."""
    titre: dict[str, str] = {}
    mots: dict[str, set[str]] = defaultdict(set)
    url_senat: dict[str, str] = {}
    for brut in dossiers:
        dp = brut.get("dossierParlementaire") or brut
        ref = dp.get("uid") or ""
        if not ref or ref in titre:
            continue
        titres = dp.get("titreDossier") or {}
        libelle = (titres.get("titre") or "").strip()
        if libelle:
            titre[ref] = libelle
            mots[ref] |= _mots(libelle)
        chemin = (titres.get("senatChemin") or "").strip()
        if chemin:
            url_senat[ref] = chemin
    for brut in documents:
        doc = brut.get("document") or brut
        ref = doc.get("dossierRef") or ""
        if not ref or (doc.get("denominationStructurelle") or "") not in _DENOMINATIONS_TEXTE:
            continue
        principal = ((doc.get("titres") or {}).get("titrePrincipal") or "").strip()
        if principal:
            mots[ref] |= _mots(principal)
    return TitresDossiers(
        titre=titre,
        mots={ref: frozenset(m) for ref, m in mots.items()},
        url_senat=url_senat,
    )


def titres_concordants(titre_cite: str, mots_dossier: frozenset[str]) -> bool:
    """Le titre cité par un vote désigne-t-il ce dossier ?

    Part des mots significatifs du titre cité retrouvés dans les titres du
    dossier. Un titre tronqué (« … ») perd son dernier mot, coupé. Trop peu de
    mots → on ne conclut rien (§2.5)."""
    titre = titre_cite.strip()
    if titre.endswith("…"):
        titre = titre[:-1].rsplit(" ", 1)[0]
    mots = _mots(titre)
    if len(mots) < _MOTS_MIN or not mots_dossier:
        return False
    return len(mots & mots_dossier) / len(mots) >= _SEUIL_CONCORDANCE


# ---------------------------------------------------------------------------
# Décisions déjà racontées par un scrutin public
# ---------------------------------------------------------------------------

_RE_ARTICLE_UNIQUE = re.compile(r"^l'article unique\b")
_RE_TEXTE_DIRECT = re.compile(r"^l[ae] (?:proposition|projet) de (?:loi|resolution)\b")
_RE_MOTION = re.compile(r"^la motion\b")


def conclut_le_texte(objet_officiel: str) -> bool:
    """Ce scrutin public tranche-t-il le texte (et pas un article, pas un
    amendement) ? Mêmes formes que l'ancre du désaccord (`sync._vote_conclusif`) :
    l'ensemble, l'article unique, le texte cité directement, une motion qui
    clôt l'examen."""
    if est_amendement(objet_officiel):
        return False
    objet = fold(objet_officiel)
    return bool(
        "ensemble" in objet
        or _RE_ARTICLE_UNIQUE.match(objet)
        or _RE_TEXTE_DIRECT.match(objet)
        or _RE_MOTION.match(objet)
    )


def _ecart(a: str, b: str) -> int:
    return abs((date.fromisoformat(a[:10]) - date.fromisoformat(b[:10])).days)


def decisions_sans_scrutin(
    decisions: list[DecisionSeance], votes: list[VotePublic]
) -> list[DecisionSeance]:
    """Les décisions qu'aucun scrutin public ne raconte déjà.

    - 49.3 et article 151-7 : il n'y a, par définition, eu **aucun** vote sur le
      texte — la décision est toujours retenue.
    - Main levée : écartée si l'acte cite lui-même son scrutin (`voteRefs`), ou
      si un scrutin public conclusif du même dossier, dans la même chambre, tombe
      le même jour (à `_FENETRE_JOURS` près quand aucune autre décision du
      dossier n'occupe ce jour-là). Sinon, c'est bien un vote sans scrutin.
    """
    jours_votes: dict[tuple[str, Chambre], set[str]] = defaultdict(set)
    for v in votes:
        if conclut_le_texte(v.objet):
            jours_votes[(v.dossier_id, v.chambre)].add(v.date[:10])
    jours_decisions: dict[tuple[str, Chambre], set[str]] = defaultdict(set)
    for d in decisions:
        jours_decisions[(d.dossier_ref, d.chambre)].add(d.jour)

    retenues: list[DecisionSeance] = []
    for d in decisions:
        if d.modalite is not ModaliteVote.main_levee:
            retenues.append(d)
            continue
        if d.votes_cites:
            continue
        cle = (d.dossier_ref, d.chambre)
        jours = jours_votes.get(cle, set())
        if d.jour in jours:
            continue
        autres = jours_decisions[cle] - {d.jour}
        if any(_ecart(j, d.jour) <= _FENETRE_JOURS and j not in autres for j in jours):
            continue
        retenues.append(d)
    return retenues


def rattacher_par_decisions(
    parses: list[ScrutinParse],
    decisions: list[DecisionSeance],
    titres: TitresDossiers,
    votes: list[VotePublic],
) -> int:
    """Range sous leur dossier officiel les votes d'un dossier reconstitué que
    désigne une décision de séance (pure, modifie `parses` en place).

    Un texte que la correspondance de titre n'a pas retrouvé (coquille de la
    source, titre tronqué) vit dans un dossier `TXT-…` ou `SEN-…`, pendant que
    l'archive enregistre, ce jour-là, la décision de son dossier officiel sans
    citer le scrutin. Trois faits doivent concorder pour les réunir : la même
    chambre, le même jour, et un titre concordant (`titres_concordants`).
    Une décision qui désigne plusieurs dossiers reconstitués, ou un dossier
    reconstitué que plusieurs décisions réclament, ne déplace rien (§2.5).

    `votes` (les scrutins publics connus, base comprise) écarte une décision que
    son dossier raconte déjà par un scrutin du même jour.

    Renvoie le nombre de votes déplacés.
    """
    # Votes conclusifs des dossiers SANS référence officielle, par (chambre, jour).
    orphelins: dict[tuple[Chambre, str], list[ScrutinParse]] = defaultdict(list)
    for p in parses:
        if (
            p.dossier_ref
            or p.est_evenement_autonome
            or not p.scrutin.scrutin_public
            or not conclut_le_texte(p.scrutin.objet)
        ):
            continue
        orphelins[(p.scrutin.chambre, p.scrutin.date[:10])].append(p)
    if not orphelins:
        return 0
    couverts = {
        (v.dossier_id, v.chambre, v.date[:10])
        for v in votes
        if conclut_le_texte(v.objet)
    }

    refs_par_groupe: dict[str, set[str]] = defaultdict(set)
    for d in decisions:
        if d.modalite is not ModaliteVote.main_levee or d.votes_cites:
            continue
        if (d.dossier_ref, d.chambre, d.jour) in couverts:
            continue
        mots = titres.mots.get(d.dossier_ref, frozenset())
        groupes = {
            p.dossier_id
            for p in orphelins.get((d.chambre, d.jour), [])
            if titres_concordants(p.dossier_titre, mots)
        }
        if len(groupes) == 1:
            refs_par_groupe[groupes.pop()].add(d.dossier_ref)

    cible = {g: refs.pop() for g, refs in refs_par_groupe.items() if len(refs) == 1}
    deplaces = 0
    for p in parses:
        ref = cible.get(p.dossier_id)
        if ref is None:
            continue
        p.dossier_id = ref
        p.dossier_ref = ref
        p.scrutin.dossier_id = ref
        deplaces += 1
    return deplaces


# ---------------------------------------------------------------------------
# Une décision → un « vote » sans décompte
# ---------------------------------------------------------------------------


def objet_decision(d: DecisionSeance) -> str:
    """L'objet affiché d'une décision : l'étape et la conclusion, verbatim.

    Aucun vote n'a d'objet officiel ici (il n'y a pas de scrutin) : on compose
    avec les deux seuls libellés que la source donne, sans un mot de plus."""
    return f"{d.etape} — {d.conclusion}"


def source_decision(d: DecisionSeance, titres: TitresDossiers) -> SourceOfficielle:
    """Où vérifier la décision : la page du dossier dans la chambre qui l'a
    prise (§7.5). Le Sénat à défaut de mieux renvoie à la page de l'Assemblée,
    qui suit les deux chambres."""
    url_senat = titres.url_senat.get(d.dossier_ref)
    if d.chambre is Chambre.senat and url_senat and url_senat.startswith("http"):
        return SourceOfficielle(
            type="texte", libelle="Dossier législatif (Sénat)", url=url_senat
        )
    legislature = legislature_du_ref(d.dossier_ref) or ""
    return dossier_source(legislature, d.dossier_ref)


def parse_decision(d: DecisionSeance, titres: TitresDossiers) -> ScrutinParse | None:
    """La décision en `ScrutinParse` : un « vote » sans scrutin public.

    `resultat` vaut 0 partout parce que le contrat l'exige — `scrutin_public`
    faux et `modalite` disent qu'il n'y a pas de décompte, et rien ne doit
    l'afficher comme des voix. None si le dossier n'a pas de titre : on ne
    crée pas un dossier qu'on ne saurait pas nommer (§2.5)."""
    titre = titres.titre.get(d.dossier_ref)
    if not titre:
        return None
    scrutin = Scrutin(
        id=d.uid,
        dossier_id=d.dossier_ref,
        date=d.jour,
        objet=objet_decision(d),
        statut=d.statut,
        chambre=d.chambre,
        scrutin_public=False,
        modalite=d.modalite,
        etape=d.etape,
        conclusion=d.conclusion,
        resultat=ResultatGlobal(pour=0, contre=0, abstention=0, non_votants=0),
        sources=[source_decision(d, titres)],
    )
    return ScrutinParse(
        scrutin=scrutin,
        dossier_id=d.dossier_ref,
        dossier_titre=titre,
        dossier_ref=d.dossier_ref,
        theme=guess_theme(titre),
        legislature=legislature_du_ref(d.dossier_ref) or "",
        numero="",
        ref_du_scrutin=True,
    )

