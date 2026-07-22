"""Données de démonstration FICTIVES.

⚠️ Illustratives — à remplacer par l'ingestion open data AN + Légifrance (§5).
Servent de backend « memory » par défaut pour que l'app se branche sur l'API
sans dépendre d'une base. Unité : le dossier (texte) et ses scrutins.
"""
from __future__ import annotations

from app.domain.enums import ObjetVote, PositionVote
from app.ingestion.normalize import type_objet_vote
from app.schemas import (
    Amendement,
    ChangementTexte,
    Depute,
    Dossier,
    GroupeListItem,
    MiseAJourDossier,
    PhaseScrutin,
    PhraseSourcee,
    PositionGroupe,
    QuestionsAmendement,
    ResultatGlobal,
    ResumeScrutin,
    Scrutin,
    ScrutinResume,
    SourceOfficielle,
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


def _grp(gid: str, position: str, pour: int, contre: int, abst: int, cohesion: float):
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
        theme="Énergie",
        temps_lecture_sec=30,
        date_dernier_scrutin="2026-07-07T16:00:00Z",
        scrutins=[_resume_scrutin("scr-2026-0410")],
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
    Dossier(
        id="dos-sante-2026",
        titre_officiel="Projet de loi relatif à l'accès aux soins dans les déserts médicaux",
        titre_clair="Lutter contre les déserts médicaux",
        accroche="Encourager l'installation de médecins dans les zones qui en manquent.",
        statut="adopte",
        theme="Santé",
        temps_lecture_sec=35,
        date_dernier_scrutin="2026-07-03T09:45:00Z",
        scrutins=[_resume_scrutin("scr-2026-0398")],
        amendements=[],
        sources=_sources("texte", "debats"),
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
            public_concerne=["Particuliers", "Collectivités"],
            confiance="haute",
            relu_par_humain=True,
            champs_non_documentes=[],
        ),
    ),
]


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
    GroupeListItem(id=gid, nom=nom, abrev=gid, couleur=couleur)
    for gid, (nom, couleur) in _GROUPES.items()
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
        groupe_id=groupe,
        groupe_nom=_GROUPES[groupe][0],
        groupe_couleur=_GROUPES[groupe][1],
        circonscription=circo,
        depuis=depuis,
        portrait_url=None,  # pas de photo dans le seed (l'app affiche les initiales)
    )
    for identifiant, nom, groupe, circo, depuis in _DEPUTES
]


def _vote_depute(scrutin_id: str, groupe_id: str, position: str) -> VoteDepute:
    """Une entrée d'historique, dérivée du scrutin seed correspondant.

    « Contre son groupe » est calculé (position ≠ position majoritaire du
    groupe sur CE scrutin) — jamais saisi à la main, comme à l'ingestion
    (§7.4). Absent si le groupe n'a pas de position sur ce vote (§2.5).
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
    if exprime and majoritaire is not None and majoritaire != PositionVote.non_votant:
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
