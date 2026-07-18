"""Tests du parser des débats (explications de vote) et de la liaison au dossier."""
from __future__ import annotations

from app.ingestion.debats import (
    DebatTexte,
    ExplicationVote,
    IndexDebats,
    _date_iso,
    extraire_debats,
    url_compte_rendu,
)

_XML = """<?xml version="1.0" encoding="UTF-8"?>
<compteRendu xmlns="http://schemas.assemblee-nationale.fr/referentiel">
  <uid>CRSANR5L17S2025O1N037</uid>
  <metadonnees><dateSeanceJour>mercredi 06 novembre 2024</dateSeanceJour></metadonnees>
  <contenu>
    <point code_grammaire="TITRE_TEXTE_DISCUSSION" valeur=" (n[[o]] 525)"><texte>Report des élections en Nouvelle-Calédonie</texte></point>
    <point code_grammaire="DISC_ARTICLES_1_2"><texte>Explications de vote</texte></point>
    <paragraphe code_grammaire="PAROLE_GENERIQUE">
      <orateurs><orateur><nom>M. Jean Dupont (RN)</nom></orateur></orateurs>
      <texte>Notre groupe votera pour ce texte car il protège les Calédoniens et respecte le vote du Congrès.</texte>
    </paragraphe>
    <paragraphe code_grammaire="INTERRUPTION_1_10">
      <orateurs><orateur><nom>Mme Autre (SOC)</nom></orateur></orateurs>
      <texte>C'est faux !</texte>
    </paragraphe>
    <paragraphe code_grammaire="PAROLE_GENERIQUE">
      <orateurs><orateur><nom>Mme la présidente</nom></orateur></orateurs>
      <texte>La parole est à Mme Untel pour le groupe suivant, je vous en prie.</texte>
    </paragraphe>
    <paragraphe code_grammaire="PAROLE_GENERIQUE">
      <orateurs><orateur><nom>Mme Claire Martin (EcoS)</nom></orateur></orateurs>
      <texte>Nous nous abstiendrons car la question de la décolonisation n'est pas traitée par ce texte.</texte>
    </paragraphe>
    <point code_grammaire="VOTE_ENS_PPL_S_1_10"><texte>Vote sur l'ensemble</texte></point>
    <paragraphe code_grammaire="PAROLE_GENERIQUE">
      <orateurs><orateur><nom>M. Hors Section (DR)</nom></orateur></orateurs>
      <texte>Cette prise de parole est après le vote et ne doit pas être capturée du tout.</texte>
    </paragraphe>
  </contenu>
</compteRendu>
"""


def test_date_iso():
    assert _date_iso("mercredi 06 novembre 2024") == "2024-11-06"
    assert _date_iso("") is None


def test_extraire_debats_isole_les_explications_de_vote():
    debats = extraire_debats(_XML)
    assert len(debats) == 1
    d = debats[0]
    assert d.date == "2024-11-06"
    assert d.seance_uid == "CRSANR5L17S2025O1N037"
    groupes = [e.groupe for e in d.explications]
    # RN et EcoS gardés ; interruption (trop courte), présidente (sans groupe) et
    # la prise de parole après le vote (hors section) exclues.
    assert groupes == ["RN", "EcoS"]
    assert d.explications[0].orateur == "M. Jean Dupont"
    # Le numéro du texte est lu dans l'attribut `valeur` du titre de discussion.
    assert d.numeros == frozenset({525})


def test_extraire_debats_variantes_de_section():
    # « Explication de vote » (singulier) et « Explications de vote communes »
    # existent dans l'archive : elles ouvrent aussi la section.
    for variante in ("Explication de vote", "Explications de vote communes"):
        xml = _XML.replace("Explications de vote", variante)
        debats = extraire_debats(xml)
        assert len(debats) == 1 and len(debats[0].explications) == 2, variante


def test_extraire_debats_xml_invalide():
    assert extraire_debats("pas du xml") == []


