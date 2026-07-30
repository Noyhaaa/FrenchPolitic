"""Données de démonstration FICTIVES.

⚠️ Illustratives — à remplacer par l'ingestion open data AN + Légifrance (§5).
Servent de backend « memory » par défaut pour que l'app se branche sur l'API
sans dépendre d'une base. Unité : le dossier (texte) et ses scrutins.
"""
from __future__ import annotations

from app.domain.enums import Chambre, ObjetVote, PositionVote
from app.ingestion.normalize import type_objet_vote
from app.domain.sources import documents_du_dossier
from app.schemas import (
    Amendement,
    ChangementTexte,
    Depute,
    Dossier,
    EtatTexte,
    ExposeMotifs,
    GroupeListItem,
    Initiative,
    MiseAJourDossier,
    PhaseScrutin,
    PhraseSourcee,
    PositionGroupe,
    QuestionsAmendement,
    QuestionsCitoyennes,
    ResultatGlobal,
    ResumeScrutin,
    Scrutin,
    ScrutinResume,
    SourceOfficielle,
    TexteAdopte,
    VoteDepute,
)

# Emoji d'illustration par thème (aligné sur le frontend).
THEME_EMOJI: dict[str, str] = {
    "Logement": "🏠",
    "Santé": "🏥",
    "Fiscalité": "💶",
    "Énergie": "⚡",
    "Éducation": "🏫",
    "Environnement": "🌱",
    "Justice": "⚖️",
    "Travail": "🧰",
    "Autre": "🏛️",
}

_GROUPES = {
    "RE": ("Renaissance", "#F5A623"),
    "RN": ("Rass. National", "#1B3A5C"),
    "LFI": ("La France Insoumise", "#C0392B"),
    "LR": ("Les Républicains", "#2E6FB5"),
    "SOC": ("Socialistes", "#E24A6E"),
    "ECO": ("Écologistes", "#2F8F4E"),
}

# Groupes du Sénat (fictifs eux aussi). Identifiants préfixés comme à
# l'ingestion : les deux chambres partagent les tables, jamais les ids.
_GROUPES_SENAT = {
    "SEN-UC": ("Union Centriste (Sénat)", "#6EC1E4"),
    "SEN-SOC": ("Socialistes (Sénat)", "#E24A6E"),
    "SEN-LR": ("Les Républicains (Sénat)", "#2E6FB5"),
}


def _grp(
    gid: str,
    position: str,
    pour: int,
    contre: int,
    abst: int,
    cohesion: float | None,
):
    nom, couleur = _GROUPES[gid]
    return PositionGroupe(
        groupe_id=gid,
        groupe_nom=nom,
        couleur=couleur,
        position_majoritaire=position,
        pour=pour,
        contre=contre,
        abstention=abst,
        cohesion=cohesion,
    )


def _grp_senat(gid: str, position: str, pour: int, contre: int, abst: int):
    """Position d'un groupe du Sénat — **sans cohésion**.

    Au Sénat les bulletins d'un scrutin public ordinaire sont déposés par un
    délégué pour tout le groupe : une cohésion calculée là-dessus mesurerait la
    procédure, pas les votes (§7.4). Le seed reflète donc ce que l'ingestion
    produit réellement.
    """
    nom, couleur = _GROUPES_SENAT[gid]
    return PositionGroupe(
        groupe_id=gid,
        groupe_nom=nom,
        couleur=couleur,
        position_majoritaire=position,
        pour=pour,
        contre=contre,
        abstention=abst,
        cohesion=None,
    )


def _sources(*types: str) -> list[SourceOfficielle]:
    libelle = {
        "texte": "Texte de loi",
        "amendements": "Amendements",
        "debats": "Débats",
        "scrutin": "Scrutin",
    }
    url = {
        "texte": "https://www.legifrance.gouv.fr/",
        "amendements": "https://www.assemblee-nationale.fr/",
        "debats": "https://www.assemblee-nationale.fr/",
        "scrutin": "https://www.assemblee-nationale.fr/",
    }
    return [SourceOfficielle(type=t, libelle=libelle[t], url=url[t]) for t in types]


# Sous-amendement (fictif) de l'amendement n° 12 du dossier logement — partagé
# entre la fiche dossier (section Sous-amendements) et le scrutin de son parent.
_SOUS_AM_01 = Amendement(
    id="sam-01",
    numero="3",
    objet="Abaisse le seuil d'encadrement aux communes de plus de 15 000 habitants",
    sort="rejete",
    scrutin_id="scr-2026-0412-sam1",
)

