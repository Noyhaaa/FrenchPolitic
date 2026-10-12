"""Décisions et amendements votés SANS scrutin public (§5.2).

Pur, sans réseau ni base. Les cas reproduisent ceux mesurés sur les archives de
la 17e législature : une convention adoptée sans scrutin dans les deux chambres,
une résolution européenne devenue définitive (art. 151-7), un 49.3, une
résolution dont le titre a changé en commission, des amendements identiques
tranchés par un seul scrutin.
"""
from __future__ import annotations

from app.domain.enums import Chambre, ModaliteVote, StatutScrutin
from app.ingestion.amendements import (
    AmendementEnrichi,
    AmendementSeance,
    ArchiveAmendements,
    amendements_sans_scrutin,
    objet_amendement_seance,
    parse_amendement_seance,
)
from app.ingestion.assemblee import ScrutinParse
from app.ingestion.decisions import (
    DecisionSeance,
    TitresDossiers,
    VotePublic,
    construire_titres,
    decisions_sans_scrutin,
    extraire_decisions,
    lire_conclusion,
    parse_decision,
    rattacher_par_decisions,
    titres_concordants,
)
from app.ai.questions import phrase_decision, phrase_resultat
from app.ingestion.sync import (
    _amendement_from_scrutin,
    _merge_avec_existant,
    build_dossier,
)
from app.schemas import DossierListItem, ResultatGlobal, Scrutin, ScrutinResume

_ZERO = ResultatGlobal(pour=0, contre=0, abstention=0, non_votants=0)


# --- Conclusions officielles -------------------------------------------------


def test_conclusion_liste_fermee():
    assert lire_conclusion("adopté sans modification") == (
        StatutScrutin.adopte,
        ModaliteVote.main_levee,
    )
    assert lire_conclusion("modifiée") == (StatutScrutin.adopte, ModaliteVote.main_levee)
    assert lire_conclusion(
        "adoptée, dans les conditions prévues à l'article 45, alinéa 3, de la Constitution"
    ) == (StatutScrutin.adopte, ModaliteVote.main_levee)
    assert lire_conclusion("rejetée") == (StatutScrutin.rejete, ModaliteVote.main_levee)
    assert lire_conclusion(
        "considérée comme définitive en application de l'article 151-7 du Règlement"
    ) == (StatutScrutin.adopte, ModaliteVote.article_151_7)
    assert lire_conclusion(
        "considéré comme adopté par l'Assemblée nationale en application de "
        "l'article 49, alinéa 3 de la Constitution"
    ) == (StatutScrutin.adopte, ModaliteVote.article_49_3)
    assert lire_conclusion(
        "considéré comme rejeté par l'Assemblée nationale en application de "
        "l'article 49, alinéa 3 de la Constitution"
    ) == (StatutScrutin.rejete, ModaliteVote.article_49_3)


def test_conclusion_inconnue_ne_produit_rien():
    # « rejet du texte par la commission préalable » n'est pas une décision de
    # séance qu'on sait raconter : rien plutôt qu'un sort deviné (§2.5).
    assert lire_conclusion("rejet du texte par la commission préalable") is None
    assert lire_conclusion("Conforme") is None
    assert lire_conclusion(None) is None
    assert lire_conclusion({"@xsi:nil": "true"}) is None


# --- Extraction des actes ------------------------------------------------------


def _acte(code, date, libelle=None, votes=None, uid=None, sous=None) -> dict:
    acte: dict = {
        "uid": uid or f"{code}-{date}",
        "codeActe": code,
        "dateActe": f"{date}T00:00:00.000+01:00",
        "libelleActe": {"nomCanonique": code},
    }
    if libelle:
        acte["statutConclusion"] = {"fam_code": "TSORTF", "libelle": libelle}
    if votes:
        acte["voteRefs"] = {"voteRef": votes[0] if len(votes) == 1 else votes}
    if sous:
        acte["actesLegislatifs"] = {"acteLegislatif": sous}
    return acte


def _etape(code, label, *sous) -> dict:
    return {
        "codeActe": code,
        "libelleActe": {"nomCanonique": label},
        "actesLegislatifs": {"acteLegislatif": list(sous)},
    }


