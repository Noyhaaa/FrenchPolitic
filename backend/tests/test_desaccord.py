"""Tests du désaccord (Q2) côté ingestion : ancre procédurale, repli discussion
générale, résolution de groupe (abréviation vs acteurRef) et fuite mesurée."""
from __future__ import annotations

from datetime import datetime, timezone

from app.domain.enums import PositionVote
from app.ingestion.debats import DebatTexte, ExplicationVote, IndexDebats
from app.ingestion.organes import GroupInfo
from app.ingestion.sync import (
    SyncJob,
    SyncReport,
    _vote_conclusif,
)
from app.schemas import PositionGroupe, QuestionsCitoyennes, ResultatGlobal, Scrutin


class _FakeLLM:
    def __init__(self, *reponses: str) -> None:
        self._reponses = list(reponses)

    async def generate_text(self, system: str, user: str) -> str:
        return self._reponses.pop(0) if self._reponses else ""



class _Client:
    legislature = 17


def _pos(gid: str, nom: str, sens: PositionVote) -> PositionGroupe:
    return PositionGroupe(
        groupe_id=gid, groupe_nom=nom, couleur="#111",
        position_majoritaire=sens, pour=1, contre=0, abstention=0,
    )


def _vote(objet: str, positions: list[PositionGroupe]) -> Scrutin:
    return Scrutin(
        id="S", dossier_id="D", date="2025-05-15", objet=objet,
        statut="adopte", scrutin_public=True,
        resultat=ResultatGlobal(pour=1, contre=0, abstention=0, non_votants=0),
        positions_groupes=positions,
    )


def _job(llm: _FakeLLM) -> SyncJob:
    return SyncJob(session_factory=None, client=_Client(), llm=llm)  # type: ignore[arg-type]


def _report() -> SyncReport:
    return SyncReport(started_at=datetime.now(timezone.utc))


# --- ancre : le vote qui conclut le texte ---


def test_vote_conclusif_ordre_de_priorite():
    ensemble = _vote("l'ensemble de la proposition de loi sur le démarchage", [])
    unique = _vote("l'article unique de la proposition de loi sur le démarchage", [])
    direct = _vote("la proposition de résolution tendant à créer un institut", [])
    censure = _vote("la motion de censure déposée en application de l'article 49", [])
    rejet = _vote("la motion de rejet préalable, déposée par Mme X, du projet de loi", [])

    # L'« ensemble » prime sur tout le reste, quel que soit l'ordre des votes.
    assert _vote_conclusif([unique, rejet, ensemble]) is ensemble
    # Sinon l'article unique (texte mono-article : ce vote EST le vote du texte).
    assert _vote_conclusif([rejet, unique]) is unique
    # Sinon le texte cité directement (résolutions, approbations d'accord).
    assert _vote_conclusif([rejet, direct]) is direct
    # Sinon un vote procédural, sinon une motion.
    assert _vote_conclusif([rejet, censure]) is censure
    assert _vote_conclusif([rejet]) is rejet


def test_vote_conclusif_ignore_les_votes_d_articles():
    # Un dossier examiné article par article (budget…) n'a pas de vote conclusif :
    # le débat sur l'article 27 n'est pas une prise de position sur le texte (§2.5).
    articles = [
        _vote("l'article 27 du projet de loi de finances pour 2025", []),
        _vote("l'article premier de la proposition de loi sur les comptes", []),
        _vote("la première partie du projet de loi de finances pour 2025", []),
    ]
    assert _vote_conclusif(articles) is None
    assert _vote_conclusif([]) is None


# --- repli discussion générale (orateur → groupe via annuaire) ---


async def test_desaccord_repli_discussion_generale():
    job = _job(_FakeLLM("Le texte doit garantir la reconstruction de Mayotte."))
    job._index_debats = IndexDebats([
        DebatTexte(
            titre="Refondation de Mayotte", date="2025-05-15", seance_uid="CR",
            numeros=frozenset({900}),
            interventions_generales=[
                ExplicationVote(groupe="", orateur="Mme S",
                                texte="Il faut reconstruire Mayotte.", acteur_ref="PA1"),
            ],
        )
    ])
    job._numeros_par_ref = {"REF": {900}}
    job._groupe_par_acteur = {"PA1": ("G1", "Groupe Un")}
    ancre = _vote(
        "l'ensemble de la proposition de loi sur la refondation de Mayotte",
        [_pos("G1", "Groupe Un", PositionVote.pour)],
    )
    q = QuestionsCitoyennes(resultat="…")
    report = _report()
    ok = await job._construire_desaccord(None, "REF", [ancre], q, report)
    assert ok and len(q.desaccord) == 1
    a = q.desaccord[0]
    assert a.groupe == "Groupe Un"
    assert a.sens == PositionVote.pour  # sens issu du scrutin, jamais du LLM
    # L'objet du vote d'ancrage est conservé : les positions ne se lisent qu'au
    # regard du vote sur lequel elles ont été exprimées (§7.4).
    assert q.desaccord_objet == ancre.objet


