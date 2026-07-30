"""Indice de division d'un scrutin — arithmétique pure sur les décomptes officiels.

Ce que cet indice EST : une mesure de **la division du vote**, calculée
uniquement sur les chiffres publiés par la chambre (décomptes globaux et par
groupe). Rien n'y est appris, deviné ni pondéré par une opinion.

Ce qu'il n'est PAS : un jugement sur la mesure votée (§4.3, §7.4). Un vote très
disputé n'est ni bon ni mauvais, ni important ni anecdotique — il est *serré*,
et c'est tout ce que l'app en dit. L'écran affiche toujours les chiffres à côté
du classement, pour que le lecteur voie le fait et pas seulement le rang.

Quatre composantes, toutes lisibles séparément dans `Division` :

- **écart** — 1 quand pour == contre, 0 quand le vote est unanime. C'est le cœur
  du signal : un texte adopté à 10 voix près a divisé l'hémicycle.
- **abstention** — part des votants qui n'ont pas tranché. Une abstention massive
  est un fait de division, pas un désintérêt : au scrutin public, s'abstenir est
  un acte déposé.
- **fracture entre groupes** — nombre de positions majoritaires distinctes parmi
  les groupes (tous pour = 0, pour/contre = 0,5, pour/contre/abstention = 1).

Une quatrième donnée, la **dispersion interne** (groupes dont plus d'un cinquième
des voix s'écarte de leur propre position majoritaire), est calculée et affichée
mais **n'entre pas dans le classement**. Deux raisons, la seconde décisive :

⚠️ Elle **n'est jamais calculable au Sénat** : les bulletins d'un scrutin public
ordinaire y sont déposés par un délégué de groupe pour tous ses membres, si bien
qu'un écart intra-groupe refléterait la procédure et non un désaccord (même
doctrine que `contre_son_groupe` et la cohésion, toujours absents au Sénat).
La pondérer reviendrait donc à classer les deux chambres sur des critères
différents : ou bien le Sénat serait pénalisé par une composante manquante, ou
bien il serait avantagé par sa renormalisation. Les deux sont des artefacts de
méthode déguisés en faits. **Le classement ne retient donc que les composantes
observables des deux côtés** ; la dispersion reste un fait affiché là où elle est
défendable, à l'Assemblée.

**Ampleur** : à division égale, un vote à 371 votants pèse plus qu'un vote à 60.
Sans ce facteur, le classement remonte des amendements votés dans un hémicycle
quasi vide (40 pour / 40 contre), statistiquement serrés mais qui n'ont divisé
personne. Le seuil est atteint bien avant l'effectif d'une chambre : on ne
cherche pas à récompenser la participation, seulement à écarter le bruit.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.domain.enums import Chambre, PositionVote, TypeVote
from app.ingestion.normalize import est_vote_de_conduite_de_seance
from app.schemas import PositionGroupe, ResultatGlobal

# En deçà, le scrutin est trop peu fourni pour que « serré » veuille dire quelque
# chose : on ne classe pas (§2.5), plutôt que de publier un rang trompeur.
_VOTANTS_MINIMUM = 50

# Au-delà, l'ampleur ne joue plus : ~300 votants, c'est déjà une chambre pleine
# au sens des scrutins publics (268 votants en moyenne à l'Assemblée).
_VOTANTS_PLEINE_CHAMBRE = 300

# Part des voix d'un groupe qui doit s'écarter de sa position majoritaire pour
# qu'on parle de dispersion. En deçà, c'est le grain normal d'un vote.
_SEUIL_DISPERSION = 0.2

# Un groupe de moins de 5 votants ne peut pas être dit « dispersé » : une voix
# suffirait à franchir le seuil.
_TAILLE_GROUPE_MINIMUM = 5

# Poids des composantes retenues pour le CLASSEMENT (la dispersion interne n'y
# figure pas : voir l'en-tête). Ils sont renormalisés si un groupe manque — un
# scrutin sans ventilation par groupe reste classable sur ses seuls décomptes.
_POIDS_ECART = 0.60
_POIDS_ABSTENTION = 0.20
_POIDS_FRACTURE = 0.20

# Part de l'indice qui ne dépend pas de l'ampleur : un vote peu fourni conserve
# la moitié de son indice, il n'est pas effacé.
_PART_INCOMPRESSIBLE = 0.5

_CHAMP_POSITION = {
    PositionVote.pour: "pour",
    PositionVote.contre: "contre",
    PositionVote.abstention: "abstention",
}


@dataclass(frozen=True)
class Division:
    """Division d'un scrutin, avec ses composantes lisibles une à une.

    Les champs bruts (`ecart`, `exprimes`, `abstention`…) sont ceux affichés à
    l'écran : l'indice ne sert qu'à ordonner, jamais à être montré seul.
    """

    indice: float
    ecart: int
    exprimes: int
    abstention: int
    votants: int
    camps: int
    # None au Sénat : le fait n'y est pas défendable (voir l'en-tête du module).
    groupes_disperses: int | None


def _fracture(positions: list[PositionGroupe]) -> int:
    """Nombre de positions majoritaires distinctes parmi les groupes."""
    return len(
        {
            p.position_majoritaire
            for p in positions
            if p.position_majoritaire in _CHAMP_POSITION
        }
    )


def _groupes_disperses(positions: list[PositionGroupe]) -> int:
    """Groupes dont une part notable des voix s'écarte de leur majorité."""
    disperses = 0
    for p in positions:
        champ = _CHAMP_POSITION.get(p.position_majoritaire)
        if champ is None:
            continue
        total = p.pour + p.contre + p.abstention
        if total < _TAILLE_GROUPE_MINIMUM:
            continue
        if (total - getattr(p, champ)) / total > _SEUIL_DISPERSION:
            disperses += 1
    return disperses


