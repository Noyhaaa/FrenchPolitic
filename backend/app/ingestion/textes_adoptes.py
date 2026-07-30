"""Le texte **définitivement voté** par le Parlement — la « petite loi » (§5.1).

Tout ce que l'app décrit d'un texte vient de son **dépôt** : l'exposé des motifs,
le dispositif, et la réponse « qu'est-ce que ça change ? ». Sur une loi
promulguée, cette version n'existe plus — la navette et les amendements l'ont
modifiée. La fiche d'une loi en vigueur affichait donc le **pitch de son auteur,
au conditionnel, sur une proposition** (mesuré : 83 des 96 lois promulguées).

L'archive désigne elle-même le bon texte : le nœud `PROM-PUB` porte un
`texteLoiRef` vers le document adopté. Son URL se dérive de l'`uid`, comme celle
du texte déposé (`textes_an.py`), avec deux schémas selon la chambre qui a voté
en dernier :

    PIONANR5L17BTA0075  → assemblee-nationale.fr/dyn/17/textes/l17t0075_texte-adopte-seance
    PRJLSNR5S459BTA0040 → senat.fr/leg/tas24-040

⚠️ Côté Sénat, l'année de l'URL est celle de la **session** (oct.→sept.), déduite
de la date de publication du document — même piège que les URLs de scrutin
(`senat.py`). Elle n'est **jamais** approchée : la numérotation redémarre à
chaque session, si bien qu'un décalage d'un an attrape un texte **sans rapport**
(cas vécu : `tas24-159` est une résolution européenne sur la subsidiarité, là où
`tas25-159` devait être une loi sur les maladies cardio-neuro-vasculaires). Un
404 ne donne rien (§2.5), il ne déclenche aucun repli.
"""
from __future__ import annotations

import re

from app.ingestion.senat import session_pour
from app.ingestion.textes_an import (
    _MAX_DISPOSITIF,
    _MIN_DISPOSITIF,
    lire_pdf,
)
from app.schemas import SourceOfficielle, TexteAdopte

# uid d'un texte adopté par l'**Assemblée** : « …L17BTA0075 » → législature 17,
# texte adopté n° 75. Les zéros de tête sont retirés ici puis re-posés sur
# 4 chiffres dans l'URL (même piège que `textes_an`).
_RE_UID_AN = re.compile(r"L(\d+)BTA0*(\d+)")
# uid d'un texte adopté par le **Sénat** : « …S459BTA0040 » → n° 40. Le « S459 »
# est un identifiant de session interne à l'archive, sans rapport avec l'année de
# l'URL : celle-ci vient de la date de publication du document.
_RE_UID_SENAT = re.compile(r"S\d+BTA0*(\d+)")

_BASE_AN = "https://www.assemblee-nationale.fr/dyn/{leg}/textes/l{leg}t{num}_texte-adopte-seance"
_BASE_SENAT = "https://www.senat.fr/leg/tas{session}-{num}"

# Début du dispositif d'une petite loi. Contrairement au texte déposé, il n'y a
# pas d'exposé des motifs à sauter : l'en-tête est administratif (« TEXTE ADOPTÉ
# n° 75 », « (Texte définitif) », « L'Assemblée nationale a adopté… dont la
# teneur suit », « Voir les numéros : … ») et n'est pas de la loi.
#
# ⚠️ Volontairement **sans `re.IGNORECASE`** : les titres d'article sont
# capitalisés (« Article unique », « Article 1 er »), alors qu'une référence en
# prose ne l'est pas (« dans les conditions prévues à l'article 45 »), et l'une
# d'elles figure justement dans l'en-tête qu'on veut sauter. Même discipline que
# `textes_an._RE_FIN`.
_RE_PREMIER_ARTICLE = re.compile(r"Article\s+(1\s*er|premier|unique|1\b)")


def ref_texte_loi(actes_legislatifs: object) -> str | None:
    """L'`uid` du texte définitivement voté, d'après l'acte de promulgation.

    C'est l'archive qui le désigne (`PROM-PUB.texteLoiRef`) : on ne le choisit
    pas. Les dossiers dont elle ne le dit pas n'en auront pas — ils portent
    pourtant plusieurs textes adoptés (un par lecture, dans chaque chambre), et
    en élire un serait choisir à la place de la source. Mesuré : le plus récent
    est parfois la version *modifiée par le Sénat*, qui n'est pas la loi (§2.5).
    """
    trouve: str | None = None

    def descendre(noeud: object) -> None:
        nonlocal trouve
        if trouve is not None:
            return
        if isinstance(noeud, list):
            for element in noeud:
                descendre(element)
            return
        if not isinstance(noeud, dict):
            return
        if noeud.get("codeActe") == "PROM-PUB":
            ref = noeud.get("texteLoiRef")
            if isinstance(ref, str) and ref:
                trouve = ref
                return
        for valeur in noeud.values():
            descendre(valeur)

    descendre(actes_legislatifs)
    return trouve