# Détail complet des votes (servis par GET /scrutins/{id}). La fiche dossier,
# elle, n'embarque que des résumés (liste compacte cliquable). Pas de nominatif
# dans le seed : on n'invente pas des noms de votants cohérents avec les
# décomptes (§2.5) — le nominatif vient des données réellement ingérées.
SEED_SCRUTINS: list[Scrutin] = [
    Scrutin(
        id="scr-2026-0412b",
        dossier_id="dos-logement-2026",
        date="2026-07-08T14:30:00Z",
        objet="Vote sur l'ensemble du texte (première lecture)",
        statut="adopte",
        scrutin_public=True,
        resultat=ResultatGlobal(pour=310, contre=231, abstention=24, non_votants=12),
        positions_groupes=[
            _grp("RE", "pour", 148, 8, 4, 0.92),
            _grp("RN", "contre", 12, 76, 0, 0.86),
            _grp("LFI", "pour", 68, 2, 1, 0.95),
            _grp("LR", "contre", 10, 48, 6, 0.75),
            _grp("SOC", "pour", 62, 1, 3, 0.94),
            _grp("ECO", "pour", 34, 0, 2, 0.94),
        ],
        sources=_sources("scrutin"),
    ),
    Scrutin(
        id="scr-2026-0412a",
        dossier_id="dos-logement-2026",
        date="2026-07-07T18:00:00Z",
        objet="Vote sur l'article 2 (encadrement des loyers)",
        statut="adopte",
        scrutin_public=True,
        resultat=ResultatGlobal(pour=298, contre=240, abstention=30, non_votants=9),
        positions_groupes=[
            _grp("RE", "pour", 140, 12, 8, 0.88),
            _grp("RN", "contre", 8, 78, 2, 0.88),
            _grp("LFI", "pour", 66, 2, 3, 0.93),
            _grp("LR", "contre", 12, 46, 6, 0.72),
            _grp("SOC", "pour", 60, 2, 4, 0.92),
            _grp("ECO", "pour", 33, 0, 3, 0.92),
        ],
        sources=_sources("scrutin"),
    ),
    # Votes d'amendement du dossier logement (apparaissent dans la section
    # « Amendements », pas dans la liste des votes du texte).
    Scrutin(
        id="scr-2026-0412-am1",
        dossier_id="dos-logement-2026",
        date="2026-07-07T15:00:00Z",
        objet="Amendement n° 12 — étendre l'encadrement aux communes de plus de 20 000 habitants",
        statut="adopte",
        scrutin_public=True,
        # Contenu enrichi (fictif) : ce que l'ingestion réelle tire de l'open
        # data AN. Le dispositif est factuel ; l'exposé sommaire est le point de
        # vue de l'auteur (bloc attribué, §4.3).
        cible="Article 2",
        dispositif=(
            "Au premier alinéa de l'article 2, le seuil de 50 000 habitants "
            "est remplacé par un seuil de 20 000 habitants."
        ),
        expose_sommaire=(
            "Les tensions locatives ne se limitent pas aux grandes villes : "
            "cet amendement étend l'encadrement des loyers aux communes "
            "moyennes."
        ),
        questions=QuestionsAmendement(
            pourquoi=(
                "Selon son auteur, les tensions sur les loyers ne se limitent "
                "pas aux grandes villes : l'amendement vise à couvrir aussi "
                "les communes moyennes."
            ),
            changement=(
                "L'encadrement des loyers s'appliquerait aussi aux communes "
                "de plus de 20 000 habitants."
            ),
            resultat=(
                "L'amendement a été adopté par 276 voix contre 254, avec "
                "38 abstentions."
            ),
        ),
        resultat=ResultatGlobal(pour=276, contre=254, abstention=38, non_votants=9),
        positions_groupes=[
            _grp("RE", "pour", 120, 30, 10, 0.70),
            _grp("RN", "contre", 4, 82, 2, 0.92),
            _grp("LFI", "pour", 68, 1, 2, 0.95),
            _grp("LR", "contre", 6, 52, 4, 0.82),
            _grp("SOC", "pour", 61, 1, 4, 0.93),
            _grp("ECO", "pour", 34, 0, 2, 0.94),
        ],
        sources=_sources("scrutin", "amendements"),
        sous_amendements=[_SOUS_AM_01],
    ),
    # Sous-amendement à l'amendement n° 12 (voté avant lui, rejeté).
    Scrutin(
        id="scr-2026-0412-sam1",
        dossier_id="dos-logement-2026",
        date="2026-07-07T14:30:00Z",
        objet=(
            "Sous-amendement n° 3 à l'amendement n° 12 — abaisser le seuil "
            "à 15 000 habitants"
        ),
        statut="rejete",
        scrutin_public=True,
        # Questions partielles : sans contenu enrichi, seules les réponses
        # déterministes existent — l'app affiche « information non
        # disponible » pour le reste (§2.5).
        questions=QuestionsAmendement(
            resultat=(
                "Le sous-amendement a été rejeté par 268 voix contre 188, "
                "avec 26 abstentions."
            ),
        ),
        resultat=ResultatGlobal(pour=188, contre=268, abstention=26, non_votants=12),
        positions_groupes=[
            _grp("RE", "contre", 18, 130, 12, 0.81),
            _grp("RN", "contre", 2, 84, 2, 0.95),
            _grp("LFI", "pour", 66, 2, 2, 0.94),
            _grp("LR", "contre", 8, 50, 4, 0.81),
            _grp("SOC", "pour", 60, 2, 4, 0.91),
            _grp("ECO", "pour", 34, 0, 2, 0.94),
        ],
        sources=_sources("scrutin", "amendements"),
    ),
    Scrutin(
        id="scr-2026-0412-am2",
        dossier_id="dos-logement-2026",
        date="2026-07-06T17:30:00Z",
        objet="Amendement n° 45 — exonérer les logements rénovés depuis moins de 3 ans",
        statut="rejete",
        scrutin_public=True,
        questions=QuestionsAmendement(
            resultat=(
                "L'amendement a été rejeté par 289 voix contre 232, avec "
                "41 abstentions."
            ),
        ),
        resultat=ResultatGlobal(pour=232, contre=289, abstention=41, non_votants=15),
        positions_groupes=[
            _grp("RE", "contre", 40, 108, 12, 0.68),
            _grp("RN", "pour", 70, 8, 4, 0.85),
            _grp("LFI", "contre", 2, 66, 3, 0.94),
            _grp("LR", "pour", 54, 6, 2, 0.86),
            _grp("SOC", "contre", 3, 60, 3, 0.92),
            _grp("ECO", "contre", 1, 33, 2, 0.94),
        ],
        sources=_sources("scrutin", "amendements"),
    ),
    # Vote du SÉNAT sur le même dossier que « scr-2026-0410 » : c'est la
    # démonstration de la jointure bicamérale (un texte, un dossier, deux
    # chambres). Pas de cohésion, pas de « contre son groupe » — cf. `_grp_senat`.
    Scrutin(
        id="SEN-2026-118",
        dossier_id="dos-energie-2026",
        date="2026-07-09T15:00:00Z",
        objet="L'ensemble du projet de loi relatif à la sobriété énergétique",
        statut="adopte",
        chambre="senat",
        scrutin_public=True,
        resultat=ResultatGlobal(pour=201, contre=112, abstention=25, non_votants=10),
        positions_groupes=[
            _grp_senat("SEN-LR", "pour", 120, 2, 6),
            _grp_senat("SEN-UC", "pour", 48, 1, 5),
            _grp_senat("SEN-SOC", "contre", 3, 60, 4),
        ],
        sources=[
            SourceOfficielle(
                type="scrutin",
                libelle="Scrutin",
                url="https://www.senat.fr/scrutin-public/2025/scr2025-118.html",
            )
        ],
    ),
    # Motion de censure — le cas où « X voix contre 0 » ne veut PAS dire ce
    # qu'il semble dire. L'article 49 de la Constitution ne fait recenser que
    # les voix FAVORABLES : `contre` et `abstention` sont à 0 par construction,
    # et seuls comptent les 267 voix face aux 289 requises. Les groupes qui ne
    # l'ont pas votée n'apparaissent donc pas « contre » mais sans position.
    Scrutin(
        id="scr-2026-0420",
        dossier_id="dos-censure-2026",
        date="2026-07-09T17:00:00Z",
        objet=(
            "la motion de censure déposée en application de l'article 49, "
            "alinéa 2, de la Constitution"
        ),
        statut="rejete",
        scrutin_public=True,
        type_vote="motion_censure",
        suffrages_requis=289,
        resultat=ResultatGlobal(pour=267, contre=0, abstention=0, non_votants=12),
        positions_groupes=[
            _grp("RN", "pour", 93, 0, 0, 1.0),
            _grp("LFI", "pour", 71, 0, 0, 1.0),
            _grp("SOC", "pour", 65, 0, 0, 1.0),
            _grp("ECO", "pour", 38, 0, 0, 1.0),
            _grp("RE", "non_votant", 0, 0, 0, None),
            _grp("LR", "non_votant", 0, 0, 0, None),
        ],
        sources=_sources("scrutin"),
    ),
    Scrutin(
        id="scr-2026-0410",
        dossier_id="dos-energie-2026",
        date="2026-07-07T16:00:00Z",
        objet="Vote sur l'ensemble du texte",
        statut="adopte",
        scrutin_public=True,
        resultat=ResultatGlobal(pour=401, contre=96, abstention=40, non_votants=40),
        positions_groupes=[
            _grp("RE", "pour", 152, 0, 8, 0.95),
            _grp("RN", "pour", 70, 4, 14, 0.80),
            _grp("LFI", "abstention", 20, 12, 39, 0.55),
            _grp("LR", "pour", 52, 2, 10, 0.81),
            _grp("SOC", "pour", 60, 0, 6, 0.91),
            _grp("ECO", "contre", 4, 28, 4, 0.78),
        ],
        sources=_sources("scrutin"),
    ),
    Scrutin(
        id="scr-2026-0405",
        dossier_id="dos-ecoles-2026",
        date="2026-07-06T11:15:00Z",
        objet="Vote sur l'ensemble du texte",
        statut="rejete",
        scrutin_public=True,
        resultat=ResultatGlobal(pour=214, contre=268, abstention=55, non_votants=40),
        positions_groupes=[
            _grp("RE", "contre", 6, 140, 14, 0.87),
            _grp("RN", "contre", 8, 70, 10, 0.80),
            _grp("LFI", "pour", 66, 0, 4, 0.94),
            _grp("LR", "contre", 12, 44, 8, 0.69),
            _grp("SOC", "pour", 62, 0, 4, 0.94),
            _grp("ECO", "pour", 34, 0, 2, 0.94),
        ],
        sources=_sources("scrutin"),
    ),
    Scrutin(
        id="scr-2026-0398",
        dossier_id="dos-sante-2026",
        date="2026-07-03T09:45:00Z",
        objet="Vote sur l'ensemble du texte",
        statut="adopte",
        scrutin_public=True,
        resultat=ResultatGlobal(pour=356, contre=120, abstention=61, non_votants=40),
        positions_groupes=[
            _grp("RE", "pour", 150, 2, 8, 0.93),
            _grp("RN", "abstention", 30, 10, 48, 0.55),
            _grp("LFI", "pour", 60, 6, 4, 0.85),
            _grp("LR", "pour", 44, 12, 8, 0.68),
            _grp("SOC", "pour", 58, 2, 6, 0.88),
            _grp("ECO", "pour", 32, 1, 3, 0.89),
        ],
        sources=_sources("scrutin"),
    ),
]

