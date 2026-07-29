"""Qui porte le texte — lecture de l'initiative dans l'archive des dossiers.

Fonctions pures : aucun réseau, aucune base. Ce que ces tests protègent, c'est la
**doctrine** — on ne nomme pas le ministre d'un projet de loi, on ne choisit pas
un auteur parmi plusieurs, un rapporteur n'est jamais un auteur, et l'initiative
se lit sur le **dépôt initial**, jamais sur un document de navette.
"""
from __future__ import annotations

from app.ingestion.initiative import (
    IdentiteAuteur,
    construire_index_initiatives,
    initiative_du_document,
    resoudre_initiative,
)

L17 = (17,)


def _doc(
    uid: str = "PIONANR5L17B0100",
    denomination: str = "Proposition de loi",
    auteur: object = None,
    depot: str = "INITDEP",
    ref: str = "DLR5L17N50001",
) -> dict:
    return {
        "uid": uid,
        "dossierRef": ref,
        "denominationStructurelle": denomination,
        "provenance": "Texte Déposé",
        "classification": {"famille": {"depot": {"code": depot}}},
        "auteurs": {"auteur": auteur} if auteur is not None else None,
    }


def _acteur(ref: str, qualite: str = "auteur") -> dict:
    return {"acteur": {"acteurRef": ref, "qualite": qualite}}


# ---------------------------------------------------------------------------
# Lecture d'un document
# ---------------------------------------------------------------------------


def test_projet_de_loi_est_du_gouvernement_sans_nommer_le_ministre():
    """Art. 39 : un projet de loi émane du Gouvernement. Le ministre déposant
    est nommé par la source, mais sa qualité ministérielle ne l'est nulle part
    chez nous — on ne la devine pas (§2.5)."""
    doc = _doc(
        uid="PRJLANR5L17B0100",
        denomination="Projet de loi",
        auteur=_acteur("PA643210"),
    )
    initiative = initiative_du_document(doc)
    assert initiative is not None
    assert initiative.origine == "gouvernement"
    assert initiative.acteur_ref is None


def test_proposition_avec_un_auteur_unique_le_nomme():
    initiative = initiative_du_document(_doc(auteur=_acteur("PA795664")))
    assert initiative is not None
    assert initiative.origine == "parlementaire"
    assert initiative.acteur_ref == "PA795664"


def test_proposition_a_plusieurs_auteurs_ne_designe_personne():
    """L'origine reste vraie, mais choisir le premier de la liste serait choisir
    à la place de la source (§2.5) — même règle que `auteur_amendement`."""
    initiative = initiative_du_document(
        _doc(auteur=[_acteur("PA775302"), _acteur("PA703538")])
    )
    assert initiative is not None
    assert initiative.origine == "parlementaire"
    assert initiative.acteur_ref is None


def test_un_meme_auteur_repete_reste_un_auteur_unique():
    """La source duplique parfois une entrée : c'est une seule personne."""
    initiative = initiative_du_document(
        _doc(auteur=[_acteur("PA758716"), _acteur("PA758716")])
    )
    assert initiative is not None
    assert initiative.acteur_ref == "PA758716"


def test_les_rapporteurs_ne_sont_jamais_des_auteurs():
    """Rapporteurs et auteurs cohabitent dans `auteurs.auteur` : seule la
    `qualite` les distingue. Sans auteur, un texte de commission n'a pas
    d'initiative lisible ici."""
    initiative = initiative_du_document(
        _doc(
            auteur=[
                _acteur("PA796010", qualite="rapporteur"),
                {"organe": {"organeRef": "PO420120"}},
            ]
        )
    )
    assert initiative is None


def test_organe_du_senat_en_navette_designe_le_senat():
    """Un texte déposé au Sénat puis transmis : l'AN n'enregistre aucune
    personne, seulement l'organe. On dit d'où vient le texte, pas qui l'écrit."""
    initiative = initiative_du_document(
        _doc(auteur={"organe": {"organeRef": "PO838901"}}, depot="INITNAV")
    )
    assert initiative is not None
    assert initiative.origine == "senat"
    assert initiative.acteur_ref is None


def test_organe_du_senat_hors_navette_nest_pas_conclu():
    """Les deux indices sont exigés : un organe seul dans un dépôt INITIAL ne
    décrit pas une transmission — on s'abstient plutôt que d'extrapoler."""
    assert (
        initiative_du_document(
            _doc(auteur={"organe": {"organeRef": "PO838901"}}, depot="INITDEP")
        )
        is None
    )