def _dossier(uid, titre, *etapes, senat=None) -> dict:
    titres = {"titre": titre}
    if senat:
        titres["senatChemin"] = senat
    return {
        "dossierParlementaire": {
            "uid": uid,
            "titreDossier": titres,
            "actesLegislatifs": {"acteLegislatif": list(etapes)},
        }
    }


_CONVENTION = _dossier(
    "DLR5L17N51519",
    "Projet de loi autorisant l'approbation de l'accord entre la France et le Japon",
    _etape(
        "SN1",
        "1ère lecture (1ère assemblée saisie)",
        _acte("SN1-DEPOT", "2025-03-01"),
        _acte("SN1-COM-FOND-DEC", "2025-06-01", "adopté"),  # commission : écarté
        _etape("SN1-DEBATS", "Discussion", _acte("SN1-DEBATS-DEC", "2025-06-23", "adopté")),
    ),
    _etape(
        "AN1",
        "1ère lecture (2ème assemblée saisie)",
        _etape(
            "AN1-DEBATS",
            "Discussion",
            _acte("AN1-DEBATS-DEC", "2025-12-17", "adopté sans modification"),
        ),
    ),
    senat="http://www.senat.fr/dossier-legislatif/pjl24-500.html",
)


def test_extraire_decisions_des_deux_chambres():
    decisions = extraire_decisions([_CONVENTION], (17,), "2024-07-18")
    assert [(d.chambre, d.jour, d.etape, d.conclusion) for d in decisions] == [
        (Chambre.senat, "2025-06-23", "1ère lecture (1ère assemblée saisie)", "adopté"),
        (
            Chambre.assemblee,
            "2025-12-17",
            "1ère lecture (2ème assemblée saisie)",
            "adopté sans modification",
        ),
    ]


def test_extraire_decisions_ecarte_cmp_commission_et_anciennes():
    dossier = _dossier(
        "DLR5L17N1",
        "Titre",
        _etape(
            "CMP",
            "Commission Mixte Paritaire",
            _acte("CMP-DEC", "2025-01-10", "Accord"),  # la CMP n'est pas une chambre
            _acte("CMP-DEBATS-AN-DEC", "2025-01-15", "adopté"),
        ),
        _etape("AN1", "1ère lecture", _acte("AN1-DEBATS-DEC", "2024-06-01", "adopté")),
    )
    decisions = extraire_decisions([dossier], (17,), "2024-07-18")
    assert [(d.chambre, d.jour) for d in decisions] == [(Chambre.assemblee, "2025-01-15")]


def test_extraire_decisions_premiere_copie_gagne():
    # La copie de la législature courante passe avant l'instantané figé de la
    # précédente, et un dossier hors des législatures chargées est ignoré.
    courant = _dossier(
        "DLR5L16N9", "T", _etape("AN1", "L", _acte("AN1-DEBATS-DEC", "2025-02-01", "adopté"))
    )
    fige = _dossier(
        "DLR5L16N9", "T", _etape("AN1", "L", _acte("AN1-DEBATS-DEC", "2025-01-01", "rejeté"))
    )
    ancien = _dossier(
        "DLR5L15N1", "T", _etape("AN1", "L", _acte("AN1-DEBATS-DEC", "2025-02-01", "adopté"))
    )
    decisions = extraire_decisions([courant, fige, ancien], (17, 16), "2024-07-18")
    assert [(d.dossier_ref, d.jour) for d in decisions] == [("DLR5L16N9", "2025-02-01")]


# --- Ce qu'un scrutin public raconte déjà ---------------------------------------


def _decision(jour, chambre=Chambre.assemblee, modalite=ModaliteVote.main_levee, cites=(), ref="DLR5L17N1"):
    return DecisionSeance(
        uid=f"DEC-{ref}-{jour}-{chambre.value}",
        dossier_ref=ref,
        chambre=chambre,
        jour=jour,
        etape="1ère lecture",
        conclusion="adopté",
        statut=StatutScrutin.adopte,
        modalite=modalite,
        votes_cites=tuple(cites),
    )