async def test_desaccord_ancre_sur_une_motion_de_rejet():
    # Texte rejeté par une motion : l'ancre est la motion, et son objet est
    # conservé — « pour » veut alors dire « pour le rejet du texte ».
    job = _job(_FakeLLM("Ce texte ne répond pas au problème posé."))
    job._index_debats = IndexDebats([
        DebatTexte(
            titre="Fermetures abusives de comptes bancaires", date="2025-05-15",
            seance_uid="CR", numeros=frozenset({1025}),
            interventions_generales=[
                ExplicationVote(groupe="", orateur="M. X",
                                texte="Nous demandons le rejet de ce texte, qui ne "
                                      "répond pas au problème posé.", acteur_ref="PA1"),
            ],
        )
    ])
    job._numeros_par_ref = {"REF": {1025}}
    job._groupe_par_acteur = {"PA1": ("G1", "Groupe Un")}
    motion = _vote(
        "la motion de rejet préalable, déposée par Mme X, de la proposition de loi",
        [_pos("G1", "Groupe Un", PositionVote.pour)],
    )
    q = QuestionsCitoyennes(resultat="…")
    ok = await job._construire_desaccord(None, "REF", [motion], q, _report())
    assert ok
    assert q.desaccord_objet == motion.objet


async def test_desaccord_ecarte_les_groupes_sans_vote_exprime():
    # Motion de censure : la Constitution ne fait recenser que les votes
    # favorables, si bien que l'open data porte « pour » pour TOUS les groupes,
    # même ceux dont aucun député n'a voté (0/0/0). On n'affiche que les
    # positions que la source documente vraiment (§2.5).
    job = _job(_FakeLLM("Le budget prive les services publics de moyens.",
                        "La censure empêcherait des mesures utiles d'être déployées."))
    job._index_debats = IndexDebats([
        DebatTexte(
            titre="Motion de censure", date="2025-05-15", seance_uid="CR",
            interventions_generales=[
                ExplicationVote(groupe="", orateur="Mme A",
                                texte="Nous censurons ce gouvernement dont le budget "
                                      "prive les services publics de moyens.",
                                acteur_ref="PA1"),
                ExplicationVote(groupe="", orateur="M. B",
                                texte="Nous refusons cette censure, qui empêcherait "
                                      "des mesures utiles d'être déployées.",
                                acteur_ref="PA2"),
            ],
        )
    ])
    job._groupe_par_acteur = {"PA1": ("G1", "Groupe Un"), "PA2": ("G2", "Groupe Deux")}
    censure = _vote(
        "la motion de censure déposée en application de l'article 49, alinéa 3",
        [
            _pos("G1", "Groupe Un", PositionVote.pour),  # 1 voix pour (cf. _pos)
            PositionGroupe(
                groupe_id="G2", groupe_nom="Groupe Deux", couleur="#111",
                position_majoritaire=PositionVote.pour,  # artefact de la source
                pour=0, contre=0, abstention=0,
            ),
        ],
    )
    q = QuestionsCitoyennes(resultat="…")
    ok = await job._construire_desaccord(None, None, [censure], q, _report())
    assert ok and [a.groupe for a in q.desaccord] == ["Groupe Un"]


def test_positions_documentees_realigne_un_desaccord_deja_en_base():
    from app.ingestion.sync import _positions_documentees
    from app.schemas import ArgumentGroupe

    ancre = _vote(
        "l'ensemble de la proposition de loi",
        [
            _pos("G1", "Groupe Un", PositionVote.contre),
            PositionGroupe(
                groupe_id="G2", groupe_nom="Groupe Deux", couleur="#111",
                position_majoritaire=PositionVote.pour, pour=0, contre=0, abstention=0,
            ),
        ],
    )
    stockes = [
        ArgumentGroupe(groupe="Groupe Un", sens=PositionVote.pour, argument="A"),
        ArgumentGroupe(groupe="Groupe Deux", sens=PositionVote.pour, argument="B"),
        ArgumentGroupe(groupe="Groupe Trois", sens=PositionVote.pour, argument="C"),
    ]
    retenus = _positions_documentees(stockes, ancre)
    # Le sens suit le scrutin (« pour » stocké → « contre » réel) ; le groupe sans
    # vote exprimé et le groupe absent du scrutin sont retirés.
    assert [(a.groupe, a.sens) for a in retenus] == [
        ("Groupe Un", PositionVote.contre)
    ]


async def test_desaccord_sans_ancre_ne_produit_rien():
    # Dossier examiné article par article : pas de vote conclusif → pas de Q2.
    job = _job(_FakeLLM("Un argument."))
    job._index_debats = IndexDebats([])
    q = QuestionsCitoyennes(resultat="…")
    article = _vote("l'article 27 du projet de loi de finances pour 2025", [])
    assert not await job._construire_desaccord(None, "REF", [article], q, _report())
    assert q.desaccord is None and q.desaccord_objet is None


