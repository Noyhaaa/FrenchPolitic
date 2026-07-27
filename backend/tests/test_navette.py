"""Trajectoire d'un texte au Parlement (pur, sans réseau).

Les actes ci-dessous reprennent la structure réelle de `actesLegislatifs` dans
l'archive « dossiers législatifs » de l'Assemblée : des étapes de premier niveau
(`AN1`, `SN1`, `CMP`, `CC`…) dont la **décision** porte la date et le
`statutConclusion` officiel.
"""
from __future__ import annotations

from app.domain.enums import Chambre, StatutScrutin
from app.ingestion.navette import (
    phases_depuis_actes,
    phases_depuis_votes,
    trajectoire,
)
from app.schemas import ResultatGlobal, Scrutin


def _etape(code: str, label: str, date: str | None, conclusion: str | None) -> dict:
    decision: dict = {
        "codeActe": f"{code}-DEBATS-DEC",
        "libelleActe": {"nomCanonique": "Décision"},
        "dateActe": f"{date}T00:00:00.000+02:00" if date else None,
    }
    if conclusion is not None:
        decision["statutConclusion"] = {"libelle": conclusion}
    return {
        "@xsi:type": "Etape_Type",
        "codeActe": code,
        "libelleActe": {"nomCanonique": label},
        "dateActe": None,
        "actesLegislatifs": {"acteLegislatif": [decision]},
    }


# Cas réel : texte déposé à l'Assemblée, transmis au Sénat, puis CMP puis
# Conseil constitutionnel (« Projet de loi d'urgence… agricoles »).
_ACTES = {
    "acteLegislatif": [
        _etape("AN1", "1ère lecture (1ère assemblée saisie)", "2026-06-02", "adopté"),
        _etape("SN1", "1ère lecture (2ème assemblée saisie)", "2026-07-02", "modifié"),
        _etape("CMP", "Commission Mixte Paritaire", "2026-07-17", "Accord"),
        _etape("CC", "Conseil constitutionnel", "2026-07-24", "Conforme"),
    ]
}


def _scrutin(
    identifiant: str, date: str, objet: str, statut: str, chambre: str
) -> Scrutin:
    return Scrutin(
        id=identifiant,
        dossier_id="d1",
        date=date,
        objet=objet,
        statut=statut,
        chambre=chambre,
        scrutin_public=True,
        resultat=ResultatGlobal(pour=1, contre=0, abstention=0, non_votants=0),
    )


# --------------------------------------------------------------------------
# Voie 1 : les actes législatifs officiels
# --------------------------------------------------------------------------


def test_trajectoire_bicamerale_dans_l_ordre_officiel():
    """La frise couvre les DEUX chambres — ce qu'aucun scrutin ne documente."""
    phases = phases_depuis_actes(_ACTES)
    assert [p.label for p in phases] == [
        "1ère lecture (1ère assemblée saisie)",
        "1ère lecture (2ème assemblée saisie)",
        "Commission Mixte Paritaire",
        "Conseil constitutionnel",
    ]
    assert [p.chambre for p in phases] == [
        Chambre.assemblee,
        Chambre.senat,
        None,  # la CMP réunit les deux assemblées
        None,  # le Conseil constitutionnel est hors Parlement
    ]
    assert [p.date for p in phases] == [
        "2026-06-02",
        "2026-07-02",
        "2026-07-17",
        "2026-07-24",
    ]


def test_statuts_depuis_le_vocabulaire_officiel():
    phases = {p.label: p for p in phases_depuis_actes(_ACTES)}
    assert phases["1ère lecture (1ère assemblée saisie)"].statut is StatutScrutin.adopte
    # « modifié » = la chambre a adopté le texte en le modifiant : la navette
    # continue, ce n'est pas un rejet.
    assert phases["1ère lecture (2ème assemblée saisie)"].statut is StatutScrutin.adopte
    assert phases["Commission Mixte Paritaire"].statut is StatutScrutin.adopte
    # « Conforme » n'est ni une adoption ni un rejet du texte : pas de statut
    # plutôt qu'un rangement au jugé (§2.5).
    assert phases["Conseil constitutionnel"].statut is None


def test_rejet_et_desaccord():
    actes = {
        "acteLegislatif": [
            _etape("AN1", "1ère lecture", "2026-01-10", "rejeté"),
            _etape("CMP", "Commission Mixte Paritaire", "2026-02-01", "Désaccord"),
        ]
    }
    assert [p.statut for p in phases_depuis_actes(actes)] == [
        StatutScrutin.rejete,
        StatutScrutin.rejete,
    ]


def test_formules_circonstanciees():
    """Le vocabulaire de l'archive est parfois long : « rejet » l'emporte sur
    « adopté » dans les formules qui contiennent les deux."""
    actes = {
        "acteLegislatif": [
            _etape(
                "CMP",
                "Commission Mixte Paritaire",
                "2026-03-01",
                "adoptée, dans les conditions prévues à l'article 45, alinéa 3, "
                "de la Constitution",
            ),
            _etape(
                "ANNLEC",
                "Nouvelle Lecture",
                "2026-03-05",
                "considéré comme rejeté par l'Assemblée nationale en application "
                "de l'article 49, alinéa 3 de la Constitution",
            ),
            _etape(
                "ANLUNI",
                "Lecture unique",
                "2026-03-10",
                "considérée comme définitive en application de l'article 151-7 "
                "du Règlement",
            ),
        ]
    }
    assert [p.statut for p in phases_depuis_actes(actes)] == [
        StatutScrutin.adopte,
        StatutScrutin.rejete,
        StatutScrutin.adopte,
    ]


