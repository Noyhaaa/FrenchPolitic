"""Référentiel des sénateurs et de leurs votes nominatifs (pendant de `deputes`).

Source : l'annuaire JSON du Sénat (`senat.fr/api-senat/senateurs.json`), qui
donne pour chaque sénateur son **matricule** — la clé que citent les scrutins —,
son nom, son groupe et sa circonscription. Endpoint non documenté par
data.senat.fr : traité en best-effort, un échec laisse simplement le référentiel
inchangé.

Les sénateurs vivent dans **les mêmes tables que les députés** (`depute`,
`vote_depute`, `groupe`), discriminés par `chambre`. Leurs identifiants sont
préfixés (`SEN-…`) pour ne jamais entrer en collision avec les `acteurRef` (PA…)
et `organeRef` (PO…) de l'Assemblée.

⚠️ **Pas de « contre son groupe » ni de cohésion au Sénat.** Dans un scrutin
public ordinaire, les bulletins sont déposés par un délégué de groupe pour
l'ensemble de ses membres : le nominatif y reflète la position du GROUPE, pas
l'acte individuel de chaque sénateur. La source ne permet pas non plus de
distinguer ces scrutins de ceux à la tribune (art. 59), qui seuls sont
individuels. Une divergence « contre son groupe » calculée là-dessus serait un
artefact de procédure présenté comme un fait politique : on ne la calcule donc
pas du tout (§7.4, §2.5). `contre_son_groupe` reste `None`, et le portrait de
vote sort sans cohésion — l'app masque alors la ligne.
"""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass

from app.domain.enums import Chambre, PositionVote
from app.ingestion.deputes import VoteActeur
from app.ingestion.organes import GroupInfo
from app.schemas import Depute

# Préfixes d'identifiant : les deux chambres partagent les tables, jamais les ids.
PREFIXE_SENATEUR = "SEN-"
PREFIXE_GROUPE = "SEN-"

_BASE = "https://www.senat.fr"

# Couleurs par code de groupe du Sénat. Comme `GROUP_COLORS` côté Assemblée,
# c'est purement cosmétique : la neutralité (§7) porte sur le contenu, pas sur
# la couleur des groupes. L'annuaire du Sénat ne publie pas de couleur — cette
# table est donc un choix de présentation assumé, symétrique entre groupes
# (§7.4), et non une donnée de la source. Code inconnu → gris neutre.
COULEURS_GROUPES_SENAT: dict[str, str] = {
    "UMP": "#2E6FB5",   # Les Républicains
    "SOC": "#E24A6E",   # Socialiste, Écologiste et Républicain
    "UC": "#6EC1E4",    # Union Centriste
    "RTLI": "#F5A623",  # Les Indépendants – République et Territoires
    "LREM": "#F58220",  # Rassemblement des démocrates, progressistes et indépendants
    "CRC": "#A8324A",   # Communiste Républicain Citoyen et Écologiste – Kanaky
    "RDSE": "#F2C94C",  # Rassemblement Démocratique et Social Européen
    "GEST": "#2F8F4E",  # Écologiste – Solidarité et Territoires
    "NI": "#9AA0A6",    # Non inscrits
}
COULEUR_DEFAUT = "#9AA0A6"

# Codes de vote du JSON nominatif (`scr{annee}-{n}.json`).
POSITIONS: dict[str, PositionVote] = {
    "p": PositionVote.pour,
    "c": PositionVote.contre,
    "a": PositionVote.abstention,
    "n": PositionVote.non_votant,
}


def id_senateur(matricule: str) -> str:
    return f"{PREFIXE_SENATEUR}{matricule}"


def id_groupe_senat(code: str) -> str:
    return f"{PREFIXE_GROUPE}{code}"


def couleur_groupe(code: str) -> str:
    return COULEURS_GROUPES_SENAT.get(code.upper(), COULEUR_DEFAUT)


@dataclass(frozen=True)
class InfoSenateur:
    """Un sénateur tel que l'annuaire le décrit."""

    matricule: str
    nom: str  # « Prénom Nom », comme côté Assemblée
    groupe_code: str
    groupe_nom: str
    groupe_abrev: str
    circonscription: str
    portrait_url: str | None = None
    # Commission permanente, lue dans `organismes` (cf. `_commission_permanente`).
    commission: str | None = None