def _vote(jour, objet="l'ensemble du projet de loi", chambre=Chambre.assemblee, ref="DLR5L17N1"):
    return VotePublic(ref, chambre, jour, objet)


def test_decision_couverte_par_son_scrutin():
    # Cité par l'acte, ou scrutin conclusif du même jour : le vote est déjà là.
    cite = _decision("2025-03-01", cites=["VTANR5L17V1"])
    meme_jour = _decision("2025-03-02")
    assert decisions_sans_scrutin([cite, meme_jour], [_vote("2025-03-02")]) == []


def test_un_vote_d_article_ne_couvre_pas_la_decision():
    # Article voté au scrutin public, ensemble à main levée : la décision reste.
    d = _decision("2025-03-02")
    article = _vote("2025-03-02", "l'article 2 du projet de loi")
    amendement = _vote("2025-03-02", "l'amendement n° 4 de M. X")
    autre_chambre = _vote("2025-03-02", chambre=Chambre.senat)
    assert decisions_sans_scrutin([d], [article, amendement, autre_chambre]) == [d]


def test_fenetre_de_deux_jours_sauf_autre_decision():
    d = _decision("2025-03-02")
    # Séance levée après minuit : le scrutin porte la veille.
    assert decisions_sans_scrutin([d], [_vote("2025-03-01")]) == []
    # …mais si la veille est le jour d'une AUTRE décision du dossier, le
    # scrutin est le sien, et celle-ci reste sans scrutin.
    veille = _decision("2025-03-01")
    assert decisions_sans_scrutin([d, veille], [_vote("2025-03-01")]) == [d]


def test_49_3_et_151_7_toujours_retenus():
    # Aucun vote n'a eu lieu sur le texte : un scrutin du jour (une motion de
    # censure, un article) ne les remplace pas.
    d493 = _decision("2025-02-03", modalite=ModaliteVote.article_49_3, cites=["VTA9"])
    d1517 = _decision("2025-02-05", modalite=ModaliteVote.article_151_7)
    assert decisions_sans_scrutin([d493, d1517], [_vote("2025-02-03")]) == [d493, d1517]


# --- Rattachement d'un dossier reconstitué -------------------------------------


def test_titres_concordants():
    mots = construire_titres(
        [_dossier("DLR5L17N51362", "Projet de loi autorisant la ratification de la résolution LP.3(4) portant amendement de l'article 6 du Protocole de Londres de 1996 à la Convention de 1972")],
        [],
    ).mots["DLR5L17N51362"]
    # Coquille de la source (1966 pour 1996) et titre tronqué : même texte.
    assert titres_concordants(
        "Projet de loi autorisant la ratification de la résolution LP.3 (4) portant "
        "amendement de l'article 6 du Protocole de Londres de 1966 à la Convention de 1972 su…",
        mots,
    )
    # Un autre accord voté le même jour : pas le même texte.
    assert not titres_concordants(
        "Projet de loi autorisant l'approbation de l'accord-cadre entre la France et "
        "les Nations unies relatif aux bureaux",
        mots,
    )
    # Trop peu de mots pour conclure.
    assert not titres_concordants("Projet de loi Londres", mots)


def _parse(uid, jour, objet, dossier_id, titre, ref=None, chambre=Chambre.assemblee):
    scrutin = Scrutin(
        id=uid,
        dossier_id=dossier_id,
        date=jour,
        objet=objet,
        statut=StatutScrutin.adopte,
        chambre=chambre,
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
    )


_MERCOSUR = (
    "Proposition de résolution européenne visant à refuser la ratification de "
    "l'accord commercial entre l'Union européenne et le Mercosur"
)


def _titres_mercosur() -> TitresDossiers:
    return construire_titres(
        [
            _dossier(
                "DLR5L17N50939",
                "Refuser la ratification de l'accord commercial entre l'Union européenne et le Mercosur",
            ),
            _dossier(
                "DLR5L17N50476",
                "Adoption et mise en œuvre d'exigences à l'importation pour les produits agricoles",
            ),
        ],
        [],
    )