_SCRUTIN = {s.id: s for s in SEED_SCRUTINS}


def _resume_scrutin(scrutin_id: str) -> ScrutinResume:
    return ScrutinResume.from_scrutin(_SCRUTIN[scrutin_id])


SEED_DOSSIERS: list[Dossier] = [
    # Dossier à deux scrutins + badge « mis à jour » (démo de la navette, §7.7).
    Dossier(
        id="dos-logement-2026",
        titre_officiel=(
            "Proposition de loi visant à faciliter l'accès au logement "
            "et à encadrer les loyers"
        ),
        titre_clair="Faciliter l'accès au logement",
        accroche=(
            "Encadrer les loyers en zone tendue et accélérer la construction "
            "de logements sociaux."
        ),
        statut="en_cours",
        phase=PhaseScrutin(label="Adopté en 1re lecture", statut="adopte"),
        # Proposition de loi : l'auteur est un parlementaire, nommé et cliquable
        # parce qu'il siège encore (même règle que `Votant`).
        initiative=Initiative(
            origine="parlementaire",
            nom="Léa Marchand",
            depute_id="dep-seed-06",
            groupe_nom=_GROUPES["ECO"][0],
            groupe_couleur=_GROUPES["ECO"][1],
        ),
        theme="Logement",
        temps_lecture_sec=50,
        date_dernier_scrutin="2026-07-08T14:30:00Z",
        mise_a_jour=MiseAJourDossier(
            date="2026-07-08T14:30:00Z", label="Nouveau vote : sur l'ensemble"
        ),
        scrutins=[
            _resume_scrutin("scr-2026-0412b"),
            _resume_scrutin("scr-2026-0412a"),
        ],
        amendements=[
            Amendement(
                id="am-01",
                numero="12",
                objet="Étend l'encadrement aux communes de plus de 20 000 habitants",
                auteur="Groupe Écologiste",
                sort="adopte",
                cible="Article 2",
                dispositif=(
                    "Au premier alinéa de l'article 2, le seuil de 50 000 "
                    "habitants est remplacé par un seuil de 20 000 habitants."
                ),
                expose_sommaire=(
                    "Les tensions locatives ne se limitent pas aux grandes "
                    "villes : cet amendement étend l'encadrement des loyers "
                    "aux communes moyennes."
                ),
                scrutin_id="scr-2026-0412-am1",
                sous_amendements=[_SOUS_AM_01],
            ),
            Amendement(
                id="am-02",
                numero="45",
                objet="Exonère les logements rénovés depuis moins de 3 ans",
                auteur="Groupe LR",
                sort="rejete",
                scrutin_id="scr-2026-0412-am2",
            ),
        ],
        # Sources de niveau dossier uniquement (texte, débats) : la source de
        # chaque vote/amendement vit sur sa propre fiche — pas de doublon.
        sources=_sources("texte", "debats"),
        resume=ResumeScrutin(
            titre_clair="Faciliter l'accès au logement",
            resume=[
                PhraseSourcee(
                    phrase=(
                        "Le texte encadre les hausses de loyer dans les zones où "
                        "la demande dépasse l'offre et prévoit d'accélérer la "
                        "construction de logements sociaux."
                    ),
                    source_id="expose_motifs",
                ),
                PhraseSourcee(
                    phrase=(
                        "Il crée un plafond de hausse à la relocation. Les meublés "
                        "touristiques ne sont pas concernés."
                    ),
                    source_id="texte_article_2",
                ),
            ],
            contexte="Les loyers ont augmenté plus vite que les revenus dans les grandes villes.",
            objectif="Limiter les hausses et rénover des logements abordables.",
            historique="Un encadrement existait déjà à titre expérimental depuis 2019.",
            changement=ChangementTexte(
                avant="Loyer libre lors d'un changement de locataire.",
                apres="Hausse plafonnée à l'indice de référence.",
            ),
            public_concerne=["Particuliers", "Entreprises", "Collectivités", "Associations"],
            # Les 4 questions citoyennes, ici pour que le backend `memory` —
            # celui sur lequel tournent les tests — exerce la partie de l'index
            # de recherche qui vient des réponses Q1/Q4 (§3.3). Contenu fictif.
            questions=QuestionsCitoyennes(
                pourquoi=(
                    "Les députés ont examiné ce texte pour freiner la hausse "
                    "des loyers dans les zones tendues."
                ),
                changement=(
                    "Le texte plafonnerait les hausses de loyer entre deux "
                    "locataires et financerait des rénovations."
                ),
            ),
            confiance="moyenne",
            relu_par_humain=True,
            champs_non_documentes=[],
        ),
    ),
    Dossier(
        id="dos-energie-2026",
        titre_officiel=(
            "Projet de loi prolongeant le bouclier tarifaire sur l'énergie "
            "pour les ménages"
        ),
        titre_clair="Baisser la facture d'énergie",
        accroche="Prolonge le bouclier tarifaire pour les ménages jusqu'en 2027.",
        statut="adopte",
        # Projet de loi : l'initiative est celle du Gouvernement (art. 39), sans
        # personne nommée — on ne descend jamais au ministre déposant.
        initiative=Initiative(origine="gouvernement"),
        theme="Énergie",
        temps_lecture_sec=30,
        date_dernier_scrutin="2026-07-09T15:00:00Z",
        # Trajectoire BICAMÉRALE : le texte a été voté à l'Assemblée puis au
        # Sénat. La dernière étape n'a pas de statut — elle est documentée par
        # les actes officiels mais aucun vote ne la conclut encore (§2.5).
        trajectoire=[
            PhaseScrutin(
                label="1ère lecture (1ère assemblée saisie)",
                chambre="assemblee",
                statut="adopte",
                date="2026-07-07",
            ),
            PhaseScrutin(
                label="1ère lecture (2ème assemblée saisie)",
                chambre="senat",
                statut="adopte",
                date="2026-07-09",
            ),
            PhaseScrutin(label="Commission Mixte Paritaire", date="2026-07-20"),
        ],
        # Texte encore en circulation : on donne le dernier point documenté, et
        # rien de plus — l'étape suivante n'est pas une donnée (§2.5).
        etat=EtatTexte(
            etat="en_navette",
            date="2026-07-20",
            etape="Commission Mixte Paritaire",
        ),
        scrutins=[
            _resume_scrutin("SEN-2026-118"),
            _resume_scrutin("scr-2026-0410"),
        ],
        amendements=[],
        sources=_sources("texte", "debats"),
        resume=ResumeScrutin(
            titre_clair="Baisser la facture d'énergie",
            resume=[
                PhraseSourcee(
                    phrase="Le texte prolonge le bouclier tarifaire pour les ménages jusqu'en 2027.",
                    source_id="texte_article_1",
                ),
                PhraseSourcee(
                    phrase="Il plafonne la hausse des tarifs réglementés de l'électricité et du gaz.",
                    source_id="texte_article_3",
                ),
            ],
            contexte="Les prix de l'énergie ont fortement augmenté depuis 2022.",
            objectif="Contenir la facture énergétique des ménages.",
            public_concerne=["Particuliers"],
            confiance="haute",
            relu_par_humain=True,
            champs_non_documentes=["historique"],
        ),
    ),
    Dossier(
        id="dos-ecoles-2026",
        titre_officiel=(
            "Proposition de loi créant un fonds national pour la rénovation "
            "des bâtiments scolaires"
        ),
        titre_clair="Rénovation des écoles",
        accroche="Créer un fonds national pour rénover les bâtiments scolaires.",
        statut="rejete",
        theme="Éducation",
        temps_lecture_sec=40,
        date_dernier_scrutin="2026-07-06T11:15:00Z",
        scrutins=[_resume_scrutin("scr-2026-0405")],
        amendements=[
            Amendement(
                id="am-03",
                objet="Fléchage prioritaire vers les écoles en zone rurale",
                auteur="Groupe Socialiste",
                sort="retire",
            ),
        ],
        sources=_sources("texte"),
        resume=ResumeScrutin(
            titre_clair="Rénovation des écoles",
            resume=[
                PhraseSourcee(
                    phrase="Le texte créait un fonds national pour rénover les bâtiments scolaires.",
                    source_id="expose_motifs",
                ),
                PhraseSourcee(
                    phrase="Le financement devait être partagé entre l'État et les collectivités.",
                    source_id="texte_article_2",
                ),
            ],
            contexte="De nombreux établissements présentent des besoins de rénovation énergétique.",
            objectif="Financer les travaux de rénovation du bâti scolaire.",
            public_concerne=["Collectivités", "Particuliers"],
            confiance="moyenne",
            relu_par_humain=False,
            champs_non_documentes=["historique"],
        ),
    ),
    # Motion de censure : un ÉVÉNEMENT AUTONOME (ni texte, ni articles, ni
    # trajectoire) et le cas où « 267 voix contre 0 » se lit à l'envers si on
    # n'explique rien — l'article 49 ne recense que les voix favorables.
    Dossier(
        id="dos-censure-2026",
        titre_officiel=(
            "Motion de censure déposée en application de l'article 49, "
            "alinéa 2, de la Constitution"
        ),
        titre_clair="Motion de censure",
        statut="rejete",
        theme="Vie parlementaire",
        temps_lecture_sec=25,
        date_dernier_scrutin="2026-07-09T17:00:00Z",
        scrutins=[_resume_scrutin("scr-2026-0420")],
        est_evenement_autonome=True,
        sources=_sources("scrutin"),
        resume=ResumeScrutin(
            titre_clair="Motion de censure",
            resume=[
                PhraseSourcee(
                    phrase=(
                        "La motion de censure a recueilli 267 voix sur les "
                        "289 requises ; elle n'a pas été adoptée."
                    ),
                    source_id="vote_ensemble",
                ),
            ],
            questions=QuestionsCitoyennes(
                resultat=(
                    "La motion de censure a recueilli 267 voix sur les "
                    "289 requises ; elle n'a pas été adoptée."
                ),
            ),
            confiance="haute",
            relu_par_humain=False,
            champs_non_documentes=["contexte", "objectif", "historique"],
        ),
    ),
    Dossier(
        id="dos-sante-2026",
        titre_officiel="Projet de loi relatif à l'accès aux soins dans les déserts médicaux",
        titre_clair="Lutter contre les déserts médicaux",
        accroche="Encourager l'installation de médecins dans les zones qui en manquent.",
        statut="adopte",
        # Texte allé au bout : promulgué. C'est la réponse à « et maintenant ? »
        # que la frise seule ne donne pas — et la référence de la loi permet de
        # la retrouver même si le lien Légifrance vieillit (§7.5).
        etat=EtatTexte(
            etat="promulgue",
            date="2026-07-13",
            numero_loi="2026-630",
            date_journal_officiel="2026-07-14",
            url_legifrance="https://www.legifrance.gouv.fr/jorf/id/JORFTEXT_SEED",
        ),
        # Le texte tel que le Parlement l'a voté — pas celui qui a été déposé.
        # C'est lui qui fait foi sur une loi en vigueur, et c'est la source de la
        # Q4 (d'où son registre à l'indicatif dans le résumé ci-dessous).
        texte_adopte=TexteAdopte(
            texte=(
                "Article 1er Les violences commises sur un professionnel de "
                "santé dans l'exercice de ses fonctions sont punies des peines "
                "prévues à l'article 222-13 du code pénal."
            ),
            source=SourceOfficielle(
                type="texte",
                libelle="Texte voté par le Parlement",
                url=(
                    "https://www.assemblee-nationale.fr/dyn/17/textes/"
                    "l17t0999_texte-adopte-seance"
                ),
            ),
        ),
        theme="Santé",
        temps_lecture_sec=35,
        date_dernier_scrutin="2026-07-03T09:45:00Z",
        scrutins=[_resume_scrutin("scr-2026-0398")],
        amendements=[],
        # Le dossier de démonstration des **six documents** (§7.5) : sa liste
        # `sources` n'est pas écrite ici mais **composée** plus bas, exactement
        # comme à l'ingestion. Ce qui est écrit, c'est la base — la page du
        # dossier — et les documents eux-mêmes (exposé, rapports, compte rendu,
        # texte voté, Légifrance), chacun à sa place dans le dossier.
        sources=[
            SourceOfficielle(
                type="texte",
                libelle="Dossier législatif",
                url="https://www.assemblee-nationale.fr/dyn/17/dossiers/DLR5L17N99999",
            )
        ],
        expose_motifs=ExposeMotifs(
            texte=(
                "Dans plusieurs départements, l'accès à un médecin traitant "
                "s'est dégradé au point que des patients renoncent aux soins."
            ),
            source=SourceOfficielle(
                type="texte",
                libelle="Texte déposé",
                url=(
                    "https://www.assemblee-nationale.fr/dyn/17/textes/"
                    "l17b0888_projet-loi"
                ),
            ),
        ),
        # Deux lectures, donc deux rapports : leur numéro les distingue, et
        # c'est celui que citent les comptes rendus (« (n° 902) »).
        rapports_commission=[
            SourceOfficielle(
                type="texte",
                libelle="Rapport de la commission (n° 902)",
                url="https://www.assemblee-nationale.fr/dyn/docs/RAPPANR5L17B0902",
            ),
            SourceOfficielle(
                type="texte",
                libelle="Rapport de la commission (n° 1450)",
                url="https://www.assemblee-nationale.fr/dyn/docs/RAPPANR5L17B1450",
            ),
        ],
        resume=ResumeScrutin(
            titre_clair="Lutter contre les déserts médicaux",
            resume=[
                PhraseSourcee(
                    phrase="Le texte encourage l'installation de médecins dans les zones sous-dotées.",
                    source_id="texte_article_1",
                ),
                PhraseSourcee(
                    phrase="Il prévoit des aides financières conditionnées à la durée d'installation.",
                    source_id="texte_article_4",
                ),
            ],
            contexte="L'accès à un médecin traitant s'est dégradé dans plusieurs départements.",
            objectif="Améliorer l'accès aux soins de proximité.",
            questions=QuestionsCitoyennes(
                # Q4 d'une loi en vigueur : à l'**indicatif** et sans
                # attribution, parce que sa source est le texte voté et non le
                # texte déposé (que la navette a modifié). Sa `changementSource`
                # renvoie donc à la petite loi, pas au dépôt.
                changement=(
                    "La loi punit les violences commises sur un professionnel "
                    "de santé dans l'exercice de ses fonctions."
                ),
                changement_source=SourceOfficielle(
                    type="texte",
                    libelle="Texte voté par le Parlement",
                    url=(
                        "https://www.assemblee-nationale.fr/dyn/17/textes/"
                        "l17t0999_texte-adopte-seance"
                    ),
                ),
                # Le compte rendu qui a produit la Q2 : typé `debats`, pas
                # `texte` — c'est un débat, et l'app lui associe 💬.
                desaccord_source=SourceOfficielle(
                    type="debats",
                    libelle="Compte rendu de la séance (Assemblée nationale)",
                    url=(
                        "https://www.assemblee-nationale.fr/dyn/17/"
                        "comptes-rendus/seance/CRSANR5L17S2026O1N999"
                    ),
                ),
            ),
            public_concerne=["Particuliers", "Collectivités"],
            confiance="haute",
            relu_par_humain=True,
            champs_non_documentes=[],
        ),
    ),
]