def _debat(titre, date="2025-03-06", numeros=frozenset()):
    return DebatTexte(
        titre=titre,
        date=date,
        seance_uid="CRTEST",
        numeros=frozenset(numeros),
        explications=[ExplicationVote("RN", "M. X", "Une explication de vote assez longue pour être gardée.")],
    )


def test_index_liaison_par_titre_meme_jour():
    idx = IndexDebats([_debat("Démarchage téléphonique consenti")])
    d = idx.pour_vote("2025-03-06", "l'ensemble de la proposition de loi sur le démarchage")
    assert d is not None and d.titre.startswith("Démarchage")


def test_index_candidat_unique_sans_recoupement_refuse():
    # Un seul débat capturé ce jour-là, mais sur un AUTRE texte : sans
    # recoupement de titre ni numéro, on ne relie PAS (vécu : des explications
    # sur le don du sang reliées à un texte sur le vote des détenus).
    idx = IndexDebats([_debat("Promotion du don du sang")])
    assert (
        idx.pour_vote(
            "2025-03-06",
            "l'ensemble de la proposition de loi sur le vote par correspondance des détenus",
        )
        is None
    )


def test_index_liaison_par_numero_meme_jour():
    # Le numéro l'emporte sur un titre sans rapport (labels courts du CR).
    idx = IndexDebats([
        _debat("Territoires zéro chômeur", numeros={610}),
        _debat("Don du sang", numeros={720}),
    ])
    d = idx.pour_vote("2025-03-06", "l'ensemble de la proposition de loi visant l'emploi durable", numeros={610, 1544})
    assert d is not None and d.titre.startswith("Territoires")


def test_index_liaison_par_numero_vote_solennel_apres_le_debat():
    # Vote solennel le mardi suivant : le débat (avec explications) date de
    # quelques jours avant. Le numéro permet la liaison certaine.
    idx = IndexDebats([_debat("Statut de l'élu local", date="2025-03-04", numeros={1603})])
    d = idx.pour_vote("2025-03-11", "l'ensemble de la proposition de loi sur le statut", numeros={1603})
    assert d is not None
    # Mais jamais un débat POSTÉRIEUR au vote, ni trop ancien.
    assert idx.pour_vote("2025-03-03", "l'ensemble…", numeros={1603}) is None
    assert idx.pour_vote("2025-04-30", "l'ensemble…", numeros={1603}) is None


def test_index_numero_ambigu_le_meme_jour_refuse():
    idx = IndexDebats([
        _debat("Première séance", numeros={99}),
        _debat("Deuxième séance", numeros={99}),
    ])
    assert idx.pour_vote("2025-03-06", "l'ensemble du texte…", numeros={99}) is None


def test_index_depart_par_titre_si_plusieurs_le_meme_jour():
    idx = IndexDebats([
        _debat("Démarchage téléphonique consenti et protection des consommateurs"),
        _debat("Gestion des compétences eau et assainissement"),
    ])
    d = idx.pour_vote(
        "2025-03-06",
        "l'ensemble de la proposition de loi sur le démarchage téléphonique consenti",
    )
    assert d is not None and d.titre.startswith("Démarchage")


def test_index_ambigu_renvoie_none():
    # Deux textes le même jour, titre du vote ne recoupant nettement aucun.
    idx = IndexDebats([
        _debat("Report des élections provinciales"),
        _debat("Simplification du millefeuille territorial"),
    ])
    assert idx.pour_vote("2025-03-06", "l'ensemble de la proposition de loi") is None


def test_index_aucun_candidat_ce_jour():
    idx = IndexDebats([_debat("Démarchage téléphonique", date="2025-03-06")])
    assert idx.pour_vote("2025-03-07", "l'ensemble du texte") is None


def test_url_compte_rendu():
    assert url_compte_rendu(17, "CRSANR5L17S2025O1N037").endswith(
        "/dyn/17/comptes-rendus/seance/CRSANR5L17S2025O1N037"
    )
