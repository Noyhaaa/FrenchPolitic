"""Tests de la génération de résumé — gabarit déterministe + garde-fous (§4.1)."""
from __future__ import annotations

from app.ai.faits import construire_faits
from app.ai.gabarit import composer_resume
from app.ai.generation import ResumeGenerator, generer_resume
from app.ai.guardrails import run_guardrails
from app.ai.rag import contexte_depuis_faits
from app.domain.enums import StatutRevue
from app.schemas import PositionGroupe, ResultatGlobal, Scrutin


def _scrutin(
    uid: str,
    date: str,
    objet: str,
    statut: str = "adopte",
    resultat: ResultatGlobal | None = None,
    positions: list[PositionGroupe] | None = None,
) -> Scrutin:
    return Scrutin(
        id=uid,
        dossier_id="dos-x",
        date=date,
        objet=objet,
        statut=statut,
        scrutin_public=True,
        resultat=resultat
        or ResultatGlobal(pour=0, contre=0, abstention=0, non_votants=0),
        positions_groupes=positions or [],
    )


def _pos(nom: str, position: str) -> PositionGroupe:
    return PositionGroupe(
        groupe_id=nom,
        groupe_nom=nom,
        couleur="#000000",
        position_majoritaire=position,
        pour=0,
        contre=0,
        abstention=0,
    )


def _faits_complet():
    ensemble = _scrutin(
        "s-ens",
        "2026-07-16",
        "l'ensemble de la proposition de loi",
        "adopte",
        ResultatGlobal(pour=305, contre=194, abstention=41, non_votants=2),
        [_pos("Groupe A", "pour"), _pos("Groupe B", "contre")],
    )
    article = _scrutin("s-art", "2026-07-03", "l'article 2", "adopte")
    amende_ok = _scrutin("s-a1", "2026-07-10", "l'amendement n° 1", "adopte")
    amende_ko = _scrutin("s-a2", "2026-07-10", "l'amendement n° 2", "rejete")
    return construire_faits(
        titre_clair="Proposition de loi visant à protéger l'eau",
        titre_officiel="Proposition de loi visant à protéger l'eau",
        theme="Environnement",
        votes_texte=[ensemble, article],
        votes_amendement=[amende_ok, amende_ko],
    )


def test_gabarit_compose_cinq_phrases_sourcees():
    faits = _faits_complet()
    context = contexte_depuis_faits(faits)
    resume = composer_resume(faits, context)

    assert len(resume.resume) == 5
    assert {p.source_id for p in resume.resume} == context.source_ids
    texte = " ".join(p.phrase for p in resume.resume)
    assert "305 voix contre 194" in texte
    assert "Environnement" in texte


def test_gabarit_passe_les_garde_fous():
    """Le résumé du gabarit ne déclenche aucun garde-fou (ancrage, lexique,
    chiffres) — garantie clé du chemin déterministe."""
    faits = _faits_complet()
    context = contexte_depuis_faits(faits)
    resume = composer_resume(faits, context)
    report = run_guardrails(resume, faits.resultat_reference, context.source_ids)
    assert report.ok, [v.message for v in report.violations]


def test_generer_resume_non_vide_et_confiance_moyenne():
    resume = generer_resume(_faits_complet())
    assert resume.resume
    assert resume.confiance.value == "moyenne"
    assert resume.relu_par_humain is False


def test_gabarit_sans_amendement_omet_la_phrase():
    """Donnée absente → pas de phrase inventée (§2.5)."""
    faits = construire_faits(
        titre_clair="Projet de loi de finances",
        titre_officiel="Projet de loi de finances",
        theme="Fiscalité",
        votes_texte=[
            _scrutin(
                "s1",
                "2026-07-01",
                "l'ensemble du projet de loi",
                "rejete",
                ResultatGlobal(pour=100, contre=200, abstention=0, non_votants=0),
            )
        ],
        votes_amendement=[],
    )
    resume = generer_resume(faits)
    assert not any(p.source_id == "amendements" for p in resume.resume)


async def test_resume_generator_mockllm_dossier_niveau():
    """Le chemin LLM (MockLLM) tourne au niveau dossier sans lever d'erreur."""
    gen = ResumeGenerator()
    result = await gen.generate(_faits_complet())
    assert result.statut_revue in (StatutRevue.publie, StatutRevue.en_attente)
