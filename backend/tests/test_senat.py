"""Parsing des scrutins publics du Sénat (pur, sans réseau).

Les fragments HTML ci-dessous reproduisent la structure réelle des pages
`senat.fr/scrutin-public/{session}/scr{session}-{n}.html` (relevée sur des
scrutins réels de la session 2025-2026), y compris ses pièges : espaces
insécables entre un libellé et son deux-points, et le fragment
« accordion-collapse » qui apparaît DANS l'en-tête d'un groupe avant d'ouvrir
le conteneur des noms.
"""
from __future__ import annotations

import pytest

from app.domain.enums import Chambre, PositionVote
from app.ingestion.dossiers_legislatifs import (
    JointureSenat,
    Reconciliation,
    construire_jointure_senat,
    legislature_du_ref,
)
from app.ingestion.normalize import auteur_amendement, est_amendement, numero_amendement
from app.ingestion.senat import (
    article_vise_senat,
    auteur_amendement_senat,
    numeros_de_session,
    parse_page_scrutin,
    parse_scrutin_senat,
    session_pour,
)
from app.ingestion.senateurs import (
    InfoSenateur,
    build_senateurs,
    construire_annuaire,
    groupes_senat,
    votes_du_scrutin_senat,
)
from app.ingestion.sync import build_dossier


def _bloc_groupe(
    code: str,
    nom: str,
    effectif: int,
    pour: int,
    contre: int,
    abstentions: int,
    nppv: int,
) -> str:
    """Un bloc « analyse par groupe », au format réel de la page."""
    return f"""
<div class="accordion-item">
<div id="accordion-scrutin-{code}" class="accordion-header">
<div role="button" class="accordion-button collapsed" data-bs-toggle="collapse"
 data-bs-target="#accordion-collapse-scrutin-{code}" aria-expanded="false"
 aria-controls="accordion-collapse-{code}">
<div class="flex-grow-1 me-2">
<h3 class="accordion-title fs-5">{nom}&nbsp;:
{effectif}<span class="visually-hidden">s&eacute;nateurs</span></h3>
<ul class="list-inline mb-0" aria-label="D&eacute;tail des votants pour le Groupe">
<li class="list-inline-item"><svg aria-hidden="true"></svg>Pour&nbsp;:
<span class="ms-1 fw-semibold">{pour}</span></li>
<li class="list-inline-item"><svg aria-hidden="true"></svg>Contre&nbsp;:
<span class="ms-1 fw-semibold">{contre}</span></li>
<li class="list-inline-item"><svg aria-hidden="true"></svg>Abstentions&nbsp;:
<span class="ms-1 fw-semibold">{abstentions}</span></li>
<li class="list-inline-item"><svg aria-hidden="true"></svg>N'ont
pas pris part au vote&nbsp;: <span class="ms-1 fw-semibold">{nppv}</span></li>
</ul></div></div></div>
<div id="accordion-collapse-scrutin-{code}" class="accordion-collapse collapse">
<p>Pour&nbsp;: Mme Une Senatrice, M. Un Autre</p>
</div>
</div>"""


def _page(
    numero: int,
    date: str,
    objet: str,
    sort: str = "Adopt&eacute;",
    slug: str | None = "pjl25-689",
    pour: int = 214,
    contre: int = 111,
    abstention: int = 20,
    nppv: int = 3,
    groupes: str = "",
) -> str:
    lien = (
        f'<li><a href="/dossier-legislatif/{slug}.html">Le dossier'
        f" l&eacute;gislatif</a></li>"
        if slug
        else ""
    )
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"></head><body>
<h1 class="page-title">
    Scrutin n&deg;{numero} - s&eacute;ance du {date}