# Les documents du dossier (§7.5) sont **composés**, jamais écrits à la main :
# c'est la même fonction qu'à l'ingestion (`app.domain.sources`), donc le seed
# montre exactement ce que l'API sert — l'ordre, les libellés et le
# dédoublonnage compris. Ce qui est déclaré plus haut dans chaque dossier n'est
# que la **base** : la page du dossier, ou son repli sur les scrutins.
for _dossier in SEED_DOSSIERS:
    _dossier.sources = documents_du_dossier(_dossier)


# ---------------------------------------------------------------------------
# Députés FICTIFS + leur historique de vote (§5.2).
#
# Les positions ci-dessous sont déclarées à la main ; le reste de chaque entrée
# d'historique (date, objet, titre, « contre son groupe ») est **dérivé** des
# scrutins seed ci-dessus, pour que la démonstration reste cohérente avec les
# `positionsGroupes` affichés sur les fiches vote.
# ---------------------------------------------------------------------------

_DOSSIER_PAR_ID = {d.id: d for d in SEED_DOSSIERS}

SEED_GROUPES: list[GroupeListItem] = [
    GroupeListItem(id=gid, nom=nom, abrev=gid, couleur=couleur, chambre="assemblee")
    for gid, (nom, couleur) in _GROUPES.items()
] + [
    GroupeListItem(
        id=gid,
        nom=nom,
        abrev=gid.removeprefix("SEN-"),
        couleur=couleur,
        chambre="senat",
    )
    for gid, (nom, couleur) in _GROUPES_SENAT.items()
]

