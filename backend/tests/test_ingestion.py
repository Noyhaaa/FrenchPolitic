"""Tests d'ingestion open data (parsing pur, sans réseau ni base)."""
from __future__ import annotations

from app.domain.enums import PositionVote, StatutScrutin
from app.ingestion.assemblee import parse_scrutin
from app.ingestion.normalize import guess_theme, map_position, map_statut
from app.ingestion.organes import build_acteurs_from_amo, build_resolver_from_organes
from app.ingestion.sync import (
    _merge_avec_existant,
    build_dossier,
    controles_coherence,
)

ORGANES = [
    {"organe": {"uid": "PO845401", "codeType": "GP", "libelle": "Rassemblement National", "libelleAbrev": "RN", "viMoDe": {"dateFin": None}}},
    {"organe": {"uid": "PO845413", "codeType": "GP", "libelle": "La France insoumise - NFP", "libelleAbrev": "LFI-NFP", "viMoDe": {"dateFin": None}}},
    {"organe": {"uid": "PO000000", "codeType": "GP", "libelle": "Groupe dissous", "libelleAbrev": "OLD", "viMoDe": {"dateFin": "2024-01-01"}}},
    {"organe": {"uid": "PO111111", "codeType": "COMPER", "libelle": "Une commission"}},
]