</h1>
<p class="page-lead">{objet}</p>
<p class="hstack gap-1 my-2"><span class="badge rounded-pill text-bg-success">{sort}</span></p>
<ul class="list-links">{lien}</ul>
<div class="card-header"><h2 class="card-title">R&eacute;sultat du scrutin</h2></div>
<ul class="list-unstyled row"><li class="col"><strong class="display-4 ff-alt">348</strong>
votants</li>
<li class="col"><strong class="display-4 ff-alt">325</strong>
suffrages exprim&eacute;s</li>
<li class="col"><strong class="display-4 ff-alt text-tertiary">{pour}</strong>
pour</li>
<li class="col"><strong class="display-4 ff-alt text-primary">{contre}</strong>
contre</li>
</ul>
<ul class="list-inline text-center"><li class="list-inline-item fs-sm">Abstention&nbsp;:
<span class="fw-semibold">{abstention}</span></li>
<li class="list-inline-item fs-sm">N'ont pas pris part au vote&nbsp;:
<span class="fw-semibold">{nppv}</span></li>
</ul>
<h2>Analyse par groupes politiques</h2>
<div class="accordion">{groupes}</div>
</body></html>"""


_GROUPES_HTML = (
    _bloc_groupe("UMP", "Groupe Les R&eacute;publicains", 131, 125, 0, 4, 2)
    + _bloc_groupe("SOC", "Groupe Socialiste", 64, 0, 60, 4, 0)
    + _bloc_groupe("UC", "Groupe Union Centriste", 59, 52, 1, 5, 1)
)

_OBJET_ENSEMBLE = (
    "sur l'ensemble du projet de loi d'urgence pour la protection et la "
    "souverainet&eacute; agricoles"
)


@pytest.fixture
def annuaire() -> dict[str, InfoSenateur]:
    return construire_annuaire(
        [
            {
                "matricule": "21071F",
                "prenom": "Marie-Do",
                "nom": "Aeschlimann",
                "groupe": {
                    "code": "UMP",
                    "libelle": "Groupe Les Républicains",
                    "libelleCourt": "Les Républicains",
                },
                "circonscription": {"libelle": "Hauts-de-Seine"},
                "urlAvatar": "/senimg/aeschlimann_marie_do21071f_carre.jpg",
            },
            {
                "matricule": "19760E",
                "prenom": "Jocelyne",
                "nom": "Antoine",
                "groupe": {
                    "code": "UC",
                    "libelle": "Groupe Union Centriste",
                    "libelleCourt": "UC",
                },
                "circonscription": {"libelle": "Meuse"},
                "urlAvatar": None,
            },
        ]
    )


# --------------------------------------------------------------------------
# Session parlementaire (le piège des URLs)
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("annee", "mois", "attendu"),
    [
        (2026, 7, 2025),   # juillet 2026 → session 2025-2026
        (2026, 9, 2025),   # septembre : encore la session précédente
        (2025, 10, 2025),  # octobre : ouverture de la session
        (2025, 12, 2025),
        (2026, 1, 2025),
    ],
)
def test_session_est_celle_du_debut_de_session(annee, mois, attendu):
    """L'année des URLs du Sénat est celle du DÉBUT de session (oct.→sept.).

    Sans ça on demande `scr2026.html` en juillet 2026 et on récolte un 404 —
    alors que le scrutin du jour est bien `scr2025-340`.
    """
    assert session_pour(annee, mois) == attendu


def test_numeros_de_session_du_plus_recent_au_plus_ancien():
    index = """
    <a href="2025/scr2025-1.html">1</a>
    <a href="2025/scr2025-12.html">12</a>
    <a href="2025/scr2025-340.html">340</a>
    <a href="2025/scr2025-12.html">doublon</a>
    """
    assert numeros_de_session(index, 2025) == [340, 12, 1]


# --------------------------------------------------------------------------
# Page d'un scrutin
# --------------------------------------------------------------------------


def test_parse_vote_sur_ensemble():
    page = parse_page_scrutin(
        _page(340, "21 juillet 2026", _OBJET_ENSEMBLE, groupes=_GROUPES_HTML), 2025
    )
    assert page is not None
    assert page.numero == 340
    assert page.session == 2025
    assert page.date == "2026-07-21"
    assert page.statut == "adopte"
    assert page.slug_dossier == "pjl25-689"
    assert page.id == "SEN-2025-340"
    # Le préfixe « sur » propre au Sénat est retiré : l'objet prend alors
    # exactement la forme de ceux de l'Assemblée, et tout l'aval s'y applique.
    assert page.objet.startswith("l'ensemble du projet de loi")


def test_decomptes_globaux_malgre_les_espaces_insecables():
    """L'abstention et les non-votants vivent après un « &nbsp;: »."""
    page = parse_page_scrutin(_page(340, "21 juillet 2026", _OBJET_ENSEMBLE), 2025)
    assert page is not None
    assert page.resultat.pour == 214
    assert page.resultat.contre == 111
    assert page.resultat.abstention == 20
    assert page.resultat.non_votants == 3


