"""Rattachement d'un vote à son dossier par les actes législatifs (`voteRefs`).

Pur, sans réseau ni base. Les cas reproduisent ceux mesurés sur l'archive de la
17e législature : deux lois spéciales au titre presque identique (déc. 2024 et
déc. 2025), un scrutin cité par un dossier d'une législature non chargée, un
vote cité par deux dossiers.
"""
from __future__ import annotations

from app.ingestion.assemblee import parse_scrutin, rattacher_par_votes_officiels
from app.ingestion.dossiers_legislatifs import (
    Reconciliation,
    construire_votes_officiels,
)
from app.ingestion.organes import build_resolver_from_organes
from app.ingestion.sync import _merge_avec_existant, build_dossier

_LOI_SPECIALE = (
    "projet de loi spéciale prévue par l'article 45 de la loi organique du "
    "1er août 2001 relative aux lois de finances"
)


def _scrutin(uid: str, date: str, objet: str, dossier_ref: str | None = None) -> dict:
    dossier = {"dossierRef": dossier_ref, "libelle": "Titre"} if dossier_ref else {}
    return {
        "scrutin": {
            "uid": uid,
            "numero": uid.rsplit("V", 1)[-1],
            "legislature": "17",
            "dateScrutin": date,
            "sort": {"code": "adopté"},
            "titre": objet,
            "objet": {"libelle": objet, "dossierLegislatif": dossier},
            "syntheseVote": {"decompte": {"pour": "10", "contre": "2"}},
            "ventilationVotes": {"organe": {"groupes": {"groupe": []}}},
        }
    }


def _dossier(uid: str, actes: list[dict]) -> dict:
    return {
        "dossierParlementaire": {
            "uid": uid,
            "actesLegislatifs": {"acteLegislatif": actes},
        }
    }


def _acte(code: str, date: str, votes: list[str] | None = None) -> dict:
    acte: dict = {"codeActe": code, "dateActe": f"{date}T00:00:00.000+01:00"}
    if votes:
        acte["voteRefs"] = {"voteRef": votes[0] if len(votes) == 1 else votes}
    return acte


# Deux lois spéciales, une par an. Seuls les votes sur l'ensemble sont cités.
_DOSSIERS = [
    _dossier(
        "DLR5L17N51079",
        [
            _acte("AN1-DEPOT", "2024-12-11"),
            _acte("AN1-DEBATS-DEC", "2024-12-16", ["VTANR5L17V525"]),
            _acte("PROM-PUB", "2024-12-21"),
        ],
    ),
    _dossier(
        "DLR5L17N53386",
        [
            _acte("AN1-DEPOT", "2025-12-19"),
            _acte("AN1-DEBATS-DEC", "2025-12-23", ["VTANR5L17V4947"]),
            _acte("PROM-PUB", "2025-12-26"),
        ],
    ),
]

# La réconciliation par titre, elle, envoie TOUT vers le dossier de 2024 :
# c'est l'erreur constatée en base.
_RECO = Reconciliation(
    _ref_par_titre={},
    _ref_par_signature={},
    _refs_par_signature_brute={},
)


def _parses(*bruts: dict) -> list:
    resolver = build_resolver_from_organes([])
    return [parse_scrutin(b, resolver, reconciliation=_RECO) for b in bruts]


def _loi_speciale(uid: str, date: str, objet: str) -> dict:
    return _scrutin(uid, date, f"{objet} du {_LOI_SPECIALE}")


def test_index_des_votes_cites_et_periodes():
    votes = construire_votes_officiels(_DOSSIERS, (17, 16))
    assert votes.ref_pour_vote("VTANR5L17V525") == "DLR5L17N51079"
    assert votes.ref_pour_vote("VTANR5L17V4947") == "DLR5L17N53386"
    assert votes.ref_pour_vote("VTANR5L17V1") is None
    assert votes.couvre("DLR5L17N53386", "2025-12-23")
    assert not votes.couvre("DLR5L17N53386", "2024-12-16")


def test_un_dossier_hors_legislatures_chargees_ne_cite_rien():
    """L'archive de la 17e contient des dossiers plus anciens ; l'un d'eux y
    cite un scrutin de la 17e, sans rien qui le corrobore."""
    ancien = _dossier(
        "DLR5L15N43846", [_acte("AN1-DEBATS-DEC", "2025-04-07", ["VTANR5L17V1303"])]
    )
    votes = construire_votes_officiels([ancien], (17, 16))
    assert votes.ref_pour_vote("VTANR5L17V1303") is None


def test_un_vote_cite_par_deux_dossiers_est_ecarte():
    doublon = [
        _dossier("DLR5L17N1", [_acte("AN1-DEBATS-DEC", "2025-01-01", ["V9"])]),
        _dossier("DLR5L17N2", [_acte("AN1-DEBATS-DEC", "2025-01-01", ["V9"])]),
    ]
    assert construire_votes_officiels(doublon, (17,)).ref_pour_vote("V9") is None