def test_rattacher_un_dossier_reconstitue_par_sa_decision():
    parses = [
        _parse("V1", "2025-01-30", "l'article unique de la proposition de résolution", "TXT-1144", _MERCOSUR),
        _parse("V2", "2025-01-30", "l'amendement n° 7 de Mme Hamelet", "TXT-1144", _MERCOSUR),
    ]
    decisions = [
        _decision("2025-01-30", ref="DLR5L17N50939"),
        _decision("2025-01-30", ref="DLR5L17N50476"),  # même jour, autre texte
    ]
    assert rattacher_par_decisions(parses, decisions, _titres_mercosur(), []) == 2
    assert {(p.dossier_id, p.dossier_ref, p.scrutin.dossier_id) for p in parses} == {
        ("DLR5L17N50939", "DLR5L17N50939", "DLR5L17N50939")
    }


def test_rattachement_ambigu_ne_deplace_rien():
    # Deux dossiers reconstitués au titre concordant le même jour : on ne
    # choisit pas (§2.5).
    parses = [
        _parse("V1", "2025-01-30", "l'article unique de la proposition de résolution", "TXT-A", _MERCOSUR),
        _parse("V2", "2025-01-30", "l'ensemble de la proposition de résolution", "TXT-B", _MERCOSUR),
    ]
    decisions = [_decision("2025-01-30", ref="DLR5L17N50939")]
    assert rattacher_par_decisions(parses, decisions, _titres_mercosur(), []) == 0
    assert {p.dossier_id for p in parses} == {"TXT-A", "TXT-B"}


def test_rattachement_inutile_si_le_dossier_a_son_scrutin():
    parses = [
        _parse("V1", "2025-01-30", "l'article unique de la proposition de résolution", "TXT-1144", _MERCOSUR),
    ]
    decisions = [_decision("2025-01-30", ref="DLR5L17N50939")]
    deja = [_vote("2025-01-30", "l'ensemble de la proposition", ref="DLR5L17N50939")]
    assert rattacher_par_decisions(parses, decisions, _titres_mercosur(), deja) == 0


# --- Une décision devient un vote sans décompte --------------------------------


def test_parse_decision_sans_decompte_et_sourcee():
    titres = construire_titres([_CONVENTION], [])
    senat, an = extraire_decisions([_CONVENTION], (17,), "2024-07-18")
    p = parse_decision(senat, titres)
    assert p.scrutin.scrutin_public is False
    assert p.scrutin.modalite is ModaliteVote.main_levee
    assert p.scrutin.resultat == _ZERO and p.scrutin.positions_groupes == []
    assert p.scrutin.objet == "1ère lecture (1ère assemblée saisie) — adopté"
    assert p.dossier_titre.startswith("Projet de loi autorisant")
    # Où vérifier : la page du dossier dans la chambre qui a décidé.
    assert p.scrutin.sources[0].url == "http://www.senat.fr/dossier-legislatif/pjl24-500.html"
    assert parse_decision(an, titres).scrutin.sources[0].url.endswith(
        "/dyn/17/dossiers/DLR5L17N51519"
    )
    # Pas de titre : pas de dossier qu'on ne saurait nommer.
    assert parse_decision(an, TitresDossiers({}, {}, {})) is None


def test_phrases_de_resultat_sans_chiffre():
    adopte_senat = Scrutin(
        id="D1",
        dossier_id="DLR1",
        date="2025-06-23",
        objet="1ère lecture — adopté",
        statut=StatutScrutin.adopte,
        chambre=Chambre.senat,
        scrutin_public=False,
        modalite=ModaliteVote.main_levee,
        resultat=_ZERO,
    )
    assert phrase_decision(adopte_senat) == (
        "Le texte a été adopté au Sénat à main levée, sans scrutin public : il "
        "n'y a pas eu de décompte des voix."
    )
    rejet_493 = adopte_senat.model_copy(
        update={
            "chambre": Chambre.assemblee,
            "statut": StatutScrutin.rejete,
            "modalite": ModaliteVote.article_49_3,
        }
    )
    assert "une motion de censure a été adoptée" in phrase_decision(rejet_493)
    assert "0 voix" not in phrase_decision(rejet_493)
    # Q3 : la décision la plus récente tranche, même après un scrutin public
    # sur l'ensemble dans l'autre chambre.
    public = ScrutinResume(
        id="V1",
        date="2025-03-01",
        objet="l'ensemble du projet de loi",
        statut=StatutScrutin.adopte,
        scrutin_public=True,
        resultat=ResultatGlobal(pour=300, contre=200, abstention=0, non_votants=0),
    )
    assert phrase_resultat(
        [ScrutinResume.from_scrutin(adopte_senat), public]
    ).startswith("Le texte a été adopté au Sénat à main levée")