async def test_desaccord_prefere_explications_et_mesure_la_fuite_alias():
    # Explications présentes → on les utilise (pas la discussion générale).
    # Une abréviation inconnue est retirée MAIS enregistrée (fuite mesurée §7.4).
    job = _job(_FakeLLM("Ce texte protège les habitants."))
    job._index_debats = IndexDebats([
        DebatTexte(
            titre="Refondation de Mayotte", date="2025-05-15", seance_uid="CR",
            numeros=frozenset({900}),
            explications=[
                ExplicationVote("RN", "M. X", "Nous votons pour ce texte utile."),
                ExplicationVote("ZZZ", "M. Y", "Argument d'un groupe à l'abréviation inconnue."),
            ],
            interventions_generales=[
                ExplicationVote(groupe="", orateur="Mme S", texte="Repli.", acteur_ref="PA1"),
            ],
        )
    ])
    job._numeros_par_ref = {"REF": {900}}
    job._groupes_par_abbrev = {"rn": GroupInfo(id="G1", nom="Rassemblement National", abrev="RN", couleur="#111")}
    ancre = _vote(
        "l'ensemble de la proposition de loi sur la refondation de Mayotte",
        [_pos("G1", "Rassemblement National", PositionVote.contre)],
    )
    q = QuestionsCitoyennes(resultat="…")
    report = _report()
    ok = await job._construire_desaccord(None, "REF", [ancre], q, report)
    assert ok and [a.groupe for a in q.desaccord] == ["Rassemblement National"]
    assert report.abrevs_non_resolues == {"ZZZ"}  # fuite mesurée, pas devinée


# --- extraits de compte rendu conservés (revalidation hors ligne) ---


async def test_desaccord_rend_les_extraits_des_seuls_groupes_retenus():
    """Un argument met une opinion dans la bouche d'un groupe : il ne peut vivre
    que si l'on garde la phrase prononcée dont il est la paraphrase (§7.4, §7.5).

    Le second argument est fabriqué (aucun mot commun avec ce que le groupe a
    dit) : il est omis, et son extrait ne doit pas être conservé pour autant.
    """
    job = _job(_FakeLLM(
        "Le texte protège mieux les victimes de violences.",
        "Le monde agricole attend autre chose de ce gouvernement.",
    ))
    job._index_debats = IndexDebats([
        DebatTexte(
            titre="Protection des victimes", date="2025-05-15", seance_uid="CR",
            numeros=frozenset({900}),
            explications=[
                ExplicationVote("G1", "M. X",
                                "Ce texte protège mieux les victimes de violences."),
                ExplicationVote("G2", "Mme Y",
                                "Le dispositif proposé restera inapplicable faute "
                                "de moyens dans les tribunaux."),
            ],
        )
    ])
    job._numeros_par_ref = {"REF": {900}}
    job._groupes_par_abbrev = {
        "g1": GroupInfo(id="G1", nom="Groupe Un", abrev="G1", couleur="#111"),
        "g2": GroupInfo(id="G2", nom="Groupe Deux", abrev="G2", couleur="#222"),
    }
    ancre = _vote(
        "l'ensemble de la proposition de loi sur la protection des victimes",
        [
            _pos("G1", "Groupe Un", PositionVote.pour),
            _pos("G2", "Groupe Deux", PositionVote.contre),
        ],
    )
    q = QuestionsCitoyennes(resultat="…")
    sources = await job._construire_desaccord(None, "REF", [ancre], q, _report())
    assert [a.groupe for a in q.desaccord] == ["Groupe Un"]
    assert sources is not None and set(sources) == {"Groupe Un"}
    # L'extrait conservé est le texte réellement prononcé, pas la paraphrase.
    assert sources["Groupe Un"].startswith("Ce texte protège")


async def test_desaccord_sans_argument_ne_rend_aucune_source():
    job = _job(_FakeLLM("Le monde agricole attend autre chose."))
    job._index_debats = IndexDebats([
        DebatTexte(
            titre="Protection des victimes", date="2025-05-15", seance_uid="CR",
            numeros=frozenset({900}),
            explications=[
                ExplicationVote("G1", "M. X",
                                "Ce texte protège mieux les victimes de violences."),
            ],
        )
    ])
    job._numeros_par_ref = {"REF": {900}}
    job._groupes_par_abbrev = {
        "g1": GroupInfo(id="G1", nom="Groupe Un", abrev="G1", couleur="#111"),
    }
    ancre = _vote(
        "l'ensemble de la proposition de loi sur la protection des victimes",
        [_pos("G1", "Groupe Un", PositionVote.pour)],
    )
    q = QuestionsCitoyennes(resultat="…")
    assert await job._construire_desaccord(None, "REF", [ancre], q, _report()) is None
    assert q.desaccord is None and q.desaccord_objet is None