def test_statut_inconnu_laisse_l_etape_sans_statut():
    actes = {"acteLegislatif": [_etape("AN1", "1ère lecture", "2026-01-10", "?????")]}
    phases = phases_depuis_actes(actes)
    assert len(phases) == 1
    assert phases[0].statut is None
    assert phases[0].date == "2026-01-10"


def test_etape_sans_decision_garde_sa_date_de_debut():
    """Une étape en cours n'a pas de conclusion : on affiche sa date, pas un
    statut deviné (§2.5)."""
    actes = {"acteLegislatif": [_etape("SN1", "1ère lecture", "2026-06-03", None)]}
    phases = phases_depuis_actes(actes)
    assert phases[0].statut is None
    assert phases[0].date == "2026-06-03"


def test_actes_hors_navette_ecartes():
    """« Travaux », « Débat » et « Mise en application de la loi » ne décrivent
    pas le parcours du texte : ils encombreraient la frise."""
    actes = {
        "acteLegislatif": [
            _etape("AN20", "Travaux", "2026-01-01", None),
            _etape("AN21", "Débat", "2026-01-02", None),
            _etape("AN-APPLI", "Mise en application de la loi", "2026-09-01", None),
            _etape("AN1", "1ère lecture", "2026-01-10", "adopté"),
            _etape("PROM", "Promulgation de la loi", "2026-08-01", None),
        ]
    }
    assert [p.label for p in phases_depuis_actes(actes)] == [
        "1ère lecture",
        "Promulgation de la loi",
    ]


def test_actes_absents_ou_illisibles():
    assert phases_depuis_actes(None) == []
    assert phases_depuis_actes({}) == []
    assert phases_depuis_actes(["pas un acte"]) == []


def test_acte_unique_serialise_en_objet():
    """L'open data sérialise « 1 élément » comme objet, « n » comme liste."""
    actes = {"acteLegislatif": _etape("AN1", "1ère lecture", "2026-01-10", "adopté")}
    assert len(phases_depuis_actes(actes)) == 1


# --------------------------------------------------------------------------
# Voie 2 : repli sur les mentions portées par les objets de vote
# --------------------------------------------------------------------------


def test_repli_distingue_les_deux_chambres():
    """« Première lecture » à l'Assemblée et au Sénat sont DEUX étapes.

    Sans la chambre dans la clé, les deux fusionneraient en une seule et la
    frise laisserait croire que le texte n'a été lu qu'une fois.
    """
    votes = [
        _scrutin(
            "a1",
            "2026-01-10",
            "l'ensemble du projet de loi (première lecture)",
            "adopte",
            "assemblee",
        ),
        _scrutin(
            "s1",
            "2026-02-20",
            "l'ensemble du projet de loi (première lecture)",
            "rejete",
            "senat",
        ),
    ]
    phases = phases_depuis_votes(votes)
    assert [(p.label, p.chambre, p.statut) for p in phases] == [
        ("Première lecture", Chambre.assemblee, StatutScrutin.adopte),
        ("Première lecture", Chambre.senat, StatutScrutin.rejete),
    ]


def test_repli_statut_du_seul_vote_sur_l_ensemble():
    """Un vote d'article ne conclut pas une phase : il la documente sans statut."""
    votes = [
        _scrutin(
            "a1", "2026-01-10", "l'article 2 du projet de loi (première lecture)",
            "adopte", "assemblee",
        ),
    ]
    phases = phases_depuis_votes(votes)
    assert len(phases) == 1
    assert phases[0].statut is None
    assert phases[0].date == "2026-01-10"


def test_repli_ordre_chronologique():
    votes = [
        _scrutin(
            "c", "2026-05-01", "l'ensemble du texte (lecture définitive)",
            "adopte", "assemblee",
        ),
        _scrutin(
            "a", "2026-01-10", "l'ensemble du texte (première lecture)",
            "adopte", "assemblee",
        ),
        _scrutin(
            "b", "2026-03-01", "l'ensemble du texte (nouvelle lecture)",
            "adopte", "assemblee",
        ),
    ]
    assert [p.label for p in phases_depuis_votes(votes)] == [
        "Première lecture",
        "Nouvelle lecture",
        "Lecture définitive",
    ]


def test_aucune_mention_de_navette_aucune_phase():
    votes = [_scrutin("a", "2026-01-10", "l'ensemble du texte", "adopte", "assemblee")]
    assert phases_depuis_votes(votes) == []


# --------------------------------------------------------------------------
# Arbitrage entre les deux voies
# --------------------------------------------------------------------------


def test_les_actes_officiels_priment_sur_les_objets_de_vote():
    votes = [
        _scrutin(
            "a1", "2026-01-10", "l'ensemble du texte (première lecture)",
            "adopte", "assemblee",
        )
    ]
    phases = trajectoire(_ACTES, votes)
    assert len(phases) == 4
    assert phases[1].chambre is Chambre.senat


def test_repli_quand_le_dossier_n_a_pas_d_actes():
    """Dossiers reconstitués (« TXT-… ») et d'origine sénatoriale (« SEN-… »)."""
    votes = [
        _scrutin(
            "s1", "2026-02-20", "l'ensemble du texte (première lecture)",
            "adopte", "senat",
        )
    ]
    phases = trajectoire(None, votes)
    assert [(p.label, p.chambre) for p in phases] == [
        ("Première lecture", Chambre.senat)
    ]


def test_ni_actes_ni_mentions_frise_masquee():
    assert trajectoire(None, []) == []
