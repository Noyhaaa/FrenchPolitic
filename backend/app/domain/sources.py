"""Les documents officiels d'un dossier — composition pure de `Dossier.sources`.

§7.5 promet la réversibilité : atteindre la source brute en un tap. Les URLs de
tous les documents d'un dossier sont déjà dans son payload, mais chacune était
enfermée dans la carte qui s'en sert — l'exposé des motifs pour le texte déposé,
la Q2 pour le compte rendu, la carte « La loi » pour le texte voté. Un lecteur
qui n'ouvrait pas la bonne carte ne savait pas qu'ils existaient : mesuré,
286 dossiers sur 328 portaient au moins un document que la liste n'affichait pas.

Ce module rassemble tout au même endroit, **sans rien télécharger** : il ne fait
que relire ce que le dossier porte. Il n'invente donc aucun libellé et n'ajoute
aucune URL — un document absent laisse simplement sa place vide (§2.5).

⚠️ Cette liste est le **seul** endroit de la fiche où un document du dossier est
lié. Les cartes qui en citent un (l'exposé des motifs, la Q2, « La loi ») ne
portent plus leur propre lien : la même URL deux ou trois fois sur une même page
n'ajoutait rien et brouillait la lecture. Ce qui reste dans les cartes, c'est ce
qu'un lien ne dit pas — la **provenance en toutes lettres** (« Selon l'auteur du
texte », « exprimés en séance », le nom du document dont sort la Q4).

Contrôlé en base : les URLs qu'affichaient les cartes sont toutes dans la liste,
zéro orpheline. Retirer un lien d'une carte ne rend donc rien inatteignable.
"""
from __future__ import annotations

from app.schemas import Dossier, SourceOfficielle

# Libellé du lien Légifrance — le MÊME que celui de la carte « La loi »
# (`src/components/LoiCard.tsx`). Deux libellés pour une seule URL feraient
# croire à deux textes ; c'est exactement ce qu'on veut éviter.
LIBELLE_LEGIFRANCE = "Texte en vigueur (Légifrance)"

# Préfixes des libellés que CE module compose, quelle que soit leur provenance
# (`textes_an`, `textes_senat`, `rapports`, `textes_adoptes`, `debats`).
#
# Liste **fermée**, et elle sert à une seule chose : reconnaître, dans une liste
# déjà composée par un run précédent, ce qui doit être **recalculé** plutôt que
# conservé. Sans elle, un document qui disparaît du dossier (un désaccord effacé
# par `revalider`, donc son compte rendu) laisserait son lien en base pour
# toujours — la liste dirait alors quelque chose que le dossier ne dit plus.
# Le dédoublonnage par URL ne suffit pas : il ne voit que ce qu'on ajoute.
_LIBELLES_COMPOSES = (
    "Texte déposé",
    "Rapport de la commission",
    "Compte rendu de la séance",
    "Texte voté par le Parlement",
    LIBELLE_LEGIFRANCE,
)


def dedupe_sources(sources: list[SourceOfficielle]) -> list[SourceOfficielle]:
    """Une URL, une entrée — la **première** vue gagne (donc son libellé aussi).

    L'exposé des motifs et le dispositif sortent du même PDF et portent la même
    URL : sans ce filtre, 176 dossiers afficheraient deux fois « Texte déposé ».
    """
    vues: set[str] = set()
    retenues: list[SourceOfficielle] = []
    for s in sources:
        if s.url not in vues:
            vues.add(s.url)
            retenues.append(s)
    return retenues


def base_du_dossier(dossier: Dossier) -> list[SourceOfficielle]:
    """Ce qui, dans `sources`, n'est PAS composé ici : la page du dossier.

    C'est-à-dire le dossier législatif (AN ou Sénat) posé par `build_dossier`,
    ou, pour un dossier sans page officielle, son repli sur les sources des
    scrutins. Tout le reste est recalculé à chaque écriture.
    """
    return [
        s
        for s in dossier.sources
        if not s.libelle.startswith(_LIBELLES_COMPOSES)
    ]


def documents_du_dossier(dossier: Dossier) -> list[SourceOfficielle]:
    """Les documents du dossier, dans l'ordre de la **vie du texte**.

    Dossier législatif → texte déposé → rapports de commission → compte rendu de
    séance → texte voté → texte en vigueur. Cet ordre-là plutôt que l'ordre
    d'arrivée : il se lit comme le parcours du texte, et il est stable d'un
    dossier à l'autre même quand des documents manquent.

    Pure et **idempotente** : rejouée sur son propre résultat, elle rend la même
    liste — c'est ce qui permet de la recomposer à chaque run comme au rattrapage
    sans que rien ne s'accumule.
    """
    composee = base_du_dossier(dossier)

    # Le texte déposé. L'exposé et le dispositif partagent le même PDF : le
    # dédoublonnage final n'en garde qu'un, sans qu'on ait à choisir ici.
    if dossier.expose_motifs is not None:
        composee.append(dossier.expose_motifs.source)
    if dossier.dispositif is not None:
        composee.append(dossier.dispositif.source)

    # Les rapports de commission, un par lecture, chacun avec son numéro.
    composee.extend(dossier.rapports_commission)

    # Le compte rendu de la séance : la source de la Q2 (« principal
    # désaccord »). Absent quand aucun débat n'a pu être relié au vote.
    questions = dossier.resume.questions
    if questions is not None and questions.desaccord_source is not None:
        composee.append(questions.desaccord_source)

    # La loi : ce que le Parlement a voté, puis ce qui s'applique aujourd'hui.
    # Deux documents distincts — une loi peut avoir été modifiée depuis.
    if dossier.texte_adopte is not None:
        composee.append(dossier.texte_adopte.source)
    if dossier.etat is not None and dossier.etat.url_legifrance:
        composee.append(
            SourceOfficielle(
                type="texte",
                libelle=LIBELLE_LEGIFRANCE,
                url=dossier.etat.url_legifrance,
            )
        )

    return dedupe_sources(composee)
