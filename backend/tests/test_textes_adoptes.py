"""Le texte définitivement voté — la « petite loi » (pur, sans réseau).

Ce que ces tests protègent, c'est surtout la **discipline des URLs** : côté Sénat,
la numérotation redémarre à chaque session, si bien qu'une année approchée d'un
cran attrape un texte sans aucun rapport (cas mesuré : `tas24-159` est une
résolution européenne sur la subsidiarité). On dérive, on ne devine pas (§2.5).
"""
from __future__ import annotations

from app.ingestion.textes_adoptes import (
    construire_index_publications_ta,
    construire_texte_adopte,
    decouper_loi,
    ref_texte_loi,
    urls_texte_adopte,
)

# En-tête réel d'une petite loi de l'Assemblée (extraction pypdf, espaces
# compris) : rien de tout cela n'est de la loi.
_ENTETE = (
    " TEXTE ADOPTÉ n°  173 « Petite loi » __ ASSEMBLÉE NATIONALE CONSTITUTION DU "
    "4 OCTOBRE 1958 DIX-SEPTIÈME LÉGISLATURE 15 octobre 2025 PROJET DE LOI "
    "autorisant la ratification de la convention n° 155 (Texte définitif) "
    "L’Assemblée nationale a adopté, dans les conditions prévues à l’article 45 "
    "(alinéas 2 et 3) de la Constitution, le projet de loi dont la teneur suit : "
    "Voir les numéros : Sénat : 688 (2023-2024) et T.A. 55 (2024-2025). – 2 – "
)


def _acte_promulgation(ref: str | None) -> dict:
    decision: dict = {"codeActe": "PROM-PUB", "dateActe": "2026-07-13T00:00:00+02:00"}
    if ref is not None:
        decision["texteLoiRef"] = ref
    return {
        "acteLegislatif": [
            {"codeActe": "AN1", "actesLegislatifs": None},
            {"codeActe": "PROM", "actesLegislatifs": {"acteLegislatif": decision}},
        ]
    }


# ---------------------------------------------------------------------------
# Quel texte est celui de la loi
# ---------------------------------------------------------------------------


def test_la_reference_du_texte_de_loi_vient_de_l_archive():
    assert (
        ref_texte_loi(_acte_promulgation("PIONANR5L17BTA0075"))
        == "PIONANR5L17BTA0075"
    )


def test_sans_reference_on_ne_choisit_pas_de_texte():
    """Ces dossiers portent pourtant 2 à 4 textes adoptés (un par lecture, dans
    chaque chambre) : en élire un serait choisir à la place de la source. Mesuré,
    le plus récent est parfois la version *modifiée par le Sénat*, qui n'est pas
    la loi."""
    assert ref_texte_loi(_acte_promulgation(None)) is None
    assert ref_texte_loi(None) is None


# ---------------------------------------------------------------------------
# Dérivation des URLs
# ---------------------------------------------------------------------------


def test_url_assemblee_zero_paddee_sur_quatre_chiffres():
    page, pdf = urls_texte_adopte("PIONANR5L17BTA0075", None)
    assert page == (
        "https://www.assemblee-nationale.fr/dyn/17/textes/"
        "l17t0075_texte-adopte-seance"
    )
    assert pdf == page + ".pdf"


def test_url_assemblee_ne_depend_pas_de_la_date():
    """La législature est dans l'uid : un texte de l'Assemblée n'a pas besoin de
    sa date de publication, contrairement au Sénat."""
    assert urls_texte_adopte("PRJLANR5L17BTA0173", None) is not None


def test_url_senat_prend_l_annee_de_session():
    """La session court d'octobre à septembre : un texte publié en juillet 2026
    appartient à la session 2025-2026, donc « tas25 » — pas « tas26 »."""
    page, pdf = urls_texte_adopte("PRJLSNR5S459BTA0040", "2026-07-09T00:00:00+02:00")
    assert page == "https://www.senat.fr/leg/tas25-040.html"
    assert pdf == "https://www.senat.fr/leg/tas25-040.pdf"


