"""Trajectoire d'un texte au Parlement (pur, sans réseau).

Les actes ci-dessous reprennent la structure réelle de `actesLegislatifs` dans
l'archive « dossiers législatifs » de l'Assemblée : des étapes de premier niveau
(`AN1`, `SN1`, `CMP`, `CC`…) dont la **décision** porte la date et le
`statutConclusion` officiel.
"""
from __future__ import annotations

from app.domain.enums import Chambre, StatutScrutin
from app.ingestion.navette import (
    etat_du_texte,
    phases_depuis_actes,
    phases_depuis_votes,
    source_legifrance,
    trajectoire,
)
from app.schemas import EtatTexte, ResultatGlobal, Scrutin


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


# --------------------------------------------------------------------------
# Où en est le texte aujourd'hui — la clôture de la frise
# --------------------------------------------------------------------------


def _promulgation(date: str, code_loi: str) -> dict:
    """Étape « Promulgation de la loi », telle que l'archive la sérialise :
    l'étape elle-même est vide, tout vit dans son acte `PROM-PUB`."""
    return {
        "@xsi:type": "Etape_Type",
        "codeActe": "PROM",
        "libelleActe": {"nomCanonique": "Promulgation de la loi"},
        "dateActe": None,
        "actesLegislatifs": {
            "acteLegislatif": {
                "@xsi:type": "Promulgation_Type",
                "codeActe": "PROM-PUB",
                "libelleActe": {"nomCanonique": "Promulgation d'une loi"},
                "dateActe": f"{date}T00:00:00.000+02:00",
                "codeLoi": code_loi,
                "infoJO": {
                    "dateJO": "2026-07-14+02:00",
                    "numJO": "163",
                    "urlLegifrance": (
                        "http://www.legifrance.gouv.fr/WAspad/UnTexteDeJorf"
                        "?numjo=JUSF2534988L"
                    ),
                    "referenceNOR": "JUSF2534988L",
                },
            }
        },
    }


def _etape_avec(code: str, label: str, enfants: list[dict]) -> dict:
    return {
        "@xsi:type": "Etape_Type",
        "codeActe": code,
        "libelleActe": {"nomCanonique": label},
        "dateActe": None,
        "actesLegislatifs": {"acteLegislatif": enfants},
    }


def _retrait(date: str) -> dict:
    return {
        "@xsi:type": "RetraitInitiative_Type",
        "codeActe": "AN1-RTRINI",
        "libelleActe": {"nomCanonique": "Retrait d'une initiative"},
        "dateActe": f"{date}T00:00:00.000+02:00",
        "actesLegislatifs": None,
    }


def test_loi_promulguee_porte_sa_reference_complete():
    """Le fait le plus important d'une fiche, et le seul lien de l'app vers le
    texte en vigueur (§7.5). Les quatre champs viennent de la source."""
    actes = {
        "acteLegislatif": [
            _etape("AN1", "1ère lecture (1ère assemblée saisie)", "2025-12-11", "adopté"),
            _promulgation("2026-07-13", "2026-630"),
        ]
    }
    etat = etat_du_texte(actes)
    assert etat is not None
    assert etat.etat == "promulgue"
    assert etat.date == "2026-07-13"
    assert etat.numero_loi == "2026-630"
    assert etat.date_journal_officiel == "2026-07-14"
    assert etat.url_legifrance is not None
    source = source_legifrance(etat)
    assert source is not None and source.url == etat.url_legifrance


def test_retrait_dans_la_derniere_etape_conclut_le_texte():
    actes = {
        "acteLegislatif": [
            _etape_avec(
                "AN1",
                "1ère lecture (1ère assemblée saisie)",
                [_retrait("2025-06-26")],
            )
        ]
    }
    etat = etat_du_texte(actes)
    assert etat is not None
    assert etat.etat == "retire"
    assert etat.date == "2025-06-26"


def test_retrait_dans_une_etape_anterieure_ne_conclut_rien():
    """Le dossier a continué après : c'est la dernière étape qui dit où il en
    est, pas un retrait dépassé."""
    actes = {
        "acteLegislatif": [
            _etape_avec(
                "AN1",
                "1ère lecture (1ère assemblée saisie)",
                [_retrait("2025-06-26")],
            ),
            _etape("SN1", "1ère lecture (2ème assemblée saisie)", "2026-02-10", None),
        ]
    }
    etat = etat_du_texte(actes)
    assert etat is not None
    assert etat.etat == "en_navette"
    assert etat.chambre is Chambre.senat