def test_analyse_par_groupe_ne_capte_pas_la_liste_des_noms():
    """Les décomptes viennent de l'en-tête, pas du bloc replié des noms.

    « Pour : » réapparaît plus bas pour introduire la liste nominative : une
    coupure trop tardive ferait lire ces noms comme des décomptes.
    """
    page = parse_page_scrutin(
        _page(340, "21 juillet 2026", _OBJET_ENSEMBLE, groupes=_GROUPES_HTML), 2025
    )
    assert page is not None
    assert [g.code for g in page.groupes] == ["UMP", "SOC", "UC"]
    ump = page.groupes[0]
    assert ump.nom == "Groupe Les Républicains"
    assert (ump.pour, ump.contre, ump.abstention, ump.non_votants) == (125, 0, 4, 2)


def test_decomptes_par_groupe_somment_au_resultat_global():
    """Contrôle de cohérence : c'est la propriété vérifiée sur les pages réelles
    (les décomptes officiels par groupe reconstituent exactement le total)."""
    page = parse_page_scrutin(
        _page(
            340,
            "21 juillet 2026",
            _OBJET_ENSEMBLE,
            pour=177,
            contre=61,
            abstention=13,
            nppv=3,
            groupes=_GROUPES_HTML,
        ),
        2025,
    )
    assert page is not None
    assert sum(g.pour for g in page.groupes) == page.resultat.pour
    assert sum(g.contre for g in page.groupes) == page.resultat.contre
    assert sum(g.abstention for g in page.groupes) == page.resultat.abstention
    assert sum(g.non_votants for g in page.groupes) == page.resultat.non_votants


def test_page_sans_reperes_est_ecartee():
    """Mieux vaut sauter un scrutin que d'en fabriquer un à moitié (§2.5)."""
    assert parse_page_scrutin("<html><body>rien</body></html>", 2025) is None
    # Sort illisible → on n'invente pas « adopté ».
    sans_badge = _page(1, "1 octobre 2025", _OBJET_ENSEMBLE).replace(
        '<span class="badge rounded-pill text-bg-success">Adopt&eacute;</span>', ""
    )
    assert parse_page_scrutin(sans_badge, 2025) is None


def test_sort_rejete():
    page = parse_page_scrutin(
        _page(1, "8 octobre 2025", _OBJET_ENSEMBLE, sort="Rejet&eacute;"), 2025
    )
    assert page is not None and page.statut == "rejete"


# --------------------------------------------------------------------------
# Objets d'amendement
# --------------------------------------------------------------------------

_OBJET_AMENDEMENT = (
    "sur l'amendement n&deg; 441 rectifi&eacute;, pr&eacute;sent&eacute; par "
    "M. Marc Dupont, &agrave; l'article 8 du projet de loi portant "
    "simplification des normes applicables aux collectivit&eacute;s territoriales"
)