def test_url_senat_en_janvier_appartient_a_la_session_precedente():
    page, _ = urls_texte_adopte("PRJLSNR5S459BTA0040", "2025-01-23T00:00:00+01:00")
    assert page == "https://www.senat.fr/leg/tas24-040.html"


def test_url_senat_impossible_sans_date():
    """Sans la date, l'année de session ne se déduit pas — et l'approcher d'un
    cran attraperait un autre texte. On n'invente pas d'URL (§2.5)."""
    assert urls_texte_adopte("PRJLSNR5S459BTA0040", None) is None


def test_page_senat_porte_son_extension():
    """L'URL nue répond 404 côté Sénat : offrir ce lien au lecteur, c'est offrir
    un 404 (§7.5)."""
    page, _ = urls_texte_adopte("PIONSNR5S459BTA0124", "2025-05-19T00:00:00+02:00")
    assert page.endswith(".html")


def test_uid_qui_nest_pas_un_texte_adopte():
    # Un texte DÉPOSÉ (pas de « BTA ») n'est pas la loi.
    assert urls_texte_adopte("PIONANR5L17B0369", None) is None


# ---------------------------------------------------------------------------
# Découpage
# ---------------------------------------------------------------------------


def test_le_decoupage_commence_au_premier_article():
    """L'en-tête d'une petite loi est administratif — et contient « l'article 45
    de la Constitution », que la casse permet justement de ne pas confondre avec
    un titre d'article."""
    corps = decouper_loi(_ENTETE + "Article unique " + "Est autorisée " * 30)
    assert corps is not None
    assert corps.startswith("Article unique")
    assert "TEXTE ADOPTÉ" not in corps
    assert "Texte définitif" not in corps


def test_article_premier_numerote_reconnu():
    """L'extraction pypdf sépare parfois l'exposant : « Article 1 er »."""
    corps = decouper_loi(_ENTETE + "Article 1 er Le code pénal " + "est modifié " * 30)
    assert corps is not None
    assert corps.startswith("Article 1 er")


def test_sans_article_rien_n_est_attache():
    assert decouper_loi(_ENTETE) is None


def test_corps_trop_court_rejete():
    assert decouper_loi(_ENTETE + "Article unique Ceci est court.") is None


def test_corps_trop_long_nest_pas_tronque():
    """Budget, PLFSS : au-delà du cap on n'attache **rien**. Le corps sert de
    source à la Q4, et un modèle qui ne verrait que les premiers articles
    présenterait un bout de loi comme le tout (§2.5)."""
    assert decouper_loi("Article unique " + "x" * 20_000) is None


# ---------------------------------------------------------------------------
# Assemblage
# ---------------------------------------------------------------------------


def test_le_lien_est_pose_meme_sans_pdf_lisible():
    """Le lien et le corps sont dissociés à dessein : le lecteur peut atteindre
    la loi votée (§7.5) même quand nous ne savons pas la lire. Mesuré : 76 liens
    pour 45 corps."""
    ta = construire_texte_adopte("https://exemple.fr/l17t0075", None)
    assert ta.texte is None
    assert ta.source.url == "https://exemple.fr/l17t0075"
    assert ta.source.libelle == "Texte voté par le Parlement"


# ---------------------------------------------------------------------------
# Index des dates de publication
# ---------------------------------------------------------------------------


def test_index_ne_retient_que_les_textes_adoptes():
    index = construire_index_publications_ta(
        [
            {
                "document": {
                    "uid": "PRJLSNR5S459BTA0040",
                    "cycleDeVie": {"chrono": {"datePublication": "2025-01-23T00:00:00+01:00"}},
                }
            },
            # Un texte déposé : hors sujet ici.
            {
                "uid": "PIONANR5L17B0369",
                "cycleDeVie": {"chrono": {"datePublication": "2025-02-01T00:00:00+01:00"}},
            },
            # Un texte adopté sans date : inutilisable, donc absent.
            {"uid": "PIONSNR5S459BTA0124", "cycleDeVie": {"chrono": {}}},
        ]
    )
    assert index == {"PRJLSNR5S459BTA0040": "2025-01-23T00:00:00+01:00"}
