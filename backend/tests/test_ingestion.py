"""Tests d'ingestion open data (parsing pur, sans réseau ni base)."""
from __future__ import annotations

from app.domain.enums import PositionVote, StatutScrutin
from app.ingestion.assemblee import parse_scrutin
from app.ingestion.normalize import guess_theme, map_position, map_statut
from app.ingestion.organes import build_resolver_from_organes
from app.ingestion.sync import controles_coherence

ORGANES = [
    {"organe": {"uid": "PO845401", "codeType": "GP", "libelle": "Rassemblement National", "libelleAbrev": "RN", "viMoDe": {"dateFin": None}}},
    {"organe": {"uid": "PO845413", "codeType": "GP", "libelle": "La France insoumise - NFP", "libelleAbrev": "LFI-NFP", "viMoDe": {"dateFin": None}}},
    {"organe": {"uid": "PO000000", "codeType": "GP", "libelle": "Groupe dissous", "libelleAbrev": "OLD", "viMoDe": {"dateFin": "2024-01-01"}}},
    {"organe": {"uid": "PO111111", "codeType": "COMPER", "libelle": "Une commission"}},
]

SCRUTIN = {
    "scrutin": {
        "uid": "VTANR5L17V999",
        "numero": "999",
        "legislature": "17",
        "dateScrutin": "2026-07-02",
        "sort": {"code": "rejeté"},
        "titre": "l'amendement n° 80 de Mme X",
        "objet": {
            "libelle": "l'amendement n° 80 de Mme X",
            "dossierLegislatif": {
                "libelle": "Projet de loi sur le logement social",
                "dossierRef": "DLR5L17N53940",
            },
        },
        "syntheseVote": {
            "decompte": {"nonVotants": "1", "pour": "21", "contre": "39", "abstentions": "4"}
        },
        "ventilationVotes": {
            "organe": {
                "organeRef": "PO838901",
                "groupes": {
                    "groupe": [
                        {"organeRef": "PO845401", "vote": {"positionMajoritaire": "contre", "decompteVoix": {"pour": "0", "contre": "10", "abstentions": "0"}}},
                        {"organeRef": "PO845413", "vote": {"positionMajoritaire": "pour", "decompteVoix": {"pour": "21", "contre": "29", "abstentions": "4"}}},
                    ]
                },
            }
        },
    }
}


def test_resolver_noms_et_couleurs():
    resolver = build_resolver_from_organes(ORGANES)
    assert len(resolver) == 2  # dissous et non-GP exclus
    rn = resolver.resolve("PO845401")
    assert rn.nom == "Rassemblement National"
    assert rn.couleur == "#1B3A5C"


def test_resolver_ref_inconnue_ne_fabrique_pas_de_nom():
    resolver = build_resolver_from_organes(ORGANES)
    inconnu = resolver.resolve("PO_INEXISTANT")
    assert inconnu.nom == "PO_INEXISTANT"


def test_parse_scrutin_complet():
    resolver = build_resolver_from_organes(ORGANES)
    s = parse_scrutin(SCRUTIN, resolver)

    assert s.id == "VTANR5L17V999"
    assert s.statut == StatutScrutin.rejete
    assert s.date == "2026-07-02"
    # Titre clair = libellé du dossier (plus lisible que « l'amendement… »).
    assert s.titre_clair == "Projet de loi sur le logement social"
    assert s.theme == "Logement"  # deviné par mot-clé
    assert s.resultat.pour == 21 and s.resultat.contre == 39
    assert s.resultat.abstention == 4 and s.resultat.non_votants == 1
    assert len(s.positions_groupes) == 2
    assert s.positions_groupes[0].groupe_nom == "Rassemblement National"
    # Toujours des scrutins publics dans cette archive.
    assert s.scrutin_public is True
    # Sources : scrutin + dossier.
    types = {src.type.value for src in s.sources}
    assert "scrutin" in types and "texte" in types


def test_parse_scrutin_resume_vide_non_comble():
    """Sans génération IA, le résumé reste vide + confiance faible (§2.5)."""
    resolver = build_resolver_from_organes(ORGANES)
    s = parse_scrutin(SCRUTIN, resolver)
    assert s.resume.resume == []
    assert s.resume.confiance.value == "faible"
    assert "resume" in s.resume.champs_non_documentes


def test_coherence_ok_quand_sommes_correspondent():
    resolver = build_resolver_from_organes(ORGANES)
    s = parse_scrutin(SCRUTIN, resolver)
    # pour: 0+21=21, contre: 10+29=39, abst: 0+4=4 → cohérent avec le global.
    assert controles_coherence(s) == []


def test_coherence_signale_incoherence():
    resolver = build_resolver_from_organes(ORGANES)
    s = parse_scrutin(SCRUTIN, resolver)
    s.resultat.pour = 999  # casse la cohérence
    anomalies = controles_coherence(s)
    assert any("pour" in a for a in anomalies)


def test_map_statut():
    assert map_statut("adopté") == "adopte"
    assert map_statut("rejeté") == "rejete"


def test_map_position_absent_devient_non_votant():
    assert map_position("absent") == PositionVote.non_votant
    assert map_position("pour") == PositionVote.pour


def test_guess_theme():
    assert guess_theme("Accès aux soins et hôpitaux") == "Santé"
    assert guess_theme("Un sujet sans mot-clé identifiable") == "Autre"