# Les sept commissions permanentes du Sénat portent un `ordre` 7001-7007 ; la
# commission des affaires européennes, à laquelle 41 sénateurs appartiennent EN
# PLUS de la leur, ouvre une autre série (8001). Prendre le plus petit `ordre`
# donne donc la commission permanente — sans lister des libellés en dur, qui
# vieilliraient mal. Vérifié sur l'annuaire complet : le premier élément est
# toujours celui de plus petit `ordre` (346/346), et 346 sénateurs sur 348 en
# ont une.
def _commission_permanente(brut: dict) -> str | None:
    """Libellé de la commission permanente du sénateur, sinon None (§2.5)."""
    commissions = [
        o
        for o in (brut.get("organismes") or [])
        if isinstance(o, dict)
        and o.get("type") == "COMMISSION"
        and (o.get("libelle") or "").strip()
    ]
    if not commissions:
        return None
    # `ordre` manquant → repoussé en fin de tri plutôt que traité comme 0, qui
    # le ferait gagner à tort.
    retenue = min(commissions, key=lambda o: o.get("ordre") or float("inf"))
    return str(retenue["libelle"]).strip()


def construire_annuaire(bruts: list[dict]) -> dict[str, InfoSenateur]:
    """Annuaire `matricule` → `InfoSenateur` (fonction pure).

    Sert au vote nominatif : les scrutins ne citent que des matricules. Un
    enregistrement sans matricule ou sans nom est ignoré plutôt que complété.
    """
    annuaire: dict[str, InfoSenateur] = {}
    for brut in bruts:
        if not isinstance(brut, dict):
            continue
        matricule = str(brut.get("matricule") or "").strip()
        nom = " ".join(
            p for p in (brut.get("prenom"), brut.get("nom")) if p
        ).strip()
        if not matricule or not nom:
            continue
        groupe = brut.get("groupe") or {}
        code = str(groupe.get("code") or "").strip()
        avatar = brut.get("urlAvatar")
        annuaire[matricule] = InfoSenateur(
            matricule=matricule,
            nom=nom,
            groupe_code=code,
            groupe_nom=str(groupe.get("libelle") or code or ""),
            groupe_abrev=str(groupe.get("libelleCourt") or code or "?"),
            circonscription=str((brut.get("circonscription") or {}).get("libelle") or ""),
            # Donnée par la source (contrairement à l'AN où l'URL est dérivée
            # de l'acteurRef, donc à vérifier avant de l'attacher).
            portrait_url=f"{_BASE}{avatar}" if avatar else None,
            commission=_commission_permanente(brut),
        )
    return annuaire


def _lignes_csv_senat(csv_texte: str) -> list[dict[str, str]]:
    """Lignes d'un export data.senat.fr (en-tête de requête en `%` ignoré)."""
    corps = "\n".join(
        ligne for ligne in csv_texte.splitlines() if not ligne.startswith("%")
    )
    return [
        {k.strip(): (v or "").strip() for k, v in ligne.items() if k}
        for ligne in csv.DictReader(io.StringIO(corps))
    ]


def construire_annuaire_historique(
    csv_texte: str, annuaire: dict[str, InfoSenateur]
) -> dict[str, InfoSenateur]:
    """Les sénateurs qui ne siègent plus, depuis `ODSEN_GENERAL.csv` (pure).

    Sans eux, un scrutin ancien perdait le nom de chaque sénateur parti depuis
    — au renouvellement de septembre 2026, c'étaient 68 noms effacés de toute
    la session précédente. Ils servent seulement à **nommer** : ni fiche, ni
    lien (le référentiel servi reste l'annuaire du jour).

    Le groupe d'un votant se lit d'abord sur la page du scrutin, qui liste les
    noms de chaque groupe (`senat._groupe_du_jour`). Le **dernier groupe
    connu** ici n'est qu'un repli, sous le contrôle des décomptes. Son libellé
    (« RDPI », « Les Républicains », ou un ancien code comme « UC ») est traduit
    par l'annuaire du jour, qui porte libellés et codes ; un groupe qu'il ne
    connaît plus reste vide (`groupe_code=""`) — le sénateur est nommé si la
    page le place, jamais rangé dans un groupe deviné (§2.5).
    """
    code_par_libelle: dict[str, str] = {}
    for info in annuaire.values():
        if info.groupe_code:
            code_par_libelle.setdefault(info.groupe_code, info.groupe_code)
            if info.groupe_abrev:
                code_par_libelle[info.groupe_abrev] = info.groupe_code
    infos_par_code = {info.groupe_code: info for info in annuaire.values()}
    historique: dict[str, InfoSenateur] = {}
    for ligne in _lignes_csv_senat(csv_texte):
        matricule = ligne.get("Matricule", "")
        if not matricule or matricule in annuaire:
            continue
        nom = " ".join(
            p for p in (ligne.get("Prénom usuel"), ligne.get("Nom usuel")) if p
        ).strip()
        if not nom:
            continue
        code = code_par_libelle.get(ligne.get("Groupe politique", ""), "")
        groupe = infos_par_code.get(code)
        historique[matricule] = InfoSenateur(
            matricule=matricule,
            nom=nom,
            groupe_code=code,
            groupe_nom=groupe.groupe_nom if groupe else "",
            groupe_abrev=groupe.groupe_abrev if groupe else "",
            circonscription=ligne.get("Circonscription", ""),
        )
    return historique