def test_conseil_constitutionnel_saisi_sans_conclusion():
    """On dit qu'il est saisi et depuis quand. Jamais ce qu'il décidera."""
    actes = {
        "acteLegislatif": [
            _etape("AN1", "1ère lecture (1ère assemblée saisie)", "2026-05-02", "adopté"),
            _etape_avec(
                "CC",
                "Conseil constitutionnel",
                [
                    {
                        "codeActe": "CC-SAISIE-AN",
                        "libelleActe": {"nomCanonique": "Saisine"},
                        "dateActe": "2026-06-03T00:00:00.000+02:00",
                        "actesLegislatifs": None,
                    }
                ],
            ),
        ]
    }
    etat = etat_du_texte(actes)
    assert etat is not None
    assert etat.etat == "conseil_constitutionnel"
    assert etat.date == "2026-06-03"


def test_conseil_constitutionnel_ayant_conclu_nest_plus_cet_etat():
    actes = {
        "acteLegislatif": [
            _etape_avec(
                "CC",
                "Conseil constitutionnel",
                [
                    {
                        "codeActe": "CC-SAISIE-AN",
                        "libelleActe": {"nomCanonique": "Saisine"},
                        "dateActe": "2026-06-03T00:00:00.000+02:00",
                        "actesLegislatifs": None,
                    },
                    {
                        "codeActe": "CC-CONCLUSION",
                        "libelleActe": {"nomCanonique": "Décision"},
                        "dateActe": "2026-06-20T00:00:00.000+02:00",
                        "actesLegislatifs": None,
                    },
                ],
            )
        ]
    }
    etat = etat_du_texte(actes)
    assert etat is not None
    assert etat.etat != "conseil_constitutionnel"


def test_resolution_conclue_est_terminee_pas_en_navette():
    """Une résolution n'est ni transmise à l'autre chambre ni promulguée : la
    ranger « en cours d'examen » la ferait passer pour un texte en attente."""
    actes = {
        "acteLegislatif": [
            _etape("ANLUNI", "Lecture unique", "2024-10-09", "adoptée")
        ]
    }
    etat = etat_du_texte(actes, {"code": "22", "libelle": "Résolution Article 34-1"})
    assert etat is not None
    assert etat.etat == "resolution"
    assert etat.statut is StatutScrutin.adopte
    assert etat.date == "2024-10-09"


def test_meme_etape_sans_procedure_de_resolution_reste_en_navette():
    """Le code de procédure est le seul indice retenu — on ne devine pas la
    nature du texte à partir du libellé de son étape (§2.5)."""
    actes = {
        "acteLegislatif": [
            _etape("ANLUNI", "Lecture unique", "2024-10-09", "adoptée")
        ]
    }
    etat = etat_du_texte(actes, {"code": "1", "libelle": "Projet de loi ordinaire"})
    assert etat is not None
    assert etat.etat == "en_navette"


def test_texte_en_navette_donne_sa_derniere_etape_enregistree():
    etat = etat_du_texte(_ACTES)
    assert etat is not None
    # _ACTES se termine par le Conseil constitutionnel « Conforme » — un avis
    # qui n'est ni adoption ni rejet, mais bien une conclusion publiée.
    assert etat.etat == "en_navette"
    assert etat.etape == "Conseil constitutionnel"


def test_dossier_sans_actes_na_pas_d_etat():
    """« TXT-… », « SEN-… », motions : le bloc disparaît (§2.5)."""
    assert etat_du_texte(None) is None
    assert etat_du_texte({"acteLegislatif": []}) is None
    assert source_legifrance(None) is None


def test_aucun_etat_ne_decrit_une_etape_a_venir():
    """Garde-fou de doctrine : le calendrier parlementaire est une décision
    politique, pas une donnée. Aucun champ ne peut annoncer la suite — s'il en
    apparaissait un, ce test le signalerait."""
    champs = set(EtatTexte.model_fields)
    assert champs == {
        "etat",
        "date",
        "etape",
        "chambre",
        "statut",
        "numero_loi",
        "date_journal_officiel",
        "url_legifrance",
    }
    etat = etat_du_texte(_ACTES)
    assert etat is not None
    # Rien de ce qu'on sérialise ne parle du futur.
    rendu = " ".join(str(v) for v in etat.model_dump().values() if v)
    assert "prochain" not in rendu.lower()