def urls_texte_adopte(uid: str, date_publication: str | None) -> tuple[str, str] | None:
    """`(url_page, url_pdf)` du texte adopté, dérivées de son `uid`.

    La page est la source lisible offerte au lecteur (§7.5), le PDF est ce qu'on
    extrait. None si l'uid n'est pas un texte adopté reconnaissable, ou si la
    date manque côté Sénat — sans elle, l'année de session ne se déduit pas et on
    n'invente pas d'URL.
    """
    an = _RE_UID_AN.search(uid)
    if an:
        leg, num = an.group(1), int(an.group(2))
        base = _BASE_AN.format(leg=leg, num=f"{num:04d}")
        return base, base + ".pdf"

    senat = _RE_UID_SENAT.search(uid)
    if senat:
        if not date_publication or len(date_publication) < 7:
            return None
        annee, mois = int(date_publication[:4]), int(date_publication[5:7])
        session = session_pour(annee, mois) % 100
        base = _BASE_SENAT.format(session=f"{session:02d}", num=f"{int(senat.group(1)):03d}")
        # Le Sénat sert la page en `.html` (l'URL nue répond 404), l'Assemblée
        # sans extension. Un détail, mais un 404 offert au lecteur est un 404.
        return base + ".html", base + ".pdf"

    return None


def decouper_loi(texte: str, max_chars: int = _MAX_DISPOSITIF) -> str | None:
    """Les articles de la loi votée, depuis le texte brut de sa petite loi.

    Cousin de `textes_an.decouper_dispositif`, mais le découpage part du
    **premier article** et non d'un en-tête de nature : une petite loi n'a pas
    d'exposé des motifs, et son en-tête est administratif.

    None si aucun article n'est repérable, si le corps est trop court
    (`_MIN_DISPOSITIF`) ou **trop long** (`max_chars`). Dans ce dernier cas on
    n'attache rien plutôt que de tronquer : le corps sert de source à la Q4, et
    un modèle qui ne verrait que les premiers articles présenterait un bout de
    loi comme le tout (§2.5).
    """
    debut = _RE_PREMIER_ARTICLE.search(texte)
    if not debut:
        return None
    corps = re.sub(r"\s+", " ", texte[debut.start() :]).strip()
    if len(corps) < _MIN_DISPOSITIF or len(corps) > max_chars:
        return None
    return corps


def construire_index_publications_ta(documents: list[dict]) -> dict[str, str]:
    """Table `uid d'un texte adopté → sa date de publication`.

    Bâtie sur les documents **déjà téléchargés** pour la réconciliation : c'est
    la seule information manquante pour dériver une URL du Sénat, dont l'année
    est celle de la session. Les textes adoptés de l'Assemblée n'en ont pas
    besoin (leur uid porte la législature), mais les indexer coûte le même
    parcours.
    """
    index: dict[str, str] = {}
    for brut in documents:
        document = brut.get("document") or brut
        uid = document.get("uid") or ""
        if "BTA" not in uid:
            continue
        chrono = (document.get("cycleDeVie") or {}).get("chrono") or {}
        date = chrono.get("datePublication")
        if isinstance(date, str) and date:
            index[uid] = date
    return index


def source_loi(url_page: str) -> SourceOfficielle:
    """Le lien vers la loi telle que le Parlement l'a votée (§7.5).

    Distinct du lien Légifrance (`EtatTexte.url_legifrance`), et la carte « La
    loi » les affiche ensemble : ici c'est **ce qui a été voté**, là-bas **ce qui
    s'applique aujourd'hui** — la loi a pu être modifiée depuis sa promulgation.
    """
    return SourceOfficielle(
        type="texte", libelle="Texte voté par le Parlement", url=url_page
    )


def construire_texte_adopte(url_page: str, pdf: bytes | None) -> TexteAdopte:
    """Assemble le bloc `TexteAdopte` : la source **toujours**, le corps si
    exploitable.

    Les deux sont dissociés à dessein — le lien vaut pour toute loi dont
    l'archive désigne le texte, alors que le corps n'a de sens que lu
    entièrement par le modèle (cf. `decouper_loi`). Mesuré : 75 liens pour
    44 corps.
    """
    texte_brut = lire_pdf(pdf) if pdf else None
    corps = decouper_loi(texte_brut) if texte_brut else None
    return TexteAdopte(source=source_loi(url_page), texte=corps)
