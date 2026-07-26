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


# --- Discussion générale (repli quand pas d'explications de vote) ---

_XML_DG = """<?xml version="1.0" encoding="UTF-8"?>
<compteRendu xmlns="http://schemas.assemblee-nationale.fr/referentiel">
  <uid>CRSANR5L17S2025DG</uid>
  <metadonnees><dateSeanceJour>jeudi 15 mai 2025</dateSeanceJour></metadonnees>
  <contenu>
    <point code_grammaire="TITRE_TEXTE_DISCUSSION" valeur=" (n[[o]] 900)"><texte>Refondation de Mayotte</texte></point>
    <point code_grammaire="DISC_GENERALE_1"><texte>Discussion générale</texte></point>
    <paragraphe code_grammaire="PAROLE_GENERIQUE">
      <orateurs><orateur><nom>Mme Sabrina Sebaihi</nom><id>795808</id></orateur></orateurs>
      <texte>Ce texte doit garantir la reconstruction et l'accès à l'eau pour les habitants de Mayotte.</texte>
    </paragraphe>
    <paragraphe code_grammaire="PAROLE_GENERIQUE">
      <orateurs><orateur><nom>Mme Sabrina Sebaihi</nom><id>795808</id></orateur></orateurs>
      <texte>Je reprends la parole mais cela ne doit pas créer un second argument pour mon groupe.</texte>
    </paragraphe>
    <paragraphe code_grammaire="PAROLE_GENERIQUE">
      <orateurs><orateur><nom>Mme la présidente</nom></orateur></orateurs>
      <texte>La parole est à l'orateur suivant pour la discussion générale, je vous en prie.</texte>
    </paragraphe>
    <paragraphe code_grammaire="PAROLE_GENERIQUE">
      <orateurs><orateur><nom>M. Éric Martineau</nom><id>795100</id></orateur></orateurs>
      <texte>Notre groupe soutient l'objectif mais s'interroge sur le financement des mesures.</texte>
    </paragraphe>
    <point code_grammaire="DISC_ARTICLES_1_2"><texte>Discussion des articles</texte></point>
    <paragraphe code_grammaire="PAROLE_GENERIQUE">
      <orateurs><orateur><nom>M. Après Section</nom><id>111111</id></orateur></orateurs>
      <texte>Cette prise de parole est hors de la discussion générale et ne doit pas être capturée.</texte>
    </paragraphe>
  </contenu>
</compteRendu>
"""


def test_extraire_debats_discussion_generale_en_repli():
    debats = extraire_debats(_XML_DG)
    assert len(debats) == 1
    d = debats[0]
    # Pas d'explications de vote formelles ici, mais le texte est conservé grâce
    # à la discussion générale (source de repli).
    assert d.explications == []
    # Orateur résolu par acteurRef (le CR n'écrit pas le groupe dans le nom).
    refs = [iv.acteur_ref for iv in d.interventions_generales]
    # Présidente exclue (pas d'id) ; orateur « hors section » exclu (point suivant).
    assert refs == ["PA795808", "PA795100"]
    assert d.interventions_generales[0].orateur == "Mme Sabrina Sebaihi"
    assert d.interventions_generales[0].groupe == ""
    # Les deux prises consécutives de Sebaihi forment UNE intervention recollée :
    # une parole hachée par les interruptions ne doit pas être réduite à son
    # premier fragment.
    assert "garantir la reconstruction" in d.interventions_generales[0].texte
    assert "Je reprends la parole" in d.interventions_generales[0].texte


def test_extraire_debats_reprise_de_parole_non_consecutive_ignoree():
    # Un orateur qui reprend la parole APRÈS un autre n'est compté qu'une fois :
    # un seul argument par groupe (§7.4).
    xml = _XML_DG.replace(
        "<texte>Je reprends la parole mais cela ne doit pas créer un second argument pour mon groupe.</texte>",
        "<texte>Ce paragraphe appartient à un autre orateur intercalé dans la discussion.</texte>",
    ).replace(
        "<nom>Mme Sabrina Sebaihi</nom><id>795808</id></orateur></orateurs>\n"
        "      <texte>Ce paragraphe appartient",
        "<nom>M. Intercalé</nom><id>795999</id></orateur></orateurs>\n"
        "      <texte>Ce paragraphe appartient",
    )
    # Sebaihi reparle plus loin dans la séance (après M. Intercalé) : ignorée.
    xml = xml.replace(
        '<point code_grammaire="DISC_ARTICLES_1_2">',
        '<paragraphe code_grammaire="PAROLE_GENERIQUE">'
        '<orateurs><orateur><nom>Mme Sabrina Sebaihi</nom><id>795808</id></orateur></orateurs>'
        '<texte>Je redemande la parole plus tard, cela ne doit pas créer un second argument.</texte>'
        '</paragraphe>'
        '<point code_grammaire="DISC_ARTICLES_1_2">',
    )
    d = extraire_debats(xml)[0]
    refs = [iv.acteur_ref for iv in d.interventions_generales]
    assert refs == ["PA795808", "PA795999", "PA795100"]