def test_document_sans_auteur_na_pas_dinitiative():
    assert initiative_du_document(_doc()) is None


# ---------------------------------------------------------------------------
# Construction de l'index
# ---------------------------------------------------------------------------


def test_index_retient_le_depot_initial_pas_la_navette():
    """⚠️ Le document le plus récent d'une navette peut être signé du Sénat
    (texte renvoyé après une première lecture à l'Assemblée). S'y rabattre
    ferait passer un texte né à l'Assemblée pour un texte sénatorial."""
    index = construire_index_initiatives(
        [
            _doc(uid="PIONANR5L17B0100", auteur=_acteur("PA1")),
            _doc(
                uid="PIONANR5L17B0900",
                auteur={"organe": {"organeRef": "PO838901"}},
                depot="INITNAV",
            ),
        ],
        L17,
    )
    assert index["DLR5L17N50001"].origine == "parlementaire"
    assert index["DLR5L17N50001"].acteur_ref == "PA1"


def test_index_ignore_les_autres_legislatures():
    index = construire_index_initiatives(
        [_doc(ref="DLR5L15N30000", auteur=_acteur("PA1"))], L17
    )
    assert index == {}


def test_index_ignore_ce_qui_nest_pas_un_texte_depose():
    """Rapports et textes adoptés ne portent pas l'initiative du texte."""
    index = construire_index_initiatives(
        [
            {**_doc(auteur=_acteur("PA1")), "provenance": "Texte Adopté"},
            {
                **_doc(auteur=_acteur("PA2"), ref="DLR5L17N50002"),
                "denominationStructurelle": "Rapport",
            },
        ],
        L17,
    )
    assert index == {}


def test_index_accepte_le_document_enveloppe():
    """L'archive sérialise chaque fichier sous une clé « document »."""
    index = construire_index_initiatives(
        [{"document": _doc(auteur=_acteur("PA1"))}], L17
    )
    assert index["DLR5L17N50001"].acteur_ref == "PA1"


# ---------------------------------------------------------------------------
# Résolution de l'auteur
# ---------------------------------------------------------------------------

_IDENTITES = {
    "PA1": IdentiteAuteur(
        "Sébastien Peytavie",
        "Écologiste et Social",
        "#3aa655",
        "https://www.assemblee-nationale.fr/dyn/static/tribun/17/photos/794830.jpg",
    ),
    # Photo non vérifiée à l'ingestion : le référentiel n'en porte pas, l'app
    # affiche alors les initiales (§2.5 — jamais d'URL devinée).
    "PA2": IdentiteAuteur("Camille Vernet", "Renaissance", "#f5a623"),
}


def test_resolution_attache_nom_groupe_photo_et_lien():
    initiative = resoudre_initiative(
        initiative_du_document(_doc(auteur=_acteur("PA1"))), _IDENTITES
    )
    assert initiative is not None
    assert initiative.nom == "Sébastien Peytavie"
    assert initiative.depute_id == "PA1"
    assert initiative.groupe_nom == "Écologiste et Social"
    assert initiative.portrait_url is not None


def test_auteur_sans_photo_au_referentiel_nen_recoit_aucune():
    initiative = resoudre_initiative(
        initiative_du_document(_doc(auteur=_acteur("PA2"))), _IDENTITES
    )
    assert initiative is not None
    assert initiative.nom == "Camille Vernet"
    assert initiative.portrait_url is None


def test_auteur_hors_referentiel_garde_lorigine_mais_perd_son_nom():
    """Ancien député : pas de fiche, donc pas de lien — et surtout jamais une
    référence machine « PA… » affichée en guise de nom (§2.5)."""
    initiative = resoudre_initiative(
        initiative_du_document(_doc(auteur=_acteur("PA-inconnu"))), _IDENTITES
    )
    assert initiative is not None
    assert initiative.origine == "parlementaire"
    assert initiative.nom is None
    assert initiative.depute_id is None


def test_le_gouvernement_et_le_senat_nont_jamais_de_lien():
    for doc in (
        _doc(uid="PRJLANR5L17B0100", denomination="Projet de loi"),
        _doc(auteur={"organe": {"organeRef": "PO838901"}}, depot="INITNAV"),
    ):
        initiative = resoudre_initiative(initiative_du_document(doc), _IDENTITES)
        assert initiative is not None
        assert initiative.nom is None
        assert initiative.depute_id is None
        assert initiative.portrait_url is None


def test_absence_dinitiative_reste_absente():
    assert resoudre_initiative(None, _IDENTITES) is None
