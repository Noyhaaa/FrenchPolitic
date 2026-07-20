"""Tests des 4 questions citoyennes (génération gardée + repli §2.5)."""
from __future__ import annotations

from app.ai.questions import (
    PREFIXE_AUTEUR,
    PREFIXE_AUTEUR_AMENDEMENT,
    generer_desaccord,
    generer_questions,
    generer_questions_amendement,
    phrase_resultat,
    phrase_resultat_amendement,
    valider_reponse,
)
from app.schemas import ResultatGlobal, Scrutin, ScrutinResume


class _FakeLLM:
    """LLM factice : rejoue des réponses fixées (aucun réseau)."""

    def __init__(self, *reponses: str) -> None:
        self._reponses = list(reponses)

    async def generate_text(self, system: str, user: str) -> str:
        return self._reponses.pop(0) if self._reponses else ""

    async def generate_json(self, system: str, user: str) -> dict:
        return {}


_EXPOSE = (
    "En 2023, 4 000 000 affaires ont été transmises aux parquets. La présente "
    "proposition de loi vise à préserver les droits des victimes dont la "
    "plainte est classée sans suite."
)
_TITRE = "Proposition de loi visant à préserver les droits des victimes"
_SOURCES = f"{_TITRE}\n{_EXPOSE}"


def _scrutin(objet: str, statut: str = "adopte", public: bool = True) -> ScrutinResume:
    return ScrutinResume(
        id="S1",
        date="2025-05-07",
        objet=objet,
        statut=statut,
        scrutin_public=public,
        resultat=ResultatGlobal(pour=55, contre=0, abstention=5, non_votants=2),
    )


# --- valider_reponse : contrôles déterministes ---


def test_valide_une_reponse_sobre():
    r = "Le texte vise à préserver les droits des victimes."
    assert valider_reponse(r, _SOURCES) == r


def test_rejette_chiffre_absent_des_sources():
    # 37 % n'est pas dans les sources : chiffre inventé (ou importé d'ailleurs).
    assert valider_reponse("37 % des plaintes sont classées.", _SOURCES) is None


def test_accepte_chiffre_present_dans_les_sources():
    r = "En 2023, des affaires ont été transmises aux parquets."
    assert valider_reponse(r, _SOURCES) == r


def test_rejette_nature_inversee():
    # « proposition » dans les sources, « projet » dans la réponse → distorsion.
    assert valider_reponse("Ce projet de loi protège les victimes.", _SOURCES) is None


def test_rejette_lexique_evaluatif():
    assert valider_reponse("Une avancée nécessaire pour les victimes.", _SOURCES) is None


def test_rejette_vide_et_trop_long():
    assert valider_reponse("", _SOURCES) is None
    assert valider_reponse("mot " * 200, _SOURCES) is None


def test_rejette_fuite_de_caracteres_non_francais():
    # Fuite CJK observée en épreuve réelle avec qwen3 (« décès婴幼儿 »).
    assert valider_reponse("Un suivi des décès婴幼儿 serait créé.", _SOURCES) is None


def test_accepte_ponctuation_typographique_francaise():
    r = "Le texte vise – d’après l’exposé – à protéger les victimes…"
    assert valider_reponse(r, _SOURCES) == r


def test_rejette_prefixe_manquant():
    assert (
        valider_reponse("Cela protège les victimes.", _SOURCES, prefixe=PREFIXE_AUTEUR)
        is None
    )


# --- phrase_resultat : Q3 déterministe ---


def test_resultat_vote_ensemble():
    p = phrase_resultat([_scrutin("l'ensemble de la proposition de loi…")])
    assert p == "Le texte a été adopté par 55 voix contre 0, avec 5 abstentions."


def test_resultat_dernier_vote_si_pas_d_ensemble():
    p = phrase_resultat([_scrutin("l'article 2 de la proposition de loi…")])
    assert p is not None and p.startswith("Le dernier vote sur le texte a été adopté")


