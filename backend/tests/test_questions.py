"""Tests des 4 questions citoyennes (génération gardée + repli §2.5)."""
from __future__ import annotations

from app.ai.questions import (
    PREFIXE_AUTEUR,
    accroche_depuis_q1,
    PREFIXE_AUTEUR_AMENDEMENT,
    generer_desaccord,
    generer_questions,
    generer_questions_amendement,
    phrase_resultat,
    phrase_resultat_amendement,
    valider_argument,
    valider_reponse,
)
from app.schemas import (
    DispositifTexte,
    ResultatGlobal,
    Scrutin,
    ScrutinResume,
    SourceOfficielle,
    TexteAdopte,
)


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


# --- Garde-fous « rien d'ajouté » : gloses et déposant ---------------------
#
# Les deux cas ci-dessous viennent d'une réponse RÉELLE trouvée en base sur
# l'amendement n° 7 du Gouvernement au projet de loi agricole (acétamipride) :
# le modèle y requalifiait le Gouvernement en « député » ET développait « Anses »
# en le confondant avec l'ANSM. Aucun contrôle ne les attrapait.

_OBJET_GOUVERNEMENT = (
    "l'amendement n° 7 du Gouvernement au projet de loi d'urgence pour la "
    "protection et la souveraineté agricoles (texte de la commission mixte "
    "paritaire)"
)
_EXPOSE_ANSES = (
    "Dans le cadre légal inchangé d'interdiction de l'acétamipride, le présent "
    "amendement allonge à six mois le délai dont dispose l'Anses pour se "
    "prononcer sur les dérogations."
)
_SOURCES_ANSES = f"{_OBJET_GOUVERNEMENT}\n{_EXPOSE_ANSES}"


def test_rejette_une_glose_absente_de_la_source():
    # « Anses » n'est jamais développé dans la source — et ce développement-ci
    # est celui de l'ANSM, une autre agence.
    r = (
        "Selon son auteur, cet amendement donne plus de temps à l'Anses "
        "(Agence nationale de sécurité du médicament et des produits de santé)."
    )
    assert valider_reponse(r, _SOURCES_ANSES, prefixe=PREFIXE_AUTEUR_AMENDEMENT) is None


def test_accepte_une_parenthese_presente_dans_la_source():
    # Une parenthèse n'est pas suspecte en soi : seule compte son absence.
    r = (
        "Selon son auteur, il modifie le texte de la commission mixte paritaire "
        "(texte de la commission mixte paritaire)."
    )
    assert valider_reponse(r, _SOURCES_ANSES, prefixe=PREFIXE_AUTEUR_AMENDEMENT) == r


def test_glose_comparee_sans_accents_ni_ponctuation():
    # « (a l'article 8) » doit passer si la source écrit « à l'article 8 ».
    sources = "l'amendement n° 4 de M. Durand à l'article 8 du projet de loi"
    r = "Cet amendement modifierait une règle (à l'article 8)."
    assert valider_reponse(r, sources) == r


def test_rejette_le_gouvernement_requalifie_en_depute():
    r = (
        "Selon son auteur, le député a proposé cet amendement pour allonger le "
        "délai dont dispose l'Anses."
    )
    assert valider_reponse(
        r,
        _SOURCES_ANSES,
        prefixe=PREFIXE_AUTEUR_AMENDEMENT,
        deposant="gouvernement",
    ) is None


def test_accepte_le_mot_depute_s_il_est_dans_la_source():
    # Le contrôle interdit d'AJOUTER une qualité d'auteur, pas de reprendre la
    # source : si l'exposé parle des députés, la réponse peut le faire aussi.
    sources = f"{_OBJET_GOUVERNEMENT}\nLes députés ont demandé un délai plus long."
    r = "Selon son auteur, les députés ont demandé un délai plus long."
    assert (
        valider_reponse(
            r, sources, prefixe=PREFIXE_AUTEUR_AMENDEMENT, deposant="gouvernement"
        )
        == r
    )


def test_le_gouvernement_peut_etre_cite_dans_un_amendement_parlementaire():
    # Contrôle ASYMÉTRIQUE : l'exposé d'un amendement de député mentionne
    # légitimement le Gouvernement — rien à rejeter là.
    sources = (
        "l'amendement n° 12 de M. Durand à la proposition de loi visant à agir\n"
        "Le Gouvernement n'a pas répondu à cette demande."
    )
    r = "Selon son auteur, le Gouvernement n'a pas répondu à cette demande."
    assert (
        valider_reponse(
            r, sources, prefixe=PREFIXE_AUTEUR_AMENDEMENT, deposant="parlementaire"
        )
        == r
    )