def test_un_meme_dossier_dans_deux_archives_n_est_pas_une_ambiguite():
    """Un dossier reporté après une dissolution figure dans les deux archives."""
    copie = _DOSSIERS[0]
    votes = construire_votes_officiels([copie, copie], (17, 16))
    assert votes.ref_pour_vote("VTANR5L17V525") == "DLR5L17N51079"


def test_chaque_loi_speciale_retrouve_son_dossier():
    """Les votes d'article d'une loi spéciale suivent le vote sur l'ensemble de
    LEUR année, que la date départage — le titre seul ne le peut pas."""
    parses = _parses(
        _loi_speciale("VTANR5L17V525", "2024-12-16", "l'ensemble"),
        _loi_speciale("VTANR5L17V520", "2024-12-16", "l'article 1er"),
        _loi_speciale("VTANR5L17V4947", "2025-12-23", "l'ensemble"),
        _loi_speciale("VTANR5L17V4942", "2025-12-23", "l'article 1er"),
    )
    votes = construire_votes_officiels(_DOSSIERS, (17, 16))
    deplaces = rattacher_par_votes_officiels(parses, votes)

    par_id = {p.scrutin.id: p for p in parses}
    assert par_id["VTANR5L17V525"].dossier_id == "DLR5L17N51079"
    assert par_id["VTANR5L17V520"].dossier_id == "DLR5L17N51079"
    assert par_id["VTANR5L17V4947"].dossier_id == "DLR5L17N53386"
    assert par_id["VTANR5L17V4942"].dossier_id == "DLR5L17N53386"
    # Le scrutin et son parse disent la même chose.
    assert par_id["VTANR5L17V4942"].scrutin.dossier_id == "DLR5L17N53386"
    assert par_id["VTANR5L17V4942"].dossier_ref == "DLR5L17N53386"
    assert deplaces == 4  # tous partaient d'un dossier reconstitué « TXT-… »


def test_un_vote_hors_de_toute_periode_reste_ou_il_etait():
    """Un vote du même texte, mais daté hors de la vie documentée de chaque
    dossier candidat (archive en retard sur le vote) : on ne devine pas."""
    parses = _parses(
        _loi_speciale("VTANR5L17V525", "2024-12-16", "l'ensemble"),
        _loi_speciale("VTANR5L17V9000", "2026-12-20", "l'article 1er"),
    )
    avant = parses[1].dossier_id
    rattacher_par_votes_officiels(parses, construire_votes_officiels(_DOSSIERS, (17,)))
    assert parses[1].dossier_id == avant
    assert avant.startswith("TXT-")


def test_le_dossier_ref_du_scrutin_prime():
    """Un vote qui porte lui-même son `dossierRef` n'est jamais déplacé."""
    brut = _scrutin(
        "VTANR5L17V4947", "2025-12-23", f"l'ensemble du {_LOI_SPECIALE}", "DLR5L17N9"
    )
    parses = _parses(brut)
    rattacher_par_votes_officiels(parses, construire_votes_officiels(_DOSSIERS, (17,)))
    assert parses[0].dossier_id == "DLR5L17N9"


def test_un_evenement_autonome_n_est_pas_deplace():
    """Une motion de censure reste son propre dossier : celui d'« engagement de
    responsabilité » qui la cite n'est pas un texte de loi."""
    brut = _scrutin("VTANR5L17V7", "2025-02-05", "la motion de censure")
    dossiers = [
        _dossier("DLR5L17N7", [_acte("AN21-MOTION-VOTE", "2025-02-05", ["VTANR5L17V7"])])
    ]
    parses = _parses(brut)
    assert parses[0].est_evenement_autonome
    rattacher_par_votes_officiels(parses, construire_votes_officiels(dossiers, (17,)))
    assert parses[0].dossier_id == "VTANR5L17V7"


def test_fusion_retire_un_vote_parti_et_ne_pose_pas_de_badge():
    """Un vote rangé ailleurs ce run quitte l'ancien dossier ; et il n'est pas
    un « nouveau vote » pour celui qui le reçoit (§7.7)."""
    parses = _parses(
        _loi_speciale("VTANR5L17V525", "2024-12-16", "l'ensemble"),
        _loi_speciale("VTANR5L17V4947", "2025-12-23", "l'ensemble"),
    )
    ancien = build_dossier(parses)  # l'état fautif : les deux dans un dossier
    ancien.id = "DLR5L17N51079"
    rattacher_par_votes_officiels(parses, construire_votes_officiels(_DOSSIERS, (17,)))
    dossier_de = {p.scrutin.id: p.dossier_id for p in parses}

    reste = build_dossier([parses[0]])
    fusion = _merge_avec_existant(ancien, reste, dossier_de, {"VTANR5L17V4947"})
    assert [s.id for s in fusion.scrutins] == ["VTANR5L17V525"]
    # La date et le statut ne viennent plus du vote parti.
    assert fusion.date_dernier_scrutin == "2024-12-16"

    recu = build_dossier([parses[1]])
    vide = build_dossier([parses[1]])
    vide.scrutins = []
    fusion = _merge_avec_existant(vide, recu, dossier_de, {"VTANR5L17V4947"})
    assert fusion.mise_a_jour is None