# --- Débats sans section dédiée (motion de censure, motion de rejet préalable) ---

_XML_CENSURE = """<?xml version="1.0" encoding="UTF-8"?>
<compteRendu xmlns="http://schemas.assemblee-nationale.fr/referentiel">
  <uid>CRSANR5L17S2025O1N092</uid>
  <metadonnees><dateSeanceJour>mercredi 05 février 2025</dateSeanceJour></metadonnees>
  <contenu>
    <point code_grammaire="TITRE_TEXTE_DISCUSSION"><texte>Motion de censure</texte></point>
    <paragraphe code_grammaire="ODJ_APPEL_DISCUSSION">
      <orateurs><orateur><nom>Mme la présidente</nom></orateur></orateurs>
      <texte>L'ordre du jour appelle la discussion et le vote sur la motion de censure.</texte>
    </paragraphe>
    <paragraphe code_grammaire="PAROLE_GENERIQUE">
      <orateurs><orateur><nom>Mme Aurélie Trouvé</nom><id>795200</id></orateur></orateurs>
      <texte>Ce gouvernement mène une politique budgétaire que nous jugeons intenable pour les services publics.</texte>
    </paragraphe>
    <paragraphe code_grammaire="INTERRUPTION_1_10">
      <orateurs><orateur><nom>M. Thibault Bazin</nom><id>795300</id></orateur></orateurs>
      <texte>C'est vous qui parlez de ruine ?</texte>
    </paragraphe>
    <paragraphe code_grammaire="PAROLE_GENERIQUE">
      <orateurs><orateur><nom>Mme Aurélie Trouvé</nom><id>795200</id></orateur></orateurs>
      <texte>Vous serez responsables d'une chute historique des recettes de l'État.</texte>
    </paragraphe>
    <point code_grammaire="SCRUTIN_1_10"><texte>Scrutin public</texte></point>
    <paragraphe code_grammaire="PAROLE_GENERIQUE">
      <orateurs><orateur><nom>M. Après Vote</nom><id>795400</id></orateur></orateurs>
      <texte>Cette prise de parole suit le scrutin et ne doit pas être capturée du tout.</texte>
    </paragraphe>
  </contenu>
</compteRendu>
"""


def test_extraire_debats_motion_de_censure_sans_section():
    # Le CR d'une motion de censure n'ouvre NI « Explications de vote » NI
    # « Discussion générale » : les paroles sont directement sous le titre.
    d = extraire_debats(_XML_CENSURE)
    assert len(d) == 1
    interventions = d[0].interventions_generales
    assert [iv.acteur_ref for iv in interventions] == ["PA795200"]
    # Présidente exclue (paragraphe non PAROLE_GENERIQUE), interruption exclue,
    # prise de parole d'après le scrutin exclue.
    texte = interventions[0].texte
    assert "politique budgétaire" in texte and "chute historique" in texte


def test_extraire_debats_motion_de_rejet_prealable():
    xml = _XML_CENSURE.replace(
        '<point code_grammaire="TITRE_TEXTE_DISCUSSION"><texte>Motion de censure</texte></point>',
        '<point code_grammaire="TITRE_TEXTE_DISCUSSION" valeur=" (n[[o]] 1025)">'
        "<texte>Fermetures abusives de comptes bancaires</texte></point>"
        '<point code_grammaire="MOTION_RP_1_1"><texte>Motion de rejet préalable</texte></point>',
    )
    d = extraire_debats(xml)[0]
    assert d.numeros == frozenset({1025})
    assert [iv.acteur_ref for iv in d.interventions_generales] == ["PA795200"]