def test_sans_deposant_connu_aucune_requalification_n_est_jugee():
    # Source muette sur le déposant → on ne tranche pas (§2.5).
    r = "Selon son auteur, le député a demandé un délai plus long."
    sources = "l'amendement n° 12 à l'article 3\nUn délai plus long est demandé."
    assert (
        valider_reponse(r, sources, prefixe=PREFIXE_AUTEUR_AMENDEMENT, deposant=None)
        == r
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


def _motion_censure(
    pour: int = 267, requis: int | None = 289, statut: str = "rejete"
) -> ScrutinResume:
    """Une motion de censure telle que l'archive la publie : SEULES les voix
    favorables sont recensées (art. 49), donc contre et abstention à zéro."""
    return ScrutinResume(
        id="MOC",
        date="2025-10-16",
        objet=(
            "la motion de censure déposée en application de l'article 49, "
            "alinéa 2, de la Constitution"
        ),
        statut=statut,
        scrutin_public=True,
        type_vote="motion_censure",
        suffrages_requis=requis,
        resultat=ResultatGlobal(pour=pour, contre=0, abstention=0, non_votants=14),
    )


def test_resultat_motion_de_censure_ne_dit_jamais_zero_voix():
    """Régression : la formule générale place le camp GAGNANT en premier, et sur
    un rejet le gagnant est « contre ». Elle écrivait donc « rejeté par 0 voix
    contre 267 » — l'inverse du fait, puisque 267 députés avaient voté POUR la
    censure. C'était le cas de TOUTES les motions en base."""
    p = phrase_resultat([_motion_censure()])
    assert p == (
        "La motion de censure a recueilli 267 voix sur les 289 requises ; "
        "elle n'a pas été adoptée."
    )
    assert "0 voix" not in p
    assert "contre" not in p


def test_resultat_motion_adoptee_dit_ce_qu_elle_emporte():
    p = phrase_resultat([_motion_censure(pour=289, statut="adopte")])
    assert p is not None and "renversé" in p


def test_resultat_motion_sans_seuil_ne_devine_pas():
    """Seuil absent de la source → on s'en tient aux voix recueillies (§2.5)."""
    p = phrase_resultat([_motion_censure(requis=None)])
    assert p == "La motion de censure a recueilli 267 voix ; elle n'a pas été adoptée."


def test_un_vote_ordinaire_garde_sa_phrase_mot_pour_mot():
    """Non-régression : la branche « motion » ne doit toucher aucun des
    8 400 autres scrutins."""
    p = phrase_resultat([_scrutin("l'ensemble de la proposition de loi…")])
    assert p == "Le texte a été adopté par 55 voix contre 0, avec 5 abstentions."


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


# --- Q4 : le dispositif officiel prime sur la parole de l'auteur ---

_DISPOSITIF_TEXTE = DispositifTexte(
    texte=(
        "Article 1er. Après l'article 15-3 du code de procédure pénale, il est "
        "inséré un article 15-3-5 ainsi rédigé : « La victime dont la plainte "
        "est classée sans suite en est informée par écrit. »"
    ),
    source=SourceOfficielle(
        type="texte",
        libelle="Texte déposé",
        url="https://www.assemblee-nationale.fr/dyn/17/textes/l17b0001_proposition-loi",
    ),
)


async def test_q4_depuis_le_dispositif_est_un_fait_non_attribue():
    llm = _FakeLLM(
        "Le texte obligerait à informer par écrit la victime dont la plainte "
        "est classée sans suite.",
        "Les députés ont examiné une proposition de loi sur les droits des victimes.",
    )
    q = await generer_questions(
        _TITRE,
        [_scrutin("l'ensemble…")],
        _EXPOSE,
        llm,
        dispositif=_DISPOSITIF_TEXTE,
    )
    assert q.changement is not None
    # Pas d'attribution : la source n'est pas un point de vue mais le texte…
    assert not q.changement.startswith(PREFIXE_AUTEUR)
    # …et elle porte son lien vers ce texte (§7.5).
    assert q.changement_source == _DISPOSITIF_TEXTE.source
    # L'exposé n'a servi qu'à la Q1 : la réponse « auteur » n'est pas demandée.
    assert q.pourquoi is not None
    assert not llm._reponses


async def test_q4_repli_sur_l_auteur_si_le_dispositif_est_rejete():
    # Chiffre absent du dispositif → réponse factuelle rejetée ; on retombe sur
    # l'exposé, et la réponse redevient attribuée (sans source).
    llm = _FakeLLM(
        "Le texte concernerait 12 000 victimes par an.",
        "Les députés ont examiné une proposition de loi sur les droits des victimes.",
        f"{PREFIXE_AUTEUR}, cela permettrait de mieux protéger les victimes.",
    )
    q = await generer_questions(
        _TITRE,
        [_scrutin("l'ensemble…")],
        _EXPOSE,
        llm,
        dispositif=_DISPOSITIF_TEXTE,
    )
    assert q.changement is not None and q.changement.startswith(PREFIXE_AUTEUR)
    assert q.changement_source is None


async def test_q4_sans_expose_mais_avec_dispositif():
    # Un texte sans exposé récupérable garde une réponse : celle du texte.
    llm = _FakeLLM("Le texte obligerait à informer la victime par écrit.")
    q = await generer_questions(
        _TITRE, [_scrutin("l'ensemble…")], None, llm, dispositif=_DISPOSITIF_TEXTE
    )
    assert q.changement is not None
    assert q.changement_source is not None
    assert q.pourquoi is None  # pas d'exposé → pas de Q1 (§2.5)


_TEXTE_ADOPTE = TexteAdopte(
    texte=(
        "Article unique Le procureur informe par écrit la victime dont la "
        "plainte est classée sans suite des motifs de sa décision."
    ),
    source=SourceOfficielle(
        type="texte",
        libelle="Texte voté par le Parlement",
        url=(
            "https://www.assemblee-nationale.fr/dyn/17/textes/"
            "l17t0075_texte-adopte-seance"
        ),
    ),
)


async def test_q4_prend_la_loi_votee_avant_le_texte_depose():
    """Le dispositif déposé décrit une version que la navette a modifiée : sur une
    loi en vigueur, c'est le texte VOTÉ qui fait foi. Un seul appel au modèle —
    le dispositif n'est pas même essayé."""
    llm = _FakeLLM(
        "La loi oblige le procureur à informer par écrit la victime dont la "
        "plainte est classée sans suite.",
        "Les députés ont examiné une proposition de loi sur les droits des victimes.",
    )
    q = await generer_questions(
        _TITRE,
        [_scrutin("l'ensemble…")],
        _EXPOSE,
        llm,
        dispositif=_DISPOSITIF_TEXTE,
        texte_adopte=_TEXTE_ADOPTE,
    )
    assert q.changement is not None
    # Un fait, donc aucune attribution — et à l'indicatif, puisque ça s'applique.
    assert not q.changement.startswith(PREFIXE_AUTEUR)
    assert q.changement.startswith("La loi oblige")
    # La source est la loi votée, pas le texte déposé (§7.5).
    assert q.changement_source == _TEXTE_ADOPTE.source
    assert not llm._reponses


async def test_q4_redescend_sur_le_texte_depose_si_la_loi_est_rejetee():
    """Chiffre absent de la loi votée → réponse rejetée, on redescend d'un
    barreau. L'échelle ne casse pas, elle se dégrade proprement (§2.5)."""
    llm = _FakeLLM(
        "La loi concerne 12 000 victimes par an.",
        "Le texte obligerait à informer par écrit la victime.",
        "Les députés ont examiné une proposition de loi sur les droits des victimes.",
    )
    q = await generer_questions(
        _TITRE,
        [_scrutin("l'ensemble…")],
        _EXPOSE,
        llm,
        dispositif=_DISPOSITIF_TEXTE,
        texte_adopte=_TEXTE_ADOPTE,
    )
    assert q.changement is not None
    assert q.changement_source == _DISPOSITIF_TEXTE.source


async def test_un_texte_adopte_sans_corps_ne_sert_pas_de_source():
    """31 lois sur 76 n'ont que le lien (corps hors cap) : la Q4 reste celle du
    texte déposé, le lien vers la loi votée existe quand même."""
    sans_corps = TexteAdopte(source=_TEXTE_ADOPTE.source)
    llm = _FakeLLM(
        "Le texte obligerait à informer par écrit la victime.",
        "Les députés ont examiné une proposition de loi sur les droits des victimes.",
    )
    q = await generer_questions(
        _TITRE,
        [_scrutin("l'ensemble…")],
        _EXPOSE,
        llm,
        dispositif=_DISPOSITIF_TEXTE,
        texte_adopte=sans_corps,
    )
    assert q.changement_source == _DISPOSITIF_TEXTE.source


def test_les_sauts_de_ligne_sont_normalises():
    """Le modèle livre parfois une phrase par ligne ; les cartes rendent un
    paragraphe. Purement cosmétique — aucun mot n'est touché."""
    valide = valider_reponse("La loi interdit ceci.\nElle crée cela.", _SOURCES)
    assert valide == "La loi interdit ceci. Elle crée cela."


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


async def test_desaccord_argument_fabrique_est_omis():
    """Une phrase plausible mais sans rapport avec ce que le groupe a dit est
    rejetée par l'ancrage lexical.

    Cas réel mesuré en base : « …le texte ne répond pas aux attentes des Français
    en matière de sécurité et d'immigration », servi tel quel sur des dossiers
    sans rapport (dont un texte sur les honoraires d'expert-comptable) et attribué
    à un groupe qui avait voté POUR. Aucun contrôle de forme ne l'attrapait : pas
    de chiffre, pas de lexique évaluatif, pas de parenthèse. §7.4 interdit
    précisément de mettre une opinion dans la bouche d'un groupe.
    """
    llm = _FakeLLM(
        "Le groupe estime que le texte ne répond pas aux attentes des Français "
        "en matière de sécurité et d'immigration.",
        "Le dispositif proposé serait inapplicable.",
    )
    args = await generer_desaccord(_INTERVENTIONS, llm)
    assert [a.groupe for a in args] == ["Rassemblement National"]


async def test_desaccord_paraphrase_fidele_passe_l_ancrage():
    """L'ancrage compare des racines : reformuler avec d'autres flexions passe."""
    interventions = [
        (
            "Groupe Un",
            "pour",
            "Cette proposition de loi rétablit le remboursement par l'État des "
            "frais d'expertise comptable engagés par les candidats pour la "
            "certification de leur compte de campagne.",
        )
    ]
    llm = _FakeLLM(
        "Le groupe veut rembourser aux candidats les frais de certification "
        "comptable de leur campagne."
    )
    args = await generer_desaccord(interventions, llm)
    assert len(args) == 1 and args[0].groupe == "Groupe Un"


def test_valider_argument_est_la_regle_unique():
    """Génération et revalidation hors ligne doivent juger à l'identique, sinon
    un run réintroduit ce que `revalider` vient d'effacer."""
    prononce = "Nous voterons contre car le dispositif est inapplicable."
    assert valider_argument("Le dispositif serait inapplicable.", prononce)
    assert valider_argument("Le texte trahit les attentes du monde agricole.", prononce) is None


def test_accroche_retire_l_amorce_de_la_q1():
    # L'amorce imposée au modèle ne dit rien sur une carte : elle saute.
    assert (
        accroche_depuis_q1(
            "Les députés ont examiné cette proposition de loi pour améliorer la "
            "sécurité dans les transports. Le texte crée de nouvelles sanctions."
        )
        == "Améliorer la sécurité dans les transports."
    )
    # Variante « car » (et mention de l'Assemblée) : même traitement.
    assert (
        accroche_depuis_q1(
            "Les députés ont examiné ce texte à l'Assemblée nationale car il "
            "propose de nationaliser ArcelorMittal France."
        )
        == "Il propose de nationaliser ArcelorMittal France."
    )


def test_accroche_sans_amorce_reconnue_garde_la_phrase():
    assert (
        accroche_depuis_q1("Le texte réforme le mode de scrutin municipal. Suite.")
        == "Le texte réforme le mode de scrutin municipal."
    )


def test_accroche_passe_a_la_phrase_suivante_si_la_premiere_ne_dit_rien():
    # « Les députés ont examiné cette proposition de résolution. » = amorce seule.
    assert (
        accroche_depuis_q1(
            "Les députés ont examiné cette proposition de résolution. "
            "Elle demande la libération de prisonniers détenus arbitrairement."
        )
        == "Elle demande la libération de prisonniers détenus arbitrairement."
    )


def test_accroche_absente_sans_q1():
    assert accroche_depuis_q1(None) is None
    assert accroche_depuis_q1("   ") is None


def test_accroche_coupe_sur_un_mot_entier():
    longue = "Les députés ont examiné ce texte pour " + "réformer le droit " * 20
    accroche = accroche_depuis_q1(longue)
    assert accroche is not None
    assert len(accroche) <= 160 and accroche.endswith("…")
    assert not accroche[:-1].endswith(" ")  # pas de mot coupé en deux


def test_lexique_de_la_source_admis_seulement_si_le_mot_y_figure():
    """Un texte officiel a le droit d'employer ses propres mots.

    Cas réel : « l'exposition des jeunes utilisateurs aux contenus dangereux »
    est écrit dans l'article unique d'une proposition de résolution — le
    reprendre n'est pas un jugement ajouté par le modèle."""
    source = (
        "Article unique. Est créée une commission d'enquête chargée d'examiner "
        "les risques liés à l'exposition aux contenus dangereux."
    )
    reponse = "Le texte créerait une commission sur les contenus dangereux."
    # Par défaut, la liste noire s'applique sans exception.
    assert valider_reponse(reponse, source) is None
    # Source officielle : le mot y figure tel quel → accepté.
    assert (
        valider_reponse(reponse, source, lexique_de_la_source_admis=True) == reponse
    )
    # Mais un jugement AJOUTÉ par le modèle reste rejeté.
    assert (
        valider_reponse(
            "Le texte créerait une commission indispensable.",
            source,
            lexique_de_la_source_admis=True,
        )
        is None
    )
