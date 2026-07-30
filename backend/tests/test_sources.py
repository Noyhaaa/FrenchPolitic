"""Les documents d'un dossier (§7.5) — composition pure, sans réseau ni base.

La fiche n'affichait qu'un lien, la page du dossier législatif, alors que le
payload portait déjà le texte déposé, le compte rendu, le texte voté et
Légifrance — chacun enfermé dans la carte qui s'en sert. Ces tests fixent l'ordre
dans lequel la liste les rassemble, et ce qu'elle refuse de dupliquer.
"""
from __future__ import annotations

from app.domain.sources import (
    LIBELLE_LEGIFRANCE,
    base_du_dossier,
    documents_du_dossier,
)
from app.schemas import (
    DispositifTexte,
    Dossier,
    EtatTexte,
    ExposeMotifs,
    QuestionsCitoyennes,
    ResumeScrutin,
    SourceOfficielle,
    TexteAdopte,
)

_URL_DOSSIER = "https://www.assemblee-nationale.fr/dyn/17/dossiers/DLR5L17N50001"
_URL_TEXTE = "https://www.assemblee-nationale.fr/dyn/17/textes/l17b0763_proposition-loi"
_URL_RAPPORT = "https://www.assemblee-nationale.fr/dyn/docs/RAPPANR5L17B0912"
_URL_CR = "https://www.assemblee-nationale.fr/dyn/17/comptes-rendus/seance/CRS1"
_URL_TA = "https://www.assemblee-nationale.fr/dyn/17/textes/l17t0075_texte-adopte-seance"
_URL_LEGIFRANCE = "https://www.legifrance.gouv.fr/jorf/id/JORFTEXT000051234567"


def _source(libelle: str, url: str, type_: str = "texte") -> SourceOfficielle:
    return SourceOfficielle(type=type_, libelle=libelle, url=url)


def _resume(**kwargs) -> ResumeScrutin:
    return ResumeScrutin(
        titre_clair="Améliorer la sécurité des trains",
        resume=[],
        confiance="moyenne",
        relu_par_humain=False,
        **kwargs,
    )


def _dossier(**kwargs) -> Dossier:
    """Dossier minimal — seuls les champs qui portent des documents varient."""
    base = dict(
        id="DLR5L17N50001",
        titre_officiel="Proposition de loi visant à améliorer la sécurité des trains",
        titre_clair="Améliorer la sécurité des trains",
        statut="adopte",
        theme="Transports",
        temps_lecture_sec=30,
        date_dernier_scrutin="2026-01-15T10:00:00Z",
        sources=[_source("Dossier législatif", _URL_DOSSIER)],
        resume=_resume(),
    )
    base.update(kwargs)
    return Dossier(**base)


def _complet() -> Dossier:
    """Un dossier qui porte les six documents (le cas d'une loi promulguée)."""
    return _dossier(
        expose_motifs=ExposeMotifs(
            texte="Les agressions se multiplient dans les transports.",
            source=_source("Texte déposé", _URL_TEXTE),
        ),
        dispositif=DispositifTexte(
            texte="Article 1er — Les agents sont habilités à…",
            # ⚠️ MÊME URL que l'exposé : les deux sortent du même PDF.
            source=_source("Texte déposé", _URL_TEXTE),
        ),
        rapports_commission=[
            _source("Rapport de la commission (n° 912)", _URL_RAPPORT)
        ],
        texte_adopte=TexteAdopte(
            texte="Article 1er — …",
            source=_source("Texte voté par le Parlement", _URL_TA),
        ),
        etat=EtatTexte(
            etat="promulgue",
            numero_loi="2025-379",
            url_legifrance=_URL_LEGIFRANCE,
        ),
        resume=_resume(
            questions=QuestionsCitoyennes(
                desaccord_source=_source(
                    "Compte rendu de la séance (Assemblée nationale)",
                    _URL_CR,
                    type_="debats",
                )
            )
        ),
    )


def test_les_documents_suivent_la_vie_du_texte():
    """Dossier → texte déposé → rapport → compte rendu → texte voté → en vigueur.

    Cet ordre-là plutôt que l'ordre d'arrivée : il se lit comme le parcours du
    texte, et il est le même d'un dossier à l'autre.
    """
    documents = documents_du_dossier(_complet())
    assert [s.url for s in documents] == [
        _URL_DOSSIER,
        _URL_TEXTE,
        _URL_RAPPORT,
        _URL_CR,
        _URL_TA,
        _URL_LEGIFRANCE,
    ]