def test_resultat_main_levee_sans_decompte():
    p = phrase_resultat([_scrutin("l'ensemble du texte…", public=False)])
    assert p == "Le texte a été adopté à main levée (pas de décompte des voix)."


def test_resultat_absent_si_statut_en_cours():
    assert phrase_resultat([_scrutin("l'ensemble du texte…", statut="en_cours")]) is None
    assert phrase_resultat([]) is None


# --- generer_questions : orchestration ---


async def test_sans_llm_seul_le_resultat_est_renseigne():
    q = await generer_questions(_TITRE, [_scrutin("l'ensemble…")], _EXPOSE, None)
    assert q.resultat is not None
    assert q.pourquoi is None and q.changement is None and q.desaccord is None


async def test_avec_llm_reponses_validees():
    llm = _FakeLLM(
        "Les députés ont examiné une proposition de loi sur les droits des victimes.",
        f"{PREFIXE_AUTEUR}, cela permettrait de mieux protéger les victimes.",
    )
    q = await generer_questions(_TITRE, [_scrutin("l'ensemble…")], _EXPOSE, llm)
    assert q.pourquoi is not None and q.changement is not None
    assert q.changement.startswith(PREFIXE_AUTEUR)
    # Le désaccord n'est JAMAIS généré sans les débats en séance (§2.5).
    assert q.desaccord is None


async def test_reponse_distordue_rejetee_sans_bloquer_le_reste():
    llm = _FakeLLM(
        "Ce projet de loi concerne 89 % des plaintes.",  # nature + chiffre faux
        f"{PREFIXE_AUTEUR}, cela permettrait de mieux protéger les victimes.",
    )
    q = await generer_questions(_TITRE, [_scrutin("l'ensemble…")], _EXPOSE, llm)
    assert q.pourquoi is None
    assert q.changement is not None


async def test_sans_expose_pas_d_appel_llm():
    llm = _FakeLLM("ne doit pas être consommé")
    q = await generer_questions(_TITRE, [_scrutin("l'ensemble…")], None, llm)
    assert q.pourquoi is None and q.changement is None
    assert llm._reponses  # la réponse n'a pas été consommée : LLM non appelé


# --- questions d'un vote d'amendement (fiche vote) ---

_OBJET_AM = "l'amendement n° 80 de M. Durand à l'article 2 de la proposition de loi"
_DISPOSITIF = (
    "Au premier alinéa de l'article 2, le seuil de 50 000 habitants est "
    "remplacé par un seuil de 20 000 habitants."
)
_EXPOSE_AM = (
    "Les tensions locatives ne se limitent pas aux grandes villes : cet "
    "amendement étend l'encadrement aux communes moyennes."
)


def _scrutin_amendement(
    objet: str = _OBJET_AM,
    statut: str = "adopte",
    public: bool = True,
    dispositif: str | None = _DISPOSITIF,
    expose: str | None = _EXPOSE_AM,
) -> Scrutin:
    return Scrutin(
        id="SA1",
        dossier_id="D1",
        date="2025-05-07",
        objet=objet,
        statut=statut,
        scrutin_public=public,
        resultat=ResultatGlobal(pour=188, contre=268, abstention=26, non_votants=12),
        dispositif=dispositif,
        expose_sommaire=expose,
    )


def test_resultat_amendement_camp_gagnant_en_premier():
    # Rejeté par 268 voix contre 188 — jamais l'inverse (trompeur).
    p = phrase_resultat_amendement(_scrutin_amendement(statut="rejete"))
    assert p == "L'amendement a été rejeté par 268 voix contre 188, avec 26 abstentions."


def test_resultat_amendement_adopte():
    p = phrase_resultat_amendement(_scrutin_amendement())
    assert p == "L'amendement a été adopté par 188 voix contre 268, avec 26 abstentions."


def test_resultat_sous_amendement_sujet_adapte():
    objet = "le sous-amendement n° 3 de Mme Yon à l'amendement n° 80"
    p = phrase_resultat_amendement(_scrutin_amendement(objet=objet, statut="rejete"))
    assert p is not None and p.startswith("Le sous-amendement a été rejeté")


