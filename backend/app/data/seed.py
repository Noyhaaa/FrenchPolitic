"""Données de démonstration FICTIVES.

⚠️ Illustratives — à remplacer par l'ingestion open data AN + Légifrance (§5).
Portage du mock frontend (src/data/mockScrutins.ts) pour que l'app puisse se
brancher sur l'API sans changement visible.
"""
from __future__ import annotations

from app.schemas import (
    Amendement,
    ChangementTexte,
    PhaseScrutin,
    PhraseSourcee,
    PositionGroupe,
    ResultatGlobal,
    ResumeScrutin,
    Scrutin,
    SourceOfficielle,
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


SEED_SCRUTINS: list[Scrutin] = [
    Scrutin(
        id="scr-2025-0412",
        date="2026-07-08T14:30:00Z",
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
        scrutin_public=True,
        temps_lecture_sec=40,
        resultat=ResultatGlobal(pour=310, contre=231, abstention=24, non_votants=12),
        positions_groupes=[
            _grp("RE", "pour", 148, 8, 4, 0.92),
            _grp("RN", "contre", 12, 76, 0, 0.86),
            _grp("LFI", "pour", 68, 2, 1, 0.95),
            _grp("LR", "contre", 10, 48, 6, 0.75),
            _grp("SOC", "pour", 62, 1, 3, 0.94),
            _grp("ECO", "pour", 34, 0, 2, 0.94),
        ],
        amendements=[
            Amendement(
                id="am-01",
                objet="Étend l'encadrement aux communes de plus de 20 000 habitants",
                auteur="Groupe Écologiste",
                sort="adopte",
            ),
            Amendement(
                id="am-02",
                objet="Exonère les logements rénovés depuis moins de 3 ans",
                auteur="Groupe LR",
                sort="rejete",
            ),
        ],
        sources=_sources("texte", "amendements", "debats", "scrutin"),
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
    Scrutin(
        id="scr-2025-0410",
        date="2026-07-07T16:00:00Z",
        titre_officiel=(
            "Projet de loi prolongeant le bouclier tarifaire sur l'énergie "
            "pour les ménages"
        ),
        titre_clair="Baisser la facture d'énergie",
        accroche="Prolonge le bouclier tarifaire pour les ménages jusqu'en 2027.",
        statut="adopte",
        theme="Énergie",
        scrutin_public=True,
        temps_lecture_sec=30,
        resultat=ResultatGlobal(pour=401, contre=96, abstention=40, non_votants=40),
        positions_groupes=[
            _grp("RE", "pour", 152, 0, 8, 0.95),
            _grp("RN", "pour", 70, 4, 14, 0.80),
            _grp("LFI", "abstention", 20, 12, 39, 0.55),
            _grp("LR", "pour", 52, 2, 10, 0.81),
            _grp("SOC", "pour", 60, 0, 6, 0.91),
            _grp("ECO", "contre", 4, 28, 4, 0.78),
        ],
        amendements=[],
        sources=_sources("texte", "debats", "scrutin"),
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
    Scrutin(
        id="scr-2025-0405",
        date="2026-07-06T11:15:00Z",
        titre_officiel=(
            "Proposition de loi créant un fonds national pour la rénovation "
            "des bâtiments scolaires"
        ),
        titre_clair="Rénovation des écoles",
        accroche="Créer un fonds national pour rénover les bâtiments scolaires.",
        statut="rejete",
        theme="Éducation",
        scrutin_public=True,
        temps_lecture_sec=40,
        resultat=ResultatGlobal(pour=214, contre=268, abstention=55, non_votants=40),
        positions_groupes=[
            _grp("RE", "contre", 6, 140, 14, 0.87),
            _grp("RN", "contre", 8, 70, 10, 0.80),
            _grp("LFI", "pour", 66, 0, 4, 0.94),
            _grp("LR", "contre", 12, 44, 8, 0.69),
            _grp("SOC", "pour", 62, 0, 4, 0.94),
            _grp("ECO", "pour", 34, 0, 2, 0.94),
        ],
        amendements=[
            Amendement(
                id="am-03",
                objet="Fléchage prioritaire vers les écoles en zone rurale",
                auteur="Groupe Socialiste",
                sort="retire",
            ),
        ],
        sources=_sources("texte", "scrutin"),
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
    Scrutin(
        id="scr-2025-0398",
        date="2026-07-03T09:45:00Z",
        titre_officiel="Projet de loi relatif à l'accès aux soins dans les déserts médicaux",
        titre_clair="Lutter contre les déserts médicaux",
        accroche="Encourager l'installation de médecins dans les zones qui en manquent.",
        statut="adopte",
        theme="Santé",
        scrutin_public=True,
        temps_lecture_sec=35,
        resultat=ResultatGlobal(pour=356, contre=120, abstention=61, non_votants=40),
        positions_groupes=[
            _grp("RE", "pour", 150, 2, 8, 0.93),
            _grp("RN", "abstention", 30, 10, 48, 0.55),
            _grp("LFI", "pour", 60, 6, 4, 0.85),
            _grp("LR", "pour", 44, 12, 8, 0.68),
            _grp("SOC", "pour", 58, 2, 6, 0.88),
            _grp("ECO", "pour", 32, 1, 3, 0.89),
        ],
        amendements=[],
        sources=_sources("texte", "debats", "scrutin"),
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