def test_un_document_absent_ne_decale_rien():
    """Un dossier sans rapport ni compte rendu garde l'ordre des autres.

    Rien n'est comblé, rien n'est annoncé comme manquant : la place reste vide
    (§2.5)."""
    dossier = _complet()
    dossier.rapports_commission = []
    dossier.resume.questions = None
    assert [s.url for s in documents_du_dossier(dossier)] == [
        _URL_DOSSIER,
        _URL_TEXTE,
        _URL_TA,
        _URL_LEGIFRANCE,
    ]


def test_exposé_et_dispositif_du_meme_pdf_ne_font_quun_lien():
    """Les deux sortent du même document : deux entrées « Texte déposé »
    identiques laisseraient croire à deux textes (176 dossiers concernés)."""
    documents = documents_du_dossier(_complet())
    assert [s.url for s in documents].count(_URL_TEXTE) == 1


def test_le_compte_rendu_est_un_debat_pas_un_texte():
    """Son type porte l'icône : six 📄 d'affilée ne distingueraient rien."""
    documents = documents_du_dossier(_complet())
    compte_rendu = next(s for s in documents if s.url == _URL_CR)
    assert compte_rendu.type == "debats"
    assert all(s.type == "texte" for s in documents if s.url != _URL_CR)


def test_le_lien_legifrance_porte_le_libelle_de_la_carte_la_loi():
    """La carte « La loi » et la liste montrent la même URL : sous deux libellés
    différents, elles laisseraient croire à deux textes — c'est justement la
    raison pour laquelle ce lien avait quitté la liste."""
    documents = documents_du_dossier(_complet())
    assert documents[-1].libelle == LIBELLE_LEGIFRANCE == "Texte en vigueur (Légifrance)"


def test_un_dossier_sans_rien_de_plus_garde_sa_seule_source():
    """Aucun document supplémentaire → la liste ne bouge pas. On ne fabrique pas
    de lien pour étoffer (§2.5)."""
    dossier = _dossier()
    assert documents_du_dossier(dossier) == dossier.sources


def test_le_repli_sur_les_sources_des_scrutins_est_preserve():
    """Un dossier reconstitué (« TXT-… ») n'a pas de page officielle : sa base
    est la liste des scrutins qui l'ont formé, et elle survit à la composition."""
    scrutins = [
        _source("Scrutin", "https://an.fr/scrutins/1", type_="scrutin"),
        _source("Scrutin", "https://an.fr/scrutins/2", type_="scrutin"),
    ]
    dossier = _dossier(sources=list(scrutins))
    assert documents_du_dossier(dossier) == scrutins


def test_la_composition_est_idempotente():
    """Rejouée sur son propre résultat, elle rend la même liste.

    C'est ce qui permet de la recomposer à chaque run comme au rattrapage
    (`python -m app.ingestion.sources`) sans que rien ne s'empile.
    """
    dossier = _complet()
    une_fois = documents_du_dossier(dossier)
    dossier.sources = une_fois
    assert documents_du_dossier(dossier) == une_fois


def test_un_document_disparu_quitte_la_liste():
    """Un désaccord effacé par `revalider` emporte le compte rendu qui l'avait
    produit : sans quoi la liste continuerait d'annoncer une source que le
    dossier ne porte plus.

    Le dédoublonnage par URL ne suffirait pas — il ne voit que ce qu'on ajoute,
    d'où la reconnaissance des libellés composés dans `base_du_dossier`.
    """
    dossier = _complet()
    dossier.sources = documents_du_dossier(dossier)
    dossier.resume.questions = None
    assert _URL_CR not in {s.url for s in documents_du_dossier(dossier)}


def test_la_base_est_la_seule_chose_qui_ne_se_recalcule_pas():
    """`base_du_dossier` isole la page du dossier ; tout le reste est recomposé."""
    dossier = _complet()
    dossier.sources = documents_du_dossier(dossier)
    assert [s.url for s in base_du_dossier(dossier)] == [_URL_DOSSIER]