_OBJET_IDENTIQUES = (
    "sur les amendements identiques n&deg; 154 rectifi&eacute;, "
    "pr&eacute;sent&eacute; par M. Bernard Delcros et plusieurs de ses "
    "coll&egrave;gues, n&deg; 207 rectifi&eacute; bis, pr&eacute;sent&eacute; "
    "par M. Yves Bleunven et plusieurs de ses coll&egrave;gues, et n&deg; 410, "
    "pr&eacute;sent&eacute; par le Gouvernement, &agrave; l'article 2 du projet "
    "de loi visant la relance et la d&eacute;centralisation du logement"
)


def test_amendement_simple_numero_auteur_et_article():
    page = parse_page_scrutin(
        _page(320, "23 juin 2026", _OBJET_AMENDEMENT, sort="Rejet&eacute;"), 2025
    )
    assert page is not None
    assert est_amendement(page.objet)
    assert numero_amendement(page.objet) == "441"
    # Le Sénat écrit prénom ET nom (l'Assemblée, le nom seul) : on restitue ce
    # qui est écrit, sans reformuler (§2.5).
    assert auteur_amendement_senat(page.objet) == "M. Marc Dupont"
    # L'article visé est cité par l'objet lui-même côté Sénat (côté Assemblée
    # il vient de l'archive des amendements).
    assert article_vise_senat(page.objet) == "Article 8"


def test_amendements_identiques_sans_numero_ni_auteur():
    """Un vote sur plusieurs amendements ne désigne AUCUN numéro à lui seul.

    Cas propre au Sénat, absent des objets de l'Assemblée. En retenir un seul
    laisserait croire que le vote ne portait que sur celui-là (§2.5).
    """
    page = parse_page_scrutin(
        _page(330, "7 juillet 2026", _OBJET_IDENTIQUES, sort="Rejet&eacute;"), 2025
    )
    assert page is not None
    assert est_amendement(page.objet)
    assert numero_amendement(page.objet) is None
    assert auteur_amendement_senat(page.objet) is None
    assert article_vise_senat(page.objet) == "Article 2"


def test_sous_amendement_garde_son_numero():
    """Le garde-fou « pluriel » ne doit pas casser le cas du sous-amendement,
    qui cite légitimement DEUX numéros (le sien et celui de son parent)."""
    objet = "le sous-amendement n° 3 de M. Durand à l'amendement n° 80 de Mme Petit"
    assert numero_amendement(objet) == "3"
    assert auteur_amendement(objet) == "M. Durand"


# --------------------------------------------------------------------------
# Cascade de rattachement au dossier
# --------------------------------------------------------------------------


def _page_ensemble(slug: str | None = "pjl25-689"):
    page = parse_page_scrutin(
        _page(340, "21 juillet 2026", _OBJET_ENSEMBLE, slug=slug, groupes=_GROUPES_HTML),
        2025,
    )
    assert page is not None
    return page


def test_rattachement_par_dossier_ref_resolu_en_amont():
    """Niveau 1/2 : l'appelant a résolu le dossier de l'Assemblée."""
    parse = parse_scrutin_senat(_page_ensemble(), dossier_ref="DLR5L17N54085")
    assert parse.dossier_id == "DLR5L17N54085"
    assert parse.dossier_ref == "DLR5L17N54085"
    assert parse.scrutin.chambre is Chambre.senat


def test_rattachement_par_titre():
    """Niveau 3 : le titre cité par l'objet retrouve le dossier officiel."""
    reconciliation = Reconciliation(
        _ref_par_titre={
            "projet de loi d'urgence pour la protection et la souverainete agricoles": (
                "DLR5L17N54085"
            )
        },
        _ref_par_signature={},
    )
    parse = parse_scrutin_senat(_page_ensemble(), reconciliation=reconciliation)
    assert parse.dossier_id == "DLR5L17N54085"


