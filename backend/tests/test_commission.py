"""Amendements de commission : seul le décompte de la commission saisie AU FOND,
nommée, est restitué (§2.5)."""
from __future__ import annotations

import io
import json
import zipfile

from app.ingestion.amendements import lire_archive
from app.ingestion.commission import (
    amendements_commission,
    commissions_au_fond,
    noms_commissions,
    organe_examen,
    organes_par_abreviation,
)
from app.schemas import AmendementsCommission

ACTES = {
    "acteLegislatif": [
        {
            "codeActe": "AN1",
            "actesLegislatifs": {
                "acteLegislatif": [
                    {"codeActe": "AN1-COM-FOND-SAISIE", "organeRef": "PO420120"},
                    {"codeActe": "AN1-COM-AVIS-SAISIE", "organeRef": "PO59048"},
                ]
            },
        },
        {"codeActe": "SN1-COM-FOND-SAISIE", "organeRef": "PO211493"},
        {
            "codeActe": "AN2",
            "actesLegislatifs": {
                "acteLegislatif": {"codeActe": "AN2-COM-FOND-SAISIE", "organeRef": "PO420120"}
            },
        },
    ]
}


def test_commissions_au_fond_assemblee_seule_sans_doublon():
    # Ni la commission pour avis, ni celle du Sénat ; la 2e lecture ne
    # duplique pas la commission déjà vue.
    assert commissions_au_fond(ACTES) == ["PO420120"]
    assert commissions_au_fond(None) == []


def test_organe_examen():
    assert organe_examen("EXANR5L17PO420120B2851P0D1") == "PO420120"
    assert organe_examen(None) is None
    assert organe_examen("autre") is None


def test_noms_commissions_complete_sans_ecraser():
    du_jour = [{"organe": {"uid": "PO420120", "codeType": "COMPER",
                           "libelle": "Commission des affaires sociales"}}]
    historique = [
        {"organe": {"uid": "PO420120", "codeType": "COMPER", "libelle": "Ancien libellé"}},
        {"organe": {"uid": "PO849474", "codeType": "CNPS",
                    "libelle": "Commission spéciale sur la simplification"}},
        {"organe": {"uid": "PO845401", "codeType": "GP", "libelle": "Un groupe"}},
    ]
    assert noms_commissions(du_jour, historique) == {
        "PO420120": "Commission des affaires sociales",
        "PO849474": "Commission spéciale sur la simplification",
    }


def test_amendements_commission_au_fond_et_nommee():
    noms = {"PO420120": "Commission des affaires sociales"}
    par_cle = {
        ("CION-SOC", "PO420120"): [12, 30],
        ("CION_FIN", "PO59048"): [4, 1],
        (None, "PO999"): [3, 3],
    }
    # Pour avis (PO59048) : hors décompte. Commission sans nom : jamais un `PO…`.
    assert amendements_commission(par_cle, ["PO420120", "PO999"], noms) == [
        AmendementsCommission(
            commission="Commission des affaires sociales", adoptes=12, rejetes=30
        )
    ]
    assert amendements_commission(None, ["PO420120"], noms) == []


def test_le_prefixe_prime_sur_un_examenref_contradictoire():
    # Vécu : commission spéciale « simplification de la vie économique »,
    # préfixe CSVIEECO (confirmé par l'acte de saisine), `examenRef` vers les
    # affaires économiques sur ses 1 487 amendements.
    par_abreviation = organes_par_abreviation(
        [{"organe": {"uid": "PO849474", "codeType": "CNPS", "libelleAbrev": "CSVIEECO"}},
         {"organe": {"uid": "PO419610", "codeType": "COMPER", "libelleAbrev": "CION-ECO"}}]
    )
    noms = {"PO849474": "Commission spéciale simplification"}
    par_cle = {("CSVIEECO", "PO419610"): [350, 245]}
    assert amendements_commission(par_cle, ["PO849474"], noms, par_abreviation) == [
        AmendementsCommission(
            commission="Commission spéciale simplification", adoptes=350, rejetes=245
        )
    ]
    # Sans annuaire des abréviations, on retombe sur `examenRef` : non attribué.
    assert amendements_commission(par_cle, ["PO849474"], noms) == []


def test_abreviation_ambigue_ecartee():
    deux = [{"organe": {"uid": u, "codeType": "COMPER", "libelleAbrev": "X"}}
            for u in ("PO1", "PO2")]
    assert organes_par_abreviation(deux) == {}


def _archive(*amendements: tuple[str, dict]) -> zipfile.ZipFile:
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, "w") as zf:
        for i, (ref, amendement) in enumerate(amendements):
            zf.writestr(f"json/{ref}/T/A{i}.json", json.dumps({"amendement": amendement}))
    return zipfile.ZipFile(tampon)


def test_lire_archive_compte_les_amendements_tranches_en_commission():
    def amdt(sort: str) -> dict:
        return {
            "uid": f"U-{sort}",
            "identification": {"prefixeOrganeExamen": "CION-SOC", "numeroLong": "AS2"},
            "examenRef": "EXANR5L17PO420120B2851P0D1",
            "cycleDeVie": {"sort": sort},
        }

    archive = lire_archive(
        _archive(
            ("DLR5L17N1", amdt("Adopté")),
            ("DLR5L17N1", amdt("Rejeté")),
            ("DLR5L17N1", amdt("Retiré")),  # pas mis aux voix : ignoré
        )
    )
    assert archive.commission["DLR5L17N1"][("CION-SOC", "PO420120")] == [1, 1]
    # Un amendement de commission n'entre ni dans l'index ni dans la séance.
    assert archive.seance == [] and archive.index == {}