def build_senateurs(annuaire: dict[str, InfoSenateur]) -> list[Depute]:
    """Référentiel servi par l'API, à partir de l'annuaire (fonction pure).

    `depuis` (début de mandat) reste `None` : l'annuaire ne le publie pas, et on
    ne le déduit pas de la série d'élection (§2.5) — l'app masque le champ.
    Vérifié à la source : les champs servis sont matricule, nom, groupe,
    circonscription, organismes, avatar — aucune date de mandat. Ce n'est donc
    pas un oubli d'ingestion, et le combler demanderait une autre source.
    `ODSEN_ELUSEN.csv` (data.senat.fr) publie bien les mandats, mais vérifié
    le 12 oct. 2026, il n'avait pas suivi le renouvellement de septembre :
    197 sénateurs actifs sur 348, et aucun mandat en cours. Une date tirée de
    là serait fausse pour la moitié de l'hémicycle.
    """
    return [
        Depute(
            id=id_senateur(info.matricule),
            nom=info.nom,
            chambre=Chambre.senat,
            groupe_id=id_groupe_senat(info.groupe_code),
            groupe_nom=info.groupe_nom,
            groupe_couleur=couleur_groupe(info.groupe_code),
            circonscription=info.circonscription,
            depuis=None,
            portrait_url=info.portrait_url,
            commission=info.commission,
        )
        for info in annuaire.values()
    ]


def groupes_senat(annuaire: dict[str, InfoSenateur]) -> list[GroupInfo]:
    """Groupes politiques du Sénat déduits de l'annuaire (fonction pure)."""
    groupes: dict[str, GroupInfo] = {}
    for info in annuaire.values():
        if not info.groupe_code:
            continue
        identifiant = id_groupe_senat(info.groupe_code)
        if identifiant in groupes:
            continue
        groupes[identifiant] = GroupInfo(
            id=identifiant,
            nom=info.groupe_nom,
            abrev=info.groupe_abrev,
            couleur=couleur_groupe(info.groupe_code),
        )
    return list(groupes.values())


def votes_du_scrutin_senat(
    votes_bruts: object, annuaire: dict[str, InfoSenateur]
) -> list[VoteActeur]:
    """Votes nominatifs d'un scrutin du Sénat (fonction pure).

    `contre_son_groupe` reste **toujours** `None` : cf. l'avertissement en tête
    de module — la délégation de vote par groupe rend ce fait indéfendable au
    Sénat, et la source ne dit pas quels scrutins y échappent.

    Un matricule absent de l'annuaire est ignoré : un sénateur dont on ne sait
    pas le nom n'a pas sa place dans une ventilation nominative (§2.5, même
    règle que côté Assemblée).
    """
    if isinstance(votes_bruts, dict):
        votes_bruts = votes_bruts.get("votes")
    if not isinstance(votes_bruts, list):
        return []

    votes: dict[str, VoteActeur] = {}
    for brut in votes_bruts:
        if not isinstance(brut, dict):
            continue
        matricule = str(brut.get("matricule") or "").strip()
        position = POSITIONS.get(str(brut.get("vote") or "").strip().lower())
        if not matricule or position is None or matricule not in annuaire:
            continue
        identifiant = id_senateur(matricule)
        if identifiant in votes:
            continue
        votes[identifiant] = VoteActeur(
            acteur_ref=identifiant,
            position=position,
            contre_son_groupe=None,
        )
    return list(votes.values())