def test_dossier_d_origine_senatoriale():
    """Niveau 4 : pas de dossier AN → dossier propre, à identifiant stable.

    Le slug du Sénat est stable d'un vote à l'autre : deux scrutins du même
    texte se rangent donc sous le même dossier, sans hachage de titre.
    """
    parse = parse_scrutin_senat(_page_ensemble())
    assert parse.dossier_id == "SEN-pjl25-689"
    assert parse.dossier_ref is None
    # Le dossier garde une source officielle de son niveau : sa page au Sénat.
    assert parse.source_dossier is not None
    assert parse.source_dossier.url.endswith("/dossier-legislatif/pjl25-689.html")


def test_scrutin_sans_dossier_est_son_propre_dossier():
    """Niveau 5 : ni texte cité ni dossier → événement autonome."""
    page = parse_page_scrutin(
        _page(12, "3 d&eacute;cembre 2025", "sur la motion r&eacute;f&eacute;rendaire", slug=None),
        2025,
    )
    assert page is not None
    parse = parse_scrutin_senat(page)
    assert parse.dossier_id == "SEN-2025-12"
    assert parse.source_dossier is None


# --------------------------------------------------------------------------
# Vote nominatif et doctrine de la délégation de vote
# --------------------------------------------------------------------------

_VOTES = {
    "votes": [
        {"matricule": "21071F", "vote": "p", "siege": 138},
        {"matricule": "19760E", "vote": "c", "siege": 38},
        # Matricule absent de l'annuaire : omis plutôt qu'affiché en référence
        # machine (§2.5) — le décompte officiel du groupe reste, lui, affiché.
        {"matricule": "00000X", "vote": "p", "siege": 1},
    ]
}


def test_votants_nommes_et_cliquables_seulement_si_connus(annuaire):
    connus = frozenset({"SEN-21071F"})
    parse = parse_scrutin_senat(
        _page_ensemble(), _VOTES, annuaire, senateurs_connus=connus
    )
    par_id = {g.groupe_id: g for g in parse.scrutin.positions_groupes}

    ump = par_id["SEN-UMP"]
    assert [v.nom for v in ump.votants_pour or []] == ["Marie-Do Aeschlimann"]
    assert (ump.votants_pour or [])[0].depute_id == "SEN-21071F"
    # Le décompte affiché reste le chiffre OFFICIEL du groupe (125), pas la
    # longueur de la liste (1) : l'écart est visible plutôt que masqué.
    assert ump.pour == 125

    uc = par_id["SEN-UC"]
    assert [v.nom for v in uc.votants_contre or []] == ["Jocelyne Antoine"]
    # Siège encore mais hors du référentiel servi → pas de lien (jamais de 404).
    assert (uc.votants_contre or [])[0].depute_id is None

    # Le matricule inconnu n'apparaît nulle part.
    tous = [
        v.nom
        for g in parse.scrutin.positions_groupes
        for liste in (g.votants_pour, g.votants_contre, g.votants_abstention)
        for v in liste or []
    ]
    assert not any("00000X" in n for n in tous)


def test_aucune_cohesion_au_senat(annuaire):
    """La délégation de vote par groupe vide la cohésion de son sens (§7.4)."""
    parse = parse_scrutin_senat(_page_ensemble(), _VOTES, annuaire)
    assert all(g.cohesion is None for g in parse.scrutin.positions_groupes)


def test_aucun_contre_son_groupe_au_senat(annuaire):
    """Même quand un sénateur vote à l'inverse de son groupe, le fait n'est pas
    posé : la source ne distingue pas un scrutin ordinaire (bulletins déposés
    par un délégué) d'un scrutin à la tribune."""
    votes = {
        "votes": [
            # Vote CONTRE alors que son groupe (UMP) est massivement POUR.
            {"matricule": "21071F", "vote": "c"},
            {"matricule": "19760E", "vote": "p"},
        ]
    }
    lignes = votes_du_scrutin_senat(votes, annuaire)
    assert {ligne.acteur_ref for ligne in lignes} == {"SEN-21071F", "SEN-19760E"}
    assert all(ligne.contre_son_groupe is None for ligne in lignes)