def division(
    resultat: ResultatGlobal,
    positions_groupes: list[PositionGroupe],
    chambre: Chambre,
    *,
    objet: str = "",
    scrutin_public: bool = True,
    type_vote: TypeVote | None = None,
) -> Division | None:
    """Division d'un scrutin, ou None s'il n'est pas classable (§2.5).

    Non classable :
    - vote sans décompte public (main levée) — il n'y a rien à mesurer ;
    - vote trop peu fourni — « serré » n'y veut rien dire ;
    - vote sur la **conduite de la séance** (suspension, prolongation au-delà de
      minuit, seconde délibération) : souvent très serré, mais il ne décide de
      rien. Le remonter à l'écran ferait passer une péripétie de séance pour un
      moment de division politique ;
    - **motion de censure** : l'article 49 ne fait recenser que les voix
      favorables, si bien que `contre` y vaut 0 par construction. L'écart entre
      deux camps n'a pas de sens quand un seul est compté — l'indice y sortirait
      « quasi unanime » sur un vote qui a divisé l'hémicycle. Elle sortait déjà
      du classement par ce score, mais **par accident arithmétique** ; ici c'est
      une décision : l'arithmétique ne s'applique pas.

    On préfère l'absence au rang trompeur.
    """
    if not scrutin_public or est_vote_de_conduite_de_seance(objet):
        return None
    if type_vote is TypeVote.motion_censure:
        return None
    exprimes = resultat.pour + resultat.contre
    votants = exprimes + resultat.abstention
    if not exprimes or votants < _VOTANTS_MINIMUM:
        return None

    ecart = abs(resultat.pour - resultat.contre)
    composantes: list[tuple[float, float]] = [
        (_POIDS_ECART, 1 - ecart / exprimes),
        (_POIDS_ABSTENTION, resultat.abstention / votants),
    ]

    camps = _fracture(positions_groupes)
    if camps:
        # 1 camp → 0 ; 2 → 0,5 ; 3 → 1. Un seul camp, c'est l'unanimité des
        # groupes : rien à signaler.
        composantes.append((_POIDS_FRACTURE, (camps - 1) / 2))

    # Calculée pour l'affichage seulement (et jamais au Sénat) : elle n'entre
    # pas dans `composantes`, donc pas dans le classement.
    disperses: int | None = None
    if chambre is Chambre.assemblee and positions_groupes:
        disperses = _groupes_disperses(positions_groupes)

    poids_total = sum(poids for poids, _ in composantes)
    brut = sum(poids * valeur for poids, valeur in composantes) / poids_total

    ampleur = min(votants / _VOTANTS_PLEINE_CHAMBRE, 1.0)
    indice = brut * (_PART_INCOMPRESSIBLE + (1 - _PART_INCOMPRESSIBLE) * ampleur)

    return Division(
        indice=round(indice, 4),
        ecart=ecart,
        exprimes=exprimes,
        abstention=resultat.abstention,
        votants=votants,
        camps=camps,
        groupes_disperses=disperses,
    )
