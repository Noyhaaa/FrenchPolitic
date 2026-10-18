"""Rattachement d'un vote au dossier qui siégeait ce jour-là (`rattacher_par_seances`)."""
from __future__ import annotations

from app.domain.enums import Chambre, StatutScrutin
from app.ingestion.assemblee import ScrutinParse
from app.ingestion.decisions import (
    TitresDossiers,
    _mots,
    rattacher_par_seances,
    seances_par_jour,
)
from app.schemas import ResultatGlobal, Scrutin


def _parse(uid, jour, dossier_id, titre, ref=None, titre_cite=None):
    scrutin = Scrutin(
        id=uid,
        dossier_id=dossier_id,
        date=jour,
        objet="l'amendement n° 1 à l'article premier",
        statut=StatutScrutin.adopte,
        chambre=Chambre.assemblee,
        scrutin_public=True,
        resultat=ResultatGlobal(pour=10, contre=2, abstention=0, non_votants=0),
    )
    return ScrutinParse(
        scrutin=scrutin,
        dossier_id=dossier_id,
        dossier_titre=titre,
        dossier_ref=ref,
        theme="Autre",
        legislature="17",
        numero="1",
        titre_cite=titre_cite,
    )


def _titres(**par_ref: str) -> TitresDossiers:
    return TitresDossiers(
        titre=dict(par_ref),
        mots={ref: frozenset(_mots(t)) for ref, t in par_ref.items()},
        url_senat={},
    )


URBANISME = "Proposition de loi de simplification du droit de l'urbanisme et du logement"
AGRICOLE = "Projet de loi d'urgence pour la protection et la souveraineté agricoles"
CALEDONIE = "Proposition de loi organique portant actualisation du corps électoral"


def test_seances_par_jour_ne_garde_que_les_seances_de_l_assemblee():
    actes = {
        "D1": {"acteLegislatif": [
            {"codeActe": "AN1-DEBATS-SEANCE", "dateActe": "2025-05-15T00:00:00.000+02:00"},
            {"codeActe": "SN1-DEBATS-SEANCE", "dateActe": "2025-06-01T00:00:00.000+02:00"},
            {"codeActe": "AN1-DEPOT", "dateActe": "2025-04-01T00:00:00.000+02:00"},
        ]}
    }
    assert seances_par_jour(actes) == {"2025-05-15": frozenset({"D1"})}


def test_coquille_de_la_source_rattrapee_par_la_seance_du_jour():
    # Vécu : « ssimplification » dans l'objet du scrutin.
    p = _parse("V1", "2025-05-15", "TXT-1", "Proposition de loi de ssimplification du droit de l'urbanisme et du logement")
    seances = {"2025-05-15": frozenset({"D_URB", "D_AUTRE"})}
    titres = _titres(D_URB=URBANISME, D_AUTRE="Lutter contre la mortalité infantile")
    assert rattacher_par_seances([p], seances, titres) == 1
    assert (p.dossier_id, p.dossier_ref, p.scrutin.dossier_id) == ("D_URB", "D_URB", "D_URB")


def test_sans_seance_ce_jour_la_rien_ne_bouge():
    p = _parse("V1", "2025-05-16", "TXT-1", URBANISME)
    assert rattacher_par_seances([p], {"2025-05-15": frozenset({"D_URB"})}, _titres(D_URB=URBANISME)) == 0
    assert p.dossier_id == "TXT-1"


def test_deux_dossiers_concordants_le_meme_jour_rien_ne_bouge():
    p = _parse("V1", "2025-05-15", "TXT-1", URBANISME)
    seances = {"2025-05-15": frozenset({"D1", "D2"})}
    assert rattacher_par_seances([p], seances, _titres(D1=URBANISME, D2=URBANISME)) == 0
    assert p.dossier_id == "TXT-1"


def test_dossierref_contredit_par_le_titre_cite():
    # Vécu : un amendement au projet de loi agricole publié sous le dossierRef
    # du corps électoral de Nouvelle-Calédonie, le jour où les deux siégeaient.
    p = _parse("V6758", "2026-05-20", "D_NC", CALEDONIE, ref="D_NC", titre_cite=AGRICOLE)
    seances = {"2026-05-20": frozenset({"D_NC", "D_AGRI"})}
    titres = _titres(D_NC=CALEDONIE, D_AGRI=AGRICOLE)
    assert rattacher_par_seances([p], seances, titres) == 1
    assert p.dossier_id == "D_AGRI"


def test_un_vote_cite_par_les_actes_ne_bouge_jamais():
    p = _parse("V6758", "2026-05-20", "D_NC", CALEDONIE, ref="D_NC", titre_cite=AGRICOLE)
    seances = {"2026-05-20": frozenset({"D_NC", "D_AGRI"})}
    titres = _titres(D_NC=CALEDONIE, D_AGRI=AGRICOLE)
    assert rattacher_par_seances([p], seances, titres, frozenset({"V6758"})) == 0
    assert p.dossier_id == "D_NC"


def test_dossierref_concordant_reste_en_place():
    p = _parse("V1", "2026-05-20", "D_AGRI", AGRICOLE, ref="D_AGRI", titre_cite=AGRICOLE)
    seances = {"2026-05-20": frozenset({"D_AGRI"})}
    assert rattacher_par_seances([p], seances, _titres(D_AGRI=AGRICOLE)) == 0
