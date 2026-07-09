"""Tests des garde-fous éditoriaux (§4.4) — le cœur anti-hallucination."""
from __future__ import annotations

from app.ai.guardrails import (
    check_ancrage,
    check_chiffres,
    check_lexique,
    doit_passer_en_revue,
    run_guardrails,
)
from app.domain.enums import NiveauConfiance
from app.schemas import PhraseSourcee, ResultatGlobal, ResumeScrutin

RESULTAT = ResultatGlobal(pour=310, contre=231, abstention=24, non_votants=12)


def _resume(**kw) -> ResumeScrutin:
    base = dict(
        titre_clair="T",
        resume=[PhraseSourcee(phrase="Le texte encadre les loyers.", source_id="texte_article_1")],
        confiance=NiveauConfiance.haute,
        relu_par_humain=False,
    )
    base.update(kw)
    return ResumeScrutin(**base)


def test_ancrage_ok():
    resume = _resume()
    assert check_ancrage(resume, {"texte_article_1"}) == []


def test_ancrage_source_inconnue():
    resume = _resume()
    violations = check_ancrage(resume, {"autre_source"})
    assert len(violations) == 1
    assert violations[0].regle == "ancrage"


def test_ancrage_source_vide():
    resume = _resume(
        resume=[PhraseSourcee(phrase="Une phrase.", source_id="")]
    )
    assert check_ancrage(resume, set()) != []


def test_lexique_detecte_adjectif_oriente():
    resume = _resume(
        resume=[PhraseSourcee(phrase="Cette réforme ambitieuse change tout.", source_id="s1")]
    )
    violations = check_lexique(resume)
    assert any(v.regle == "lexique" for v in violations)


def test_lexique_gere_les_accents():
    # « controversé » doit être détecté malgré l'accent.
    resume = _resume(
        resume=[PhraseSourcee(phrase="Un sujet controversé.", source_id="s1")]
    )
    assert check_lexique(resume) != []


def test_lexique_neutre_passe():
    resume = _resume(
        resume=[PhraseSourcee(phrase="Le groupe X a voté contre le texte.", source_id="s1")]
    )
    assert check_lexique(resume) == []


def test_chiffres_incoherents_bloques():
    resume = _resume(
        resume=[PhraseSourcee(phrase="Le texte a recueilli 999 voix.", source_id="texte_article_1")]
    )
    violations = check_chiffres(resume, RESULTAT)
    assert any(v.regle == "chiffres" for v in violations)


def test_chiffres_coherents_ok():
    resume = _resume(
        resume=[PhraseSourcee(phrase="310 députés ont voté pour.", source_id="texte_article_1")]
    )
    assert check_chiffres(resume, RESULTAT) == []


def test_confiance_faible_force_la_revue():
    report = run_guardrails(_resume(confiance=NiveauConfiance.faible), RESULTAT, {"texte_article_1"})
    assert doit_passer_en_revue(report, NiveauConfiance.faible) is True


def test_resume_propre_est_publiable():
    resume = _resume()
    report = run_guardrails(resume, RESULTAT, {"texte_article_1"})
    assert report.ok
    assert doit_passer_en_revue(report, resume.confiance) is False