def test_extraire_debats_exclut_la_presidence_meme_avec_un_id():
    # La présidence de séance est elle-même députée : elle porte un acteurRef et
    # serait donc résolue en groupe. Ses annonces d'ordre du jour ne sont pas une
    # prise de position (§7.4) — on l'écarte par sa fonction.
    xml = _XML_CENSURE.replace(
        "<nom>Mme Aurélie Trouvé</nom><id>795200</id>",
        "<nom>Mme la présidente</nom><id>721908</id>",
    )
    assert extraire_debats(xml) == []


def test_extraire_debats_repli_seulement_en_dernier_recours():
    # Quand une discussion générale existe, le vivier de repli n'est PAS utilisé.
    xml = _XML_CENSURE.replace(
        '<point code_grammaire="SCRUTIN_1_10"><texte>Scrutin public</texte></point>',
        '<point code_grammaire="DISC_GENERALE_1"><texte>Discussion générale</texte></point>'
        '<paragraphe code_grammaire="PAROLE_GENERIQUE">'
        "<orateurs><orateur><nom>M. Orateur DG</nom><id>795500</id></orateur></orateurs>"
        "<texte>Notre groupe s'exprime ici dans le cadre de la discussion générale.</texte>"
        "</paragraphe>"
        '<point code_grammaire="SCRUTIN_1_10"><texte>Scrutin public</texte></point>',
    )
    d = extraire_debats(xml)[0]
    assert [iv.acteur_ref for iv in d.interventions_generales] == ["PA795500"]


def test_extraire_debats_explications_et_discussion_generale_coexistent():
    # Un texte qui a une discussion générale PUIS des explications de vote :
    # les deux sont capturées (l'ingestion préférera les explications).
    xml = _XML_DG.replace(
        '<point code_grammaire="DISC_ARTICLES_1_2"><texte>Discussion des articles</texte></point>',
        '<point code_grammaire="DISC_ARTICLES_1_2"><texte>Explications de vote</texte></point>'
        '<paragraphe code_grammaire="PAROLE_GENERIQUE">'
        '<orateurs><orateur><nom>M. Jean Dupont (RN)</nom></orateur></orateurs>'
        '<texte>Notre groupe votera pour ce texte essentiel à la reconstruction de Mayotte.</texte>'
        '</paragraphe>',
    )
    d = extraire_debats(xml)[0]
    assert [e.groupe for e in d.explications] == ["RN"]
    assert len(d.interventions_generales) == 2


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


def test_index_fusionne_le_meme_texte_discute_deux_fois_le_meme_jour():
    # Le CR rouvre un titre de discussion à chaque reprise de séance : le même
    # numéro deux fois le même jour, c'est UN texte, pas deux candidats ambigus.
    idx = IndexDebats([
        DebatTexte(
            titre="Statut de l'élu local", date="2025-03-06", seance_uid="CR1",
            numeros=frozenset({99}),
            explications=[ExplicationVote("RN", "M. X", "Un argument suffisamment long pour être gardé.")],
        ),
        DebatTexte(
            titre="Statut de l'élu local (suite)", date="2025-03-06", seance_uid="CR2",
            numeros=frozenset({99}),
            explications=[ExplicationVote("SOC", "Mme Y", "Un autre argument, tout aussi long, du groupe SOC.")],
        ),
    ])
    d = idx.pour_vote("2025-03-06", "l'ensemble du texte…", numeros={99})
    assert d is not None
    assert [e.groupe for e in d.explications] == ["RN", "SOC"]


def test_index_fusion_par_titre_quand_le_cr_ne_porte_pas_de_numero():
    idx = IndexDebats([
        _debat("Démarchage téléphonique consenti"),
        _debat("Démarchage téléphonique consenti"),
    ])
    d = idx.pour_vote(
        "2025-03-06", "l'ensemble de la proposition de loi sur le démarchage"
    )
    assert d is not None and d.titre.startswith("Démarchage")


def test_index_deux_textes_reellement_differents_restent_ambigus():
    # La fusion ne masque pas une vraie collision : deux textes distincts le
    # même jour, aucun ne recoupant nettement l'objet du vote → None (§2.5).
    idx = IndexDebats([
        _debat("Report des élections provinciales", numeros={10}),
        _debat("Simplification du millefeuille territorial", numeros={11}),
    ])
    assert idx.pour_vote("2025-03-06", "l'ensemble de la proposition de loi") is None


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