# (id, nom, groupe, circonscription, début de mandat)
_DEPUTES: tuple[tuple[str, str, str, str, str | None], ...] = (
    ("dep-seed-01", "Camille Vernet", "RE", "Loire-Atlantique, 3ᵉ circ.", "2024-07-19"),
    ("dep-seed-02", "Hugo Belmont", "RN", "Somme, 1re circ.", "2024-07-19"),
    ("dep-seed-03", "Nadia Ferrand", "LFI", "Seine-Saint-Denis, 7ᵉ circ.", "2024-07-19"),
    ("dep-seed-04", "Olivier Sancerre", "LR", "Cantal, 2ᵉ circ.", "2024-07-19"),
    ("dep-seed-05", "Awa Diallo", "SOC", "Gironde, 4ᵉ circ.", "2024-07-19"),
    # Circonscription et date de début non documentées : les champs restent
    # vides / absents, ils ne sont pas devinés (§2.5).
    ("dep-seed-06", "Léa Marchand", "ECO", "", None),
)

SEED_DEPUTES: list[Depute] = [
    Depute(
        id=identifiant,
        nom=nom,
        chambre="assemblee",
        groupe_id=groupe,
        groupe_nom=_GROUPES[groupe][0],
        groupe_couleur=_GROUPES[groupe][1],
        circonscription=circo,
        depuis=depuis,
        portrait_url=None,  # pas de photo dans le seed (l'app affiche les initiales)
    )
    for identifiant, nom, groupe, circo, depuis in _DEPUTES
]