def test_resultat_amendement_main_levee():
    p = phrase_resultat_amendement(_scrutin_amendement(public=False))
    assert p == "L'amendement a été adopté à main levée (pas de décompte des voix)."


def test_resultat_amendement_absent_si_en_cours():
    assert phrase_resultat_amendement(_scrutin_amendement(statut="en_cours")) is None


async def test_questions_amendement_sans_llm_seul_le_resultat():
    q = await generer_questions_amendement(_scrutin_amendement(), None)
    assert q.resultat is not None
    assert q.pourquoi is None and q.changement is None


async def test_questions_amendement_avec_llm_reponses_validees():
    llm = _FakeLLM(
        f"{PREFIXE_AUTEUR_AMENDEMENT}, l'encadrement doit aussi couvrir les "
        "communes moyennes.",
        "Le seuil de 50 000 habitants passerait à 20 000 habitants.",
    )
    q = await generer_questions_amendement(_scrutin_amendement(), llm)
    assert q.pourquoi is not None and q.pourquoi.startswith(PREFIXE_AUTEUR_AMENDEMENT)
    assert q.changement is not None


async def test_questions_amendement_pourquoi_sans_prefixe_rejete():
    llm = _FakeLLM(
        "L'encadrement doit aussi couvrir les communes moyennes.",  # pas d'attribution
        "Le seuil de 50 000 habitants passerait à 20 000 habitants.",
    )
    q = await generer_questions_amendement(_scrutin_amendement(), llm)
    assert q.pourquoi is None
    assert q.changement is not None


async def test_questions_amendement_chiffre_invente_rejete():
    llm = _FakeLLM(
        f"{PREFIXE_AUTEUR_AMENDEMENT}, cela concernerait 3 000 communes.",  # 3 000 absent
        "Le seuil de 50 000 habitants passerait à 20 000 habitants.",
    )
    q = await generer_questions_amendement(_scrutin_amendement(), llm)
    assert q.pourquoi is None
    assert q.changement is not None


async def test_questions_amendement_sans_contenu_pas_d_appel_llm():
    llm = _FakeLLM("ne doit pas être consommé")
    q = await generer_questions_amendement(
        _scrutin_amendement(dispositif=None, expose=None), llm
    )
    assert q.pourquoi is None and q.changement is None
    assert llm._reponses  # LLM non appelé : rien à générer sans source (§2.5)


# --- generer_desaccord : Q2 depuis les explications de vote ---

_INTERVENTIONS = [
    ("La France insoumise", "pour", "Nous voterons ce texte qui protège les victimes."),
    ("Rassemblement National", "contre", "Nous voterons contre car le dispositif est inapplicable."),
]


async def test_desaccord_paraphrase_par_groupe_sens_preserve():
    llm = _FakeLLM(
        "Ce texte protège mieux les victimes.",
        "Le dispositif proposé serait inapplicable.",
    )
    args = await generer_desaccord(_INTERVENTIONS, llm)
    assert [a.groupe for a in args] == ["La France insoumise", "Rassemblement National"]
    # Le sens vient du scrutin, pas du LLM : il est conservé tel quel.
    assert [a.sens.value for a in args] == ["pour", "contre"]
    assert all(a.argument for a in args)


async def test_desaccord_argument_distordu_est_omis():
    # Le 1er argument invente un chiffre absent de l'explication → rejeté ;
    # le 2e est valide → conservé (un rejet ne bloque pas les autres).
    llm = _FakeLLM(
        "Ce texte concerne 42 millions de personnes.",
        "Le dispositif proposé serait inapplicable.",
    )
    args = await generer_desaccord(_INTERVENTIONS, llm)
    assert [a.groupe for a in args] == ["Rassemblement National"]


async def test_desaccord_sans_llm_est_vide():
    assert await generer_desaccord(_INTERVENTIONS, None) == []