# --- Amendements votés à main levée ----------------------------------------------


def _amdt(numero, jour, adopte=True, ref="DLR5L17N1", identique=None, parent=None, uid=None, auteur="PA1", type_auteur="Député"):
    return AmendementSeance(
        uid=uid or f"AMANR5L17PO1B1P0D1N{int(numero):06d}",
        dossier_ref=ref,
        numero=str(numero),
        adopte=adopte,
        jour=jour,
        type_auteur=type_auteur,
        acteur_ref=auteur,
        parent_uid=parent,
        discussion_identique=identique,
        contenu=AmendementEnrichi(
            dispositif="Supprimer cet article.",
            expose_sommaire="Cet amendement vise à supprimer l'article.",
            cible="Article 2",
            date_sort=None,
        ),
    )


def test_amendement_couvert_par_son_scrutin_public():
    publics = [
        ("DLR5L17N1", "2025-03-03", "l'amendement n° 12 de M. X à l'article 2"),
        # Amendements identiques : le scrutin n'en cite qu'un…
        ("DLR5L17N1", "2025-03-03", "l'amendement n° 20 du Gouvernement et les amendements identiques suivants"),
        # …ou les cite tous.
        ("DLR5L17N1", "2025-03-03", "les amendements identiques n° 30 et n° 31"),
    ]
    seance = [
        _amdt(12, "2025-03-04"),               # sort le lendemain (minuit passé)
        _amdt(20, "2025-03-03", identique="G1"),
        _amdt(21, "2025-03-03", identique="G1"),  # identique au n° 20 : couvert
        _amdt(30, "2025-03-03"),
        _amdt(31, "2025-03-03"),
        _amdt(40, "2025-03-03"),               # aucun scrutin : main levée
        _amdt(12, "2026-01-10"),               # n° 12 d'une autre lecture
    ]
    restants = amendements_sans_scrutin(seance, publics, "2024-07-18")
    assert [(a.numero, a.jour) for a in restants] == [("40", "2025-03-03"), ("12", "2026-01-10")]


def test_amendement_au_scrutin_dans_un_dossier_reconstitue_reste_couvert():
    # Le scrutin vit dans un `TXT-…` : dans le doute, ce n'est pas « main levée ».
    publics = [("TXT-abc", "2025-03-03", "l'amendement n° 7 de Mme Y")]
    assert amendements_sans_scrutin([_amdt(7, "2025-03-03")], publics, "2024-07-18") == []


def test_objet_amendement_comme_l_assemblee_l_ecrit():
    civ = {"PA1": "M. Girard"}
    assert objet_amendement_seance(_amdt(9, "2025-01-01"), None, civ) == (
        "l'amendement n° 9 de M. Girard"
    )
    gouv = _amdt(5, "2025-01-01", type_auteur="Gouvernement", auteur=None)
    assert objet_amendement_seance(gouv, None, civ) == "l'amendement n° 5 du Gouvernement"
    inconnu = _amdt(6, "2025-01-01", auteur="PA999")
    assert objet_amendement_seance(inconnu, None, civ) == "l'amendement n° 6"
    sous = _amdt(12, "2025-01-01", parent="AMX")
    assert objet_amendement_seance(sous, "80", civ) == (
        "le sous-amendement n° 12 de M. Girard à l'amendement n° 80"
    )