# Sénateurs FICTIFS. L'annuaire du Sénat ne publie pas de début de mandat :
# `depuis` reste absent, comme à l'ingestion (§2.5).
_SENATEURS: tuple[tuple[str, str, str, str], ...] = (
    ("sen-seed-01", "Martine Ravel", "SEN-LR", "Aveyron"),
    ("sen-seed-02", "Bernard Lestrade", "SEN-UC", "Ille-et-Vilaine"),
    ("sen-seed-03", "Sylvie Nogaro", "SEN-SOC", "Nord"),
)

SEED_DEPUTES += [
    Depute(
        id=identifiant,
        nom=nom,
        chambre="senat",
        groupe_id=groupe,
        groupe_nom=_GROUPES_SENAT[groupe][0],
        groupe_couleur=_GROUPES_SENAT[groupe][1],
        circonscription=circo,
        depuis=None,
        portrait_url=None,
    )
    for identifiant, nom, groupe, circo in _SENATEURS
]


def _vote_depute(scrutin_id: str, groupe_id: str, position: str) -> VoteDepute:
    """Une entrée d'historique, dérivée du scrutin seed correspondant.

    « Contre son groupe » est calculé (position ≠ position majoritaire du
    groupe sur CE scrutin) — jamais saisi à la main, comme à l'ingestion
    (§7.4). Absent si le groupe n'a pas de position sur ce vote (§2.5), et
    **toujours** absent sur un vote du Sénat : les bulletins d'un scrutin public
    ordinaire y sont déposés par un délégué pour tout le groupe, une divergence
    calculée là-dessus mesurerait la procédure, pas le vote.
    """
    scrutin = _SCRUTIN[scrutin_id]
    objet_type = type_objet_vote(scrutin.objet)
    dossier = _DOSSIER_PAR_ID.get(scrutin.dossier_id)
    titre = scrutin.objet
    if objet_type is ObjetVote.dossier and dossier is not None:
        titre = dossier.titre_clair
    majoritaire = next(
        (
            g.position_majoritaire
            for g in scrutin.positions_groupes
            if g.groupe_id == groupe_id
        ),
        None,
    )
    exprime = position != PositionVote.non_votant.value
    contre_son_groupe = None
    if (
        scrutin.chambre is Chambre.assemblee
        and exprime
        and majoritaire is not None
        and majoritaire != PositionVote.non_votant
    ):
        contre_son_groupe = position != majoritaire.value
    return VoteDepute(
        scrutin_id=scrutin.id,
        date=scrutin.date,
        objet_type=objet_type,
        titre=titre,
        dossier_id=scrutin.dossier_id,
        position=position,
        contre_son_groupe=contre_son_groupe,
    )


