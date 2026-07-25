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
    _vote_ancre_procedural,
    _vote_ensemble,
)
from app.schemas import PositionGroupe, QuestionsCitoyennes, ResultatGlobal, Scrutin


class _FakeLLM:
    def __init__(self, *reponses: str) -> None:
        self._reponses = list(reponses)

    async def generate_text(self, system: str, user: str) -> str:
        return self._reponses.pop(0) if self._reponses else ""

    async def generate_json(self, system: str, user: str) -> dict:
        return {}


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


# --- ancre procédurale (motions de censure) ---


def test_vote_ancre_procedural_motion():
    motion = _vote("la motion de censure déposée en application de l'article 49", [])
    loi = _vote("l'ensemble de la proposition de loi", [])
    assert _vote_ensemble([motion]) is None  # pas d'« ensemble »
    assert _vote_ancre_procedural([motion]) is motion
    # Un texte non procédural n'obtient PAS d'ancre de repli (§2.5).
    assert _vote_ancre_procedural([loi]) is None


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
