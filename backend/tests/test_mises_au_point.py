"""Mises au point : la formule de l'Assemblée, mot pour mot, et rien d'inventé."""
from __future__ import annotations

from app.domain.enums import PositionVote
from app.ingestion.mises_au_point import extraire_mises_au_point

ACTEURS = {
    "PA1": "Dominique Voynet",
    "PA2": "Benoît Biteau",
    "PA3": "Alexandra Martin",
    "PA4": "Éric Woerth",
    "PA5": "Emmanuel Fernandes",
    "PA6": "Camille Sansciv",
}
CIV = {"PA1": "Mme", "PA2": "M.", "PA3": "Mme", "PA4": "M.", "PA5": "M."}


def _v(*refs: str) -> dict:
    votants = [{"acteurRef": r, "parDelegation": "false"} for r in refs]
    return {"votant": votants[0] if len(votants) == 1 else votants}


# Forme réelle de l'open data : listes [None, None] et None pour les vides.
BLOC = {
    "pours": None,
    "contres": _v("PA1", "PA2"),
    "abstentions": [None, None],
    "nonVotants": _v("PA3"),
    "nonVotantsVolontaires": [None, None],
    "dysfonctionnement": {
        "nonVotants": None,
        "pour": None,
        "contre": _v("PA4"),
        "abstentions": _v("PA5"),
        "nonVotantsVolontaires": None,
    },
}


def test_phrases_officielles_mot_pour_mot():
    phrases = [m.phrase for m in extraire_mises_au_point(BLOC, ACTEURS, CIV)]
    assert phrases == [
        # Scrutin 3985 de la L17.
        "Mme Dominique Voynet a fait savoir qu'elle avait voulu « voter contre ».",
        "M. Benoît Biteau a fait savoir qu'il avait voulu « voter contre ».",
        # Scrutin 209.
        "Mme Alexandra Martin n'a pas pris part au scrutin.",
        # Scrutins 4569 et 4643.
        "M. Éric Woerth a voté « contre ». Sa position de vote n'a pas pu être prise en compte.",
        "M. Emmanuel Fernandes a voulu « s'abstenir volontairement ». Sa position de vote n'a pas pu être prise en compte.",
    ]


def test_nature_et_position_declaree():
    m = extraire_mises_au_point(BLOC, ACTEURS, CIV)
    assert [(x.nature, x.position) for x in m] == [
        ("mise_au_point", PositionVote.contre),
        ("mise_au_point", PositionVote.contre),
        ("mise_au_point", PositionVote.non_votant),
        ("dysfonctionnement", PositionVote.contre),
        ("dysfonctionnement", PositionVote.abstention),
    ]


def test_sans_civilite_forme_neutre_sans_deviner_le_genre():
    bloc = {"pours": _v("PA6")}
    [m] = extraire_mises_au_point(bloc, ACTEURS, CIV)
    assert m.phrase == "Camille Sansciv a indiqué avoir voulu « voter pour »."


def test_inconnu_omis_et_lien_seulement_si_le_depute_siege():
    bloc = {"contres": _v("PA1", "PA999")}
    m = extraire_mises_au_point(bloc, ACTEURS, CIV, frozenset({"PA1"}))
    # Une référence « PA999 » n'est pas un nom : omise (§2.5).
    assert [(x.nom, x.depute_id) for x in m] == [("Dominique Voynet", "PA1")]
    m = extraire_mises_au_point(bloc, ACTEURS, CIV, frozenset())
    assert m[0].depute_id is None


def test_rien_a_extraire():
    assert extraire_mises_au_point(None, ACTEURS, CIV) == []
    assert extraire_mises_au_point(BLOC, None, CIV) == []