def test_amendement_main_levee_dans_le_dossier():
    parent = _amdt(80, "2025-03-03", uid="AMANR5L17PARENT")
    sous = _amdt(12, "2025-03-03", parent="AMANR5L17PARENT", adopte=False)
    # Même numéro 80, autre lecture : le numéro seul tromperait.
    homonyme = _amdt(80, "2025-01-10", uid="AMANR5L17HOMONYME")
    archive = ArchiveAmendements(
        index={}, seance=[], numero_par_uid={"AMANR5L17PARENT": "80"}
    )
    civ = {"PA1": "M. Girard"}
    parses = [
        parse_amendement_seance(a, archive, "Titre du dossier", civ)
        for a in (parent, sous, homonyme)
    ]
    assert parses[0].scrutin.sources[0].url == (
        "https://www.assemblee-nationale.fr/dyn/17/amendements/AMANR5L17PARENT"
    )
    dossier = build_dossier(parses)
    amendements = {a.id: a for a in dossier.amendements}
    assert set(amendements) == {"AMANR5L17PARENT", "AMANR5L17HOMONYME"}
    racine = amendements["AMANR5L17PARENT"]
    assert [sa.id for sa in racine.sous_amendements] == [sous.uid]
    assert racine.modalite is ModaliteVote.main_levee
    assert racine.auteur == "M. Girard"
    assert racine.dispositif == "Supprimer cet article." and racine.cible == "Article 2"
    # Seuls des amendements : le texte n'a pas (encore) été voté.
    assert dossier.statut is StatutScrutin.en_cours
    assert dossier.scrutins == []


def test_contenu_d_un_vote_main_levee_n_est_pas_apparie_a_l_index():
    # L'index pourrait porter un autre n° 9 du même dossier (autre lecture) :
    # le vote apporte son propre contenu, on ne le remplace pas.
    archive = ArchiveAmendements(index={}, seance=[], numero_par_uid={})
    scrutin = parse_amendement_seance(
        _amdt(9, "2025-03-03"), archive, "Titre", {"PA1": "M. Girard"}
    ).scrutin
    index = {
        (scrutin.dossier_id, "9"): [
            AmendementEnrichi("AUTRE", "AUTRE", "Article 9", None)
        ]
    }
    a = _amendement_from_scrutin(scrutin, index)
    assert a.dispositif == "Supprimer cet article."
    assert a.sort == "adopte"


# --- Le dossier : statut, carte, badge « nouveau vote » --------------------------


def _scrutin(uid, jour, objet, statut="adopte", public=True, modalite=None, chambre=Chambre.assemblee):
    return Scrutin(
        id=uid,
        dossier_id="DLR5L17N1",
        date=jour,
        objet=objet,
        statut=statut,
        chambre=chambre,
        scrutin_public=public,
        modalite=modalite,
        resultat=ResultatGlobal(pour=300, contre=200, abstention=0, non_votants=0)
        if public
        else _ZERO,
    )


def _p(scrutin: Scrutin, titre="Titre public") -> ScrutinParse:
    return ScrutinParse(
        scrutin=scrutin,
        dossier_id=scrutin.dossier_id,
        dossier_titre=titre,
        dossier_ref=scrutin.dossier_id,
        theme="Autre",
        legislature="17",
        numero="1",
    )


def test_statut_du_dernier_vote_sur_le_texte():
    ensemble = _scrutin("V1", "2025-03-03", "l'ensemble du projet de loi")
    amdt_meme_jour = _scrutin("V2", "2025-03-03", "l'amendement n° 4 de M. X", statut="rejete")
    d = build_dossier([_p(amdt_meme_jour), _p(ensemble)])
    assert d.statut is StatutScrutin.adopte
    # Un amendement voté APRÈS : l'examen a repris, le texte est en discussion.
    amdt_apres = _scrutin("V3", "2025-10-01", "l'amendement n° 9 de M. Y")
    d = build_dossier([_p(amdt_apres), _p(ensemble)])
    assert d.statut is StatutScrutin.en_cours
    assert d.date_dernier_scrutin == "2025-10-01"


