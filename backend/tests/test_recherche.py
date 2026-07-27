"""Tests des fonctions pures de recherche (§3.3) : termes, index, pertinence."""
from __future__ import annotations

from app.domain.recherche import (
    SCORE_ACCROCHE,
    SCORE_AUTRE,
    SCORE_TITRE,
    SCORE_TITRE_EXACT,
    ChampsRecherche,
    index_recherche,
    score,
    termes,
)
from app.data.seed import SEED_DOSSIERS


def _champs(
    titre_clair="Encadrer les loyers",
    titre_officiel="Proposition de loi visant à encadrer les loyers",
    accroche="Plafonne les hausses de loyer.",
    theme="Logement",
    index=None,
) -> ChampsRecherche:
    if index is None:
        index = f"{titre_clair} {titre_officiel} {accroche} {theme}".lower()
    return ChampsRecherche(
        titre_clair=titre_clair,
        titre_officiel=titre_officiel,
        accroche=accroche,
        theme=theme,
        index=index,
    )


# --- Découpage de la requête ---------------------------------------------


def test_termes_plie_et_decoupe():
    assert termes("Logement Social") == ["logement", "social"]
    assert termes("ÉNERGIE") == ["energie"]  # accents et casse indifférents


def test_termes_ecarte_les_mots_trop_courts():
    # « de », « la », « à » ne discriminent rien et ramèneraient tout.
    assert termes("aide a mourir") == ["aide", "mourir"]
    assert termes("   ") == []
    assert termes("") == []


# --- Index ----------------------------------------------------------------


def test_index_couvre_les_reponses_citoyennes():
    # Le dossier « loyers » du seed porte une Q1/Q4 : c'est là que vit le
    # vocabulaire du lecteur, absent du titre officiel.
    dossier = next(d for d in SEED_DOSSIERS if d.theme == "Logement")
    idx = index_recherche(dossier)
    assert "zones tendues" in idx  # vient de la Q1
    assert "renovations" in idx  # vient de la Q4, plié sans accent
    assert "particuliers" in idx  # vient des publics concernés
    assert dossier.theme.lower() in idx


def test_index_exclut_l_expose_des_motifs():
    # L'exposé est long et argumentatif : indexé, il ramenait 41 % du corpus sur
    # une requête comme « fin de vie ». Il reste hors de l'index (§3.3).
    dossier = next((d for d in SEED_DOSSIERS if d.expose_motifs), None)
    if dossier is None:
        return  # le seed n'a pas d'exposé : rien à prouver ici
    assert dossier.expose_motifs.texte.lower()[:40] not in index_recherche(dossier)


# --- Pertinence -----------------------------------------------------------


def test_score_requete_absente_de_l_index():
    assert score(_champs(), ["narcotrafic"]) == 0
    assert score(_champs(), []) == 0  # requête vide → non pertinent


def test_score_phrase_exacte_dans_le_titre_prime():
    c = _champs()
    assert score(c, termes("encadrer les loyers"), "encadrer les loyers") == (
        SCORE_TITRE_EXACT
    )


def test_score_tous_les_termes_dans_le_titre():
    c = _champs()
    # Mots présents dans les titres mais pas côte à côte : c'est précisément le
    # cas que l'ancienne recherche (LIKE d'un bloc) ne trouvait pas.
    assert score(c, termes("loi loyers"), "loi loyers") == SCORE_TITRE


def test_score_accroche_et_theme_sous_le_titre():
    c = _champs()
    assert score(c, termes("plafonne hausses"), "plafonne hausses") == SCORE_ACCROCHE
    assert score(c, termes("logement"), "logement") == SCORE_ACCROCHE


def test_score_reponses_citoyennes_en_dernier():
    c = _champs(index="encadrer les loyers logement zones tendues renovations")
    assert score(c, termes("zones tendues"), "zones tendues") == SCORE_AUTRE
    # Et l'ordre des niveaux est bien celui attendu.
    assert SCORE_TITRE_EXACT > SCORE_TITRE > SCORE_ACCROCHE > SCORE_AUTRE
