"""Indice de division d'un scrutin (rangée « Les votes les plus disputés »).

Arithmétique pure : aucun réseau, aucune base. Ce que ces tests protègent, c'est
surtout la **doctrine** — pas de dispersion interne au Sénat, pas de classement
d'un vote de conduite de séance, pas de rang sur un vote sans décompte.
"""
from __future__ import annotations

from app.domain.division import division
from app.domain.enums import Chambre, PositionVote, TypeVote
from app.repositories.base import limiter_par_dossier
from app.schemas import PositionGroupe, ResultatGlobal, VoteDisputeItem


def _resultat(pour: int, contre: int, abstention: int = 0, nv: int = 0):
    return ResultatGlobal(
        pour=pour, contre=contre, abstention=abstention, non_votants=nv
    )


def _groupe(
    nom: str,
    position: PositionVote,
    pour: int = 0,
    contre: int = 0,
    abstention: int = 0,
) -> PositionGroupe:
    return PositionGroupe(
        groupe_id=f"PO-{nom}",
        groupe_nom=nom,
        couleur="#000000",
        position_majoritaire=position,
        pour=pour,
        contre=contre,
        abstention=abstention,
    )


# Cas réel : amendement n° 7 du Gouvernement (acétamipride), 20 juillet 2026.
_ACETAMIPRIDE = _resultat(121, 131, 119)


def test_vote_serre_score_plus_haut_qu_un_vote_unanime():
    serre = division(_ACETAMIPRIDE, [], Chambre.assemblee)
    unanime = division(_resultat(500, 2, 3), [], Chambre.assemblee)
    assert serre is not None and unanime is not None
    assert serre.indice > unanime.indice


def test_composantes_brutes_sont_les_chiffres_affiches():
    d = division(_ACETAMIPRIDE, [], Chambre.assemblee)
    assert d is not None
    # Ce sont ces valeurs que la carte montre : elles viennent du scrutin, pas
    # d'une pondération.
    assert d.ecart == 10
    assert d.exprimes == 252
    assert d.abstention == 119
    assert d.votants == 371


def test_ampleur_departage_deux_votes_egalement_serres():
    # 40/40 et 200/200 sont aussi serrés l'un que l'autre ; seul le second a
    # divisé une chambre pleine.
    petit = division(_resultat(40, 40, 10), [], Chambre.assemblee)
    grand = division(_resultat(200, 200, 50), [], Chambre.assemblee)
    assert petit is not None and grand is not None
    assert grand.indice > petit.indice


def test_fracture_entre_groupes_compte_les_camps():
    groupes = [
        _groupe("A", PositionVote.pour, pour=100),
        _groupe("B", PositionVote.contre, contre=100),
        _groupe("C", PositionVote.abstention, abstention=60),
    ]
    d = division(_resultat(100, 100, 60), groupes, Chambre.assemblee)
    assert d is not None and d.camps == 3

    unanimes = [
        _groupe("A", PositionVote.pour, pour=100),
        _groupe("B", PositionVote.pour, pour=100),
    ]
    e = division(_resultat(200, 0, 60), unanimes, Chambre.assemblee)
    assert e is not None and e.camps == 1


def test_dispersion_interne_compte_les_groupes_divises():
    groupes = [
        # 40/10/5 : un quart des voix s'écarte de la position du groupe.
        _groupe("Divisé", PositionVote.pour, pour=40, contre=10, abstention=5),
        # 48/2/0 : 4 % d'écart, le grain normal d'un vote — pas « divisé ».
        _groupe("Uni", PositionVote.contre, pour=2, contre=48),
        # Trop petit pour qu'une voix isolée fasse un « groupe divisé ».
        _groupe("Minuscule", PositionVote.pour, pour=2, contre=1),
    ]
    d = division(_resultat(44, 59, 5), groupes, Chambre.assemblee)
    assert d is not None and d.groupes_disperses == 1