def test_decision_sans_scrutin_ne_change_pas_le_titre_du_dossier():
    public = _p(_scrutin("V1", "2025-03-03", "l'ensemble du projet de loi"), "Titre des votes")
    decision = _p(
        _scrutin(
            "D1",
            "2025-06-23",
            "1ère lecture — adopté",
            public=False,
            modalite=ModaliteVote.main_levee,
            chambre=Chambre.senat,
        ),
        "Titre de l'archive",
    )
    d = build_dossier([decision, public])
    assert d.titre_officiel == "Titre des votes"
    assert d.statut is StatutScrutin.adopte
    # La carte résume le DERNIER vote : sans décompte, elle dit comment il a
    # été pris plutôt que d'afficher les voix d'un vote plus ancien.
    item = DossierListItem.from_dossier(d)
    assert item.resultat_dernier_scrutin is None
    assert item.modalite_dernier_scrutin is ModaliteVote.main_levee
    assert item.chambres == [Chambre.assemblee, Chambre.senat]


def test_vote_ancien_decouvert_n_est_pas_un_nouveau_vote():
    ensemble = _scrutin("V1", "2025-03-03", "l'ensemble du projet de loi")
    prev = build_dossier([_p(ensemble)])
    ancien = _scrutin(
        "AM1", "2025-03-02", "l'amendement n° 4 de M. X", public=False,
        modalite=ModaliteVote.main_levee,
    )
    fusion = _merge_avec_existant(
        prev,
        build_dossier([_p(ensemble), _p(ancien)]),
        dates_sans_scrutin={"AM1": "2025-03-02"},
    )
    assert fusion.mise_a_jour is None
    assert [a.id for a in fusion.amendements] == ["AM1"]
    # Une décision postérieure au dernier vote connu, elle, est un événement.
    decision = _scrutin(
        "D1", "2025-06-23", "1ère lecture — adopté", public=False,
        modalite=ModaliteVote.main_levee, chambre=Chambre.senat,
    )
    fusion = _merge_avec_existant(
        prev,
        build_dossier([_p(ensemble), _p(decision)]),
        dates_sans_scrutin={"D1": "2025-06-23"},
    )
    assert fusion.mise_a_jour is not None
    assert fusion.mise_a_jour.label == "Nouveau vote"


def test_amendement_tranche_apres_minuit_appartient_a_la_seance_de_la_veille():
    from app.ingestion.amendements import _jour_de_seance

    assert _jour_de_seance("2026-02-04T00:03:06+01:00") == "2026-02-03"
    assert _jour_de_seance("2026-02-04T06:59:00+01:00") == "2026-02-03"
    assert _jour_de_seance("2026-02-04T15:10:00+01:00") == "2026-02-04"
    assert _jour_de_seance("2026-02-04") == "2026-02-04"
    assert _jour_de_seance({"@xsi:nil": "true"}) is None


def test_statut_en_cours_corrige_par_les_actes():
    from app.ingestion.sync import statut_au_vu_des_actes
    from app.schemas import EtatTexte, PhaseScrutin

    amdt = _scrutin(
        "AM1", "2025-04-07", "l'amendement n° 4 de M. X", public=False,
        modalite=ModaliteVote.main_levee,
    )
    senat = _scrutin(
        "V1", "2025-03-11", "l'ensemble de la proposition de loi", chambre=Chambre.senat
    )
    d = build_dossier([_p(amdt), _p(senat)])
    assert d.statut is StatutScrutin.en_cours
    # La dernière étape conclue date du jour des amendements : elle tranche.
    d.trajectoire = [
        PhaseScrutin(label="2e lecture", chambre="assemblee", statut="adopte", date="2025-04-07")
    ]
    statut_au_vu_des_actes(d)
    assert d.statut is StatutScrutin.adopte
    # Une étape conclue plus ancienne que les amendements ne tranche rien.
    d = build_dossier([_p(amdt), _p(senat)])
    d.trajectoire = [
        PhaseScrutin(label="1re lecture", chambre="senat", statut="adopte", date="2025-03-11")
    ]
    statut_au_vu_des_actes(d)
    assert d.statut is StatutScrutin.en_cours
    # Promulguée : adoptée, quoi que disent les votes.
    d.etat = EtatTexte(etat="promulgue", date="2025-05-01")
    statut_au_vu_des_actes(d)
    assert d.statut is StatutScrutin.adopte