def test_position_majoritaire_deduite_des_decomptes():
    """Le Sénat ne publie pas ce champ (l'Assemblée si) : on le calcule."""
    parse = parse_scrutin_senat(_page_ensemble())
    par_id = {g.groupe_id: g for g in parse.scrutin.positions_groupes}
    assert par_id["SEN-UMP"].position_majoritaire is PositionVote.pour
    assert par_id["SEN-SOC"].position_majoritaire is PositionVote.contre


def test_groupe_sans_position_exploitable():
    """Aucun vote exprimé, ou égalité parfaite → pas de position majoritaire."""
    page = parse_page_scrutin(
        _page(
            1,
            "8 octobre 2025",
            _OBJET_ENSEMBLE,
            groupes=(
                _bloc_groupe("NI", "Non inscrits", 4, 0, 0, 0, 4)
                + _bloc_groupe("RDSE", "Groupe RDSE", 17, 8, 8, 1, 0)
            ),
        ),
        2025,
    )
    assert page is not None
    parse = parse_scrutin_senat(page)
    par_id = {g.groupe_id: g for g in parse.scrutin.positions_groupes}
    assert par_id["SEN-NI"].position_majoritaire is PositionVote.non_votant
    assert par_id["SEN-RDSE"].position_majoritaire is PositionVote.non_votant


# --------------------------------------------------------------------------
# Référentiel des sénateurs
# --------------------------------------------------------------------------


def test_referentiel_senateurs(annuaire):
    senateurs = {s.id: s for s in build_senateurs(annuaire)}
    marie = senateurs["SEN-21071F"]
    assert marie.nom == "Marie-Do Aeschlimann"
    assert marie.chambre is Chambre.senat
    assert marie.groupe_id == "SEN-UMP"
    assert marie.circonscription == "Hauts-de-Seine"
    # L'annuaire ne publie pas le début de mandat : absent, jamais deviné (§2.5).
    assert marie.depuis is None
    # La photo est DONNÉE par la source (pas dérivée) : URL absolue directe.
    assert marie.portrait_url == (
        "https://www.senat.fr/senimg/aeschlimann_marie_do21071f_carre.jpg"
    )
    # Photo non publiée → None, l'app affiche les initiales.
    assert senateurs["SEN-19760E"].portrait_url is None


def test_groupes_du_senat(annuaire):
    groupes = {g.id: g for g in groupes_senat(annuaire)}
    assert set(groupes) == {"SEN-UMP", "SEN-UC"}
    assert groupes["SEN-UMP"].nom == "Groupe Les Républicains"
    assert groupes["SEN-UMP"].couleur.startswith("#")


def test_annuaire_ignore_les_entrees_incompletes():
    annuaire = construire_annuaire(
        [
            {"matricule": "", "prenom": "X", "nom": "Y"},
            {"matricule": "12345A", "prenom": "", "nom": ""},
            "pas un dict",
        ]
    )
    assert annuaire == {}


# --------------------------------------------------------------------------
# Jointure Assemblée ↔ Sénat
# --------------------------------------------------------------------------

_DOSSIERS = [
    {
        "dossierParlementaire": {
            "uid": "DLR5L17N54085",
            "titreDossier": {
                "titre": "Projet de loi d'urgence…",
                "titreChemin": "projet_loi_urgence_protection_souverainete_agricoles",
                "senatChemin": "http://www.senat.fr/dossier-legislatif/pjl25-689.html",
            },
        }
    },
    {
        "dossierParlementaire": {
            "uid": "DLR5L17N54608",
            "titreDossier": {
                "titre": "Relance et décentralisation du logement",
                "titreChemin": "PJL_relance_decentralisation_logement_2",
                "senatChemin": None,
            },
        }
    },
]