def test_jamais_de_dispersion_interne_au_senat():
    """Doctrine : au Sénat, les bulletins sont déposés par un délégué de groupe.

    Un écart intra-groupe y mesurerait la procédure, pas un désaccord — même
    raison que l'absence de « contre son groupe » et de cohésion.
    """
    groupes = [
        _groupe("Divisé", PositionVote.pour, pour=45, contre=6, abstention=3),
        _groupe("Uni", PositionVote.contre, contre=80),
    ]
    d = division(_resultat(47, 87, 3), groupes, Chambre.senat)
    assert d is not None
    assert d.groupes_disperses is None


def test_les_deux_chambres_sont_classees_sur_les_memes_criteres():
    """À chiffres identiques, un vote du Sénat et un vote de l'Assemblée ont le
    MÊME indice — parce que la dispersion interne, incalculable au Sénat, est
    hors du classement. Sinon l'une des deux chambres serait avantagée par un
    simple artefact de méthode."""
    groupes = [
        _groupe("Divisé", PositionVote.pour, pour=40, contre=10, abstention=5),
        _groupe("Uni", PositionVote.contre, contre=100),
    ]
    an = division(_resultat(140, 110, 40), groupes, Chambre.assemblee)
    senat = division(_resultat(140, 110, 40), groupes, Chambre.senat)
    assert an is not None and senat is not None
    assert an.indice == senat.indice
    # Le fait reste affiché là où il est défendable, et seulement là.
    assert an.groupes_disperses == 1
    assert senat.groupes_disperses is None


def test_vote_a_main_levee_non_classable():
    assert (
        division(_ACETAMIPRIDE, [], Chambre.assemblee, scrutin_public=False) is None
    )


def test_vote_trop_peu_fourni_non_classable():
    # 20 votants : « serré » n'y veut rien dire.
    assert division(_resultat(10, 10), [], Chambre.assemblee) is None


def test_motion_de_censure_non_classable():
    """L'article 49 ne fait recenser que les voix FAVORABLES à la motion :
    `contre` y vaut 0 par construction.

    L'écart entre deux camps n'a donc aucun sens ici — l'indice sortirait
    « quasi unanime » sur un vote qui a divisé l'hémicycle. La motion sortait
    déjà du classement par ce score, mais **par accident arithmétique** ; on
    l'écarte désormais parce que l'arithmétique ne s'y applique pas.
    """
    censure = _resultat(267, 0, 0, nv=12)
    # Sans le garde-fou, le vote serait bel et bien classé (267 votants).
    assert division(censure, [], Chambre.assemblee) is not None
    assert (
        division(censure, [], Chambre.assemblee, type_vote=TypeVote.motion_censure)
        is None
    )


def test_vote_de_conduite_de_seance_non_classable():
    """Souvent très serré, mais il ne décide de rien : le remonter ferait passer
    une péripétie de séance pour un moment de division politique."""
    for objet in (
        "la proposition du Gouvernement de prolonger la séance en cours au delà "
        "de minuit (projet de loi de finances)",
        "la demande de suspension de séance présentée par M. Léaument",
        "la demande de seconde délibération de M. Tanguy sur l'amendement n° 2",
    ):
        assert division(_ACETAMIPRIDE, [], Chambre.assemblee, objet=objet) is None

    # Un vote de fond reste classable, même s'il cite une motion.
    garde = division(
        _ACETAMIPRIDE,
        [],
        Chambre.assemblee,
        objet="la motion de rejet préalable de la proposition de loi",
    )
    assert garde is not None


def _item(scrutin_id: str, dossier_id: str) -> VoteDisputeItem:
    return VoteDisputeItem(
        scrutin_id=scrutin_id,
        dossier_id=dossier_id,
        dossier_titre="Un texte",
        objet="l'ensemble du projet de loi",
        date="2026-07-20",
        chambre=Chambre.assemblee,
        statut="adopte",
        resultat=_ACETAMIPRIDE,
        ecart=10,
        camps=3,
    )


def test_plafond_par_dossier_garde_les_mieux_classes():
    votes = [
        _item("S1", "D1"),
        _item("S2", "D1"),
        _item("S3", "D1"),  # 3e du même texte → écarté
        _item("S4", "D2"),
    ]
    retenus = limiter_par_dossier(votes, 2)
    assert [v.scrutin_id for v in retenus] == ["S1", "S2", "S4"]