# Positions déclarées par député (scrutin → position). « dep-seed-06 » n'a
# aucun vote enregistré : sa fiche montre alors des statistiques sans cohésion
# (« information non disponible »), pas un 0 % inventé (§2.5).
_POSITIONS: dict[str, dict[str, str]] = {
    "dep-seed-01": {
        "scr-2026-0412b": "pour",
        "scr-2026-0412a": "pour",
        "scr-2026-0412-am1": "pour",
        "scr-2026-0412-sam1": "contre",
        # Position opposée à celle de son groupe sur ce vote (cas « contre son
        # groupe » : purement descriptif).
        "scr-2026-0412-am2": "pour",
        "scr-2026-0410": "pour",
        "scr-2026-0405": "contre",
        "scr-2026-0398": "pour",
    },
    "dep-seed-02": {
        "scr-2026-0412b": "contre",
        "scr-2026-0412a": "contre",
        "scr-2026-0412-am1": "contre",
        "scr-2026-0412-am2": "pour",
        "scr-2026-0410": "pour",
        "scr-2026-0398": "abstention",
    },
    "dep-seed-03": {
        "scr-2026-0412b": "pour",
        "scr-2026-0412a": "pour",
        "scr-2026-0412-am1": "pour",
        "scr-2026-0412-sam1": "pour",
        "scr-2026-0405": "pour",
        "scr-2026-0398": "pour",
    },
    "dep-seed-04": {
        "scr-2026-0412b": "contre",
        "scr-2026-0412a": "contre",
        "scr-2026-0412-am2": "pour",
        # N'a pas pris part au vote : compté ni dans les votes exprimés ni
        # dans la cohésion.
        "scr-2026-0405": "non_votant",
        "scr-2026-0410": "pour",
    },
    "dep-seed-05": {
        "scr-2026-0412b": "pour",
        "scr-2026-0412a": "pour",
        "scr-2026-0412-am1": "pour",
        "scr-2026-0410": "pour",
        "scr-2026-0405": "pour",
        "scr-2026-0398": "pour",
    },
    # Sénateurs : leur seul vote possible est celui du Sénat. « sen-seed-03 »
    # vote à l'inverse de son groupe, et pourtant `contreSonGroupe` reste absent
    # — c'est exactement ce que la délégation de vote impose (§7.4).
    "sen-seed-01": {"SEN-2026-118": "pour"},
    "sen-seed-02": {"SEN-2026-118": "pour"},
    "sen-seed-03": {"SEN-2026-118": "pour"},
}

# Historique par député, du plus récent au plus ancien (comme l'API réelle).
SEED_VOTES_DEPUTES: dict[str, list[VoteDepute]] = {
    depute.id: sorted(
        (
            _vote_depute(scrutin_id, depute.groupe_id, position)
            for scrutin_id, position in _POSITIONS.get(depute.id, {}).items()
        ),
        key=lambda v: v.date,
        reverse=True,
    )
    for depute in SEED_DEPUTES
}