def test_jointure_par_chemin_senat():
    jointure = construire_jointure_senat(_DOSSIERS)
    assert jointure.ref_pour_slug_senat("pjl25-689") == "DLR5L17N54085"
    # Tolère l'URL complète comme le slug nu (les deux formes circulent).
    assert (
        jointure.ref_pour_slug_senat("/dossier-legislatif/pjl25-689.html")
        == "DLR5L17N54085"
    )
    assert jointure.ref_pour_slug_senat("pjl25-999") is None
    assert jointure.ref_pour_slug_senat(None) is None


def test_jointure_inverse_par_url_de_l_assemblee():
    """Quand l'archive AN ne connaît pas le dossier Sénat, c'est le Sénat qui
    cite l'Assemblée. La casse diffère entre les deux sources."""
    jointure = construire_jointure_senat(_DOSSIERS)
    assert (
        jointure.ref_pour_url_an(
            "http://www.assemblee-nationale.fr/17/dossiers/"
            "PJL_relance_decentralisation_logement_2.asp"
        )
        == "DLR5L17N54608"
    )
    # L'URL moderne porte déjà le dossierRef : reconnu sans passer par l'index.
    assert (
        jointure.ref_pour_url_an(
            "https://www.assemblee-nationale.fr/dyn/17/dossiers/DLR5L17N54085"
        )
        == "DLR5L17N54085"
    )
    assert jointure.ref_pour_url_an("https://exemple.fr/rien") is None


def test_jointure_s_abstient_en_cas_d_ambiguite():
    """Un slug qui désignerait deux dossiers n'en désigne aucun (§2.5)."""
    jointure = construire_jointure_senat(
        _DOSSIERS
        + [
            {
                "dossierParlementaire": {
                    "uid": "DLR5L16N40000",
                    "titreDossier": {
                        "senatChemin": (
                            "http://www.senat.fr/dossier-legislatif/pjl25-689.html"
                        )
                    },
                }
            }
        ]
    )
    assert jointure.ref_pour_slug_senat("pjl25-689") is None


def test_jointure_vide_ne_casse_rien():
    jointure = JointureSenat(_ref_par_slug_senat={}, _ref_par_slug_an={})
    assert len(jointure) == 0
    assert jointure.ref_pour_slug_senat("pjl25-689") is None


# --------------------------------------------------------------------------
# L'URL du dossier à l'Assemblée
# --------------------------------------------------------------------------


def test_legislature_lue_dans_le_dossier_ref():
    """La législature vient du `dossierRef`, jamais du vote qui l'a amené.

    Régression vécue : un run où un dossier n'était touché QUE par des votes du
    Sénat produisait « /dyn/2025/dossiers/DLR5L17N54085 » — 2025 étant la
    *session* sénatoriale, prise pour une législature. L'URL était morte.
    """
    assert legislature_du_ref("DLR5L17N54085") == "17"
    assert legislature_du_ref("DLR5L16N47697") == "16"
    assert legislature_du_ref("TXT-abcdef") is None
    assert legislature_du_ref("SEN-pjl25-689") is None
    assert legislature_du_ref(None) is None


def test_source_dossier_juste_meme_sans_vote_de_l_assemblee():
    """Un dossier de l'Assemblée touché uniquement par des votes du Sénat garde
    l'URL de SA législature."""
    parse = parse_scrutin_senat(_page_ensemble(), dossier_ref="DLR5L17N54085")
    # Le parse sénatorial transporte la session (2025) là où l'AN met sa
    # législature : c'est précisément ce qu'il ne faut pas propager dans l'URL.
    assert parse.legislature == "2025"
    dossier = build_dossier([parse])
    assert dossier.sources[0].url == (
        "https://www.assemblee-nationale.fr/dyn/17/dossiers/DLR5L17N54085"
    )