ACTEURS = [
    {"acteur": {"uid": {"#text": "PA100"}, "etatCivil": {"ident": {"civ": "Mme", "prenom": "Jeanne", "nom": "Martin"}}}},
    {"acteur": {"uid": {"#text": "PA200"}, "etatCivil": {"ident": {"civ": "M.", "prenom": "Paul", "nom": "Durand"}}}},
    {"acteur": {"uid": "PA300", "etatCivil": {"ident": {"prenom": "Luc", "nom": "Bernard"}}}},
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
                        {
                            "organeRef": "PO845401",
                            "vote": {
                                "positionMajoritaire": "contre",
                                "decompteVoix": {"pour": "0", "contre": "10", "abstentions": "0"},
                                "decompteNominatif": {
                                    "pours": None,
                                    # 1 votant → objet (pas liste) : cas réel de l'open data.
                                    "contres": {"votant": {"acteurRef": "PA100"}},
                                    "abstentions": None,
                                },
                            },
                        },
                        {
                            "organeRef": "PO845413",
                            "vote": {
                                "positionMajoritaire": "pour",
                                "decompteVoix": {"pour": "21", "contre": "29", "abstentions": "4"},
                                "decompteNominatif": {
                                    "pours": {"votant": [{"acteurRef": "PA200"}, {"acteurRef": "PA_INCONNU"}]},
                                    "contres": None,
                                    "abstentions": {"votant": [{"acteurRef": "PA300"}]},
                                },
                            },
                        },
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


def test_annuaire_acteurs():
    acteurs = build_acteurs_from_amo(ACTEURS)
    assert acteurs["PA100"] == "Jeanne Martin"
    assert acteurs["PA300"] == "Luc Bernard"  # uid en chaîne simple aussi accepté


def test_parse_nominatif_avec_annuaire():
    resolver = build_resolver_from_organes(ORGANES)
    acteurs = build_acteurs_from_amo(ACTEURS)
    s = parse_scrutin(SCRUTIN, resolver, acteurs).scrutin

    rn, lfi = s.positions_groupes
    assert rn.noms_contre == ["Jeanne Martin"]  # votant unique sérialisé en objet
    assert rn.noms_pour is None  # bloc absent → masqué, pas inventé (§2.5)
    # Acteur absent de l'annuaire → on garde sa référence (factuel).
    assert lfi.noms_pour == ["Paul Durand", "PA_INCONNU"]
    assert lfi.noms_abstention == ["Luc Bernard"]


def test_parse_sans_annuaire_pas_de_noms():
    resolver = build_resolver_from_organes(ORGANES)
    s = parse_scrutin(SCRUTIN, resolver).scrutin
    assert all(
        g.noms_pour is None and g.noms_contre is None for g in s.positions_groupes
    )


def test_parse_scrutin_complet():
    resolver = build_resolver_from_organes(ORGANES)
    parse = parse_scrutin(SCRUTIN, resolver)
    s = parse.scrutin

    assert s.id == "VTANR5L17V999"
    assert s.dossier_id == "DLR5L17N53940"
    assert s.statut == StatutScrutin.rejete
    assert s.date == "2026-07-02"
    # Objet = ce sur quoi on a voté (le scrutin lui-même).
    assert s.objet == "l'amendement n° 80 de Mme X"
    # Le titre du dossier (plus lisible) est porté par le ScrutinParse.
    assert parse.dossier_titre == "Projet de loi sur le logement social"
    assert parse.theme == "Logement"  # deviné par mot-clé
    assert s.resultat.pour == 21 and s.resultat.contre == 39
    assert s.resultat.abstention == 4 and s.resultat.non_votants == 1
    assert len(s.positions_groupes) == 2
    assert s.positions_groupes[0].groupe_nom == "Rassemblement National"
    assert s.scrutin_public is True


def test_build_dossier_agrege_le_scrutin():
    resolver = build_resolver_from_organes(ORGANES)
    dossier = build_dossier([parse_scrutin(SCRUTIN, resolver)])
    assert dossier.id == "DLR5L17N53940"
    assert dossier.titre_clair.startswith("Projet de loi sur le logement")
    assert len(dossier.scrutins) == 1
    assert dossier.statut == StatutScrutin.rejete
    assert dossier.mise_a_jour is None
    # Sources : lien du scrutin + lien du dossier (texte).
    types = {src.type.value for src in dossier.sources}
    assert "scrutin" in types and "texte" in types


def test_resume_vide_non_comble():
    """Sans génération IA, le résumé du dossier reste vide + confiance faible (§2.5)."""
    resolver = build_resolver_from_organes(ORGANES)
    dossier = build_dossier([parse_scrutin(SCRUTIN, resolver)])
    assert dossier.resume.resume == []
    assert dossier.resume.confiance.value == "faible"
    assert "resume" in dossier.resume.champs_non_documentes


def test_mise_a_jour_quand_nouveau_scrutin():
    """Un nouveau scrutin rattaché à un dossier connu → badge « mis à jour » (§7.7)."""
    resolver = build_resolver_from_organes(ORGANES)
    prev = build_dossier([parse_scrutin(SCRUTIN, resolver)])

    parse2 = parse_scrutin(SCRUTIN, resolver)
    parse2.scrutin = parse2.scrutin.model_copy(
        update={"id": "VTANR5L17V1000", "date": "2026-07-05", "objet": "Vote sur l'ensemble"}
    )
    incoming = build_dossier([parse2])

    merged = _merge_avec_existant(prev, incoming)
    assert len(merged.scrutins) == 2
    assert merged.mise_a_jour is not None
    assert merged.mise_a_jour.date == "2026-07-05"
    assert merged.date_dernier_scrutin == "2026-07-05"


def test_pas_de_mise_a_jour_si_scrutin_deja_connu():
    resolver = build_resolver_from_organes(ORGANES)
    prev = build_dossier([parse_scrutin(SCRUTIN, resolver)])
    incoming = build_dossier([parse_scrutin(SCRUTIN, resolver)])
    merged = _merge_avec_existant(prev, incoming)
    assert len(merged.scrutins) == 1
    assert merged.mise_a_jour is None


def test_coherence_ok_quand_sommes_correspondent():
    resolver = build_resolver_from_organes(ORGANES)
    s = parse_scrutin(SCRUTIN, resolver).scrutin
    # pour: 0+21=21, contre: 10+29=39, abst: 0+4=4 → cohérent avec le global.
    assert controles_coherence(s) == []


def test_coherence_signale_incoherence():
    resolver = build_resolver_from_organes(ORGANES)
    s = parse_scrutin(SCRUTIN, resolver).scrutin
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
