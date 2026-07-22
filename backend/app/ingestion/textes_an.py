"""Exposé des motifs depuis le PDF officiel du texte (§5.1).

L'open data AN ne contient PAS le corps des textes (métadonnées seules). Mais le
**PDF du texte déposé** est public, et son URL se **dérive de l'`uid`** du
document de l'archive « dossiers législatifs » (déjà chargée pour la
réconciliation). On en extrait l'**exposé des motifs** — le « pourquoi » rédigé
par l'auteur du dépôt.

⚠️ L'exposé est le **point de vue du déposant**, PAS un fait neutre (§4.3) : il
est stocké dans un bloc `ExposeMotifs` **cité et attribué**, jamais fondu dans le
résumé neutre (l'usage comme contexte d'un LLM neutre viendra plus tard).

La page HTML du texte est vide (rendu JS) : seul le PDF est exploitable. Quand le
PDF manque ou n'a pas d'exposé identifiable, on n'attache rien (§2.5 : jamais de
comblement) — la couverture est donc partielle (surtout des propositions de loi).
"""
from __future__ import annotations

import io
import re
from collections import defaultdict

from pypdf import PdfReader

from app.ingestion.dossiers_legislatifs import _DENOMINATIONS_TEXTE
from app.schemas import ExposeMotifs, SourceOfficielle

# uid document → (législature, numéro) : « …L17B1337 » → 17, 1337 (zéros de tête
# retirés pour l'URL : « l17b1337 »).
_RE_UID = re.compile(r"L(\d+)B0*(\d+)")
# Début de l'exposé (insensible casse/accent).
_RE_DEBUT = re.compile(r"expos[eé]\s+des\s+motifs", re.I)
# Début du dispositif → fin de l'exposé. L'en-tête est en MAJUSCULES dans le PDF
# (les mentions « proposition de loi » en minuscules du corps ne comptent donc
# pas) ; à défaut, le premier « Article premier / 1er / unique ».
_RE_FIN = re.compile(
    r"(PROPOSITION DE LOI|PROJET DE LOI|Article\s+(1er|premier|unique|1\b))"
)
# Salutation formulaire en tête d'exposé — retirée pour un bloc plus propre.
_RE_SALUT = re.compile(r"^\s*mesdames,?\s+messieurs,?\s*", re.I)


def url_page_texte(uid: str) -> str | None:
    """URL de la page officielle du texte déposé, dérivée de l'`uid` du document.

    None si l'uid ne porte pas le motif `L{leg}B{num}` ou n'est pas un texte AN
    (proposition `PION…` / projet `PRJL…` / proposition de résolution `PNREAN…`).
    Le PDF est cette URL suffixée `.pdf` ; la page (sans suffixe) sert de source
    lisible (§7.5).
    """
    if uid.startswith("PION"):
        suffixe = "proposition-loi"
    elif uid.startswith("PRJL"):
        suffixe = "projet-loi"
    elif uid.startswith("PNREAN"):
        suffixe = "proposition-resolution"
    else:
        return None
    m = _RE_UID.search(uid)
    if not m:
        return None
    leg, num = m.group(1), m.group(2)
    # Le site AN garde les zéros de tête (4 chiffres) : « l17b0369_… » répond,
    # « l17b369_… » renvoie 404 (vérifié — c'était la 1re cause d'exposés
    # manquants).
    return (
        f"https://www.assemblee-nationale.fr/dyn/{leg}/textes/"
        f"l{leg}b{num.zfill(4)}_{suffixe}"
    )


def decouper_expose(texte: str, max_chars: int = 4000) -> str | None:
    """Extrait l'exposé des motifs d'un texte brut (déjà extrait du PDF).

    Pur et testable. None s'il n'y a pas d'exposé identifiable (§2.5). Coupe au
    début du dispositif (en-tête MAJUSCULES ou premier article), retire la
    salutation formulaire, et tronque au mot près au-delà de `max_chars`.
    """
    debut = _RE_DEBUT.search(texte)
    if not debut:
        return None
    reste = texte[debut.end() :]
    fin = _RE_FIN.search(reste)
    corps = reste[: fin.start()] if fin else reste
    corps = re.sub(r"\s+", " ", corps).strip()
    corps = _RE_SALUT.sub("", corps).strip()
    if len(corps) < 40:  # trop court pour être un exposé réel
        return None
    if len(corps) > max_chars:
        corps = corps[:max_chars].rsplit(" ", 1)[0].rstrip(" ,;.") + "…"
    return corps


def lire_pdf(pdf: bytes) -> str | None:
    """Texte brut d'un PDF (concat des pages, via pypdf). None si illisible."""
    try:
        reader = PdfReader(io.BytesIO(pdf))
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    except Exception:
        return None


def extraire_expose(pdf: bytes, max_chars: int = 4000) -> str | None:
    """Exposé des motifs extrait du PDF (extraction pypdf + `decouper_expose`).

    None si le PDF est illisible ou sans exposé identifiable (§2.5).
    """
    texte = lire_pdf(pdf)
    return decouper_expose(texte, max_chars) if texte else None


def source_texte(url_page: str) -> SourceOfficielle:
    return SourceOfficielle(type="texte", libelle="Texte déposé", url=url_page)


def construire_expose(uid: str, pdf: bytes) -> ExposeMotifs | None:
    """Assemble le bloc `ExposeMotifs` (texte + source) ; None si non exploitable."""
    url_page = url_page_texte(uid)
    if not url_page:
        return None
    texte = extraire_expose(pdf)
    if not texte:
        return None
    return ExposeMotifs(texte=texte, source=source_texte(url_page))


def _numero_uid(uid: str) -> int:
    """Numéro du texte porté par l'uid (pour trier du dépôt initial au plus récent)."""
    m = _RE_UID.search(uid)
    return int(m.group(2)) if m else 10**9


def construire_index_textes(
    documents: list[dict], legislatures: tuple[int, ...]
) -> dict[str, list[str]]:
    """Table `dossierRef → uids des textes AN déposés` (URL dérivable), triés du
    **dépôt initial** (plus petit numéro) au plus récent.

    On essaiera le dépôt initial d'abord : c'est lui qui porte l'exposé des
    motifs. Les versions de navette (« transmise / modifiée par le Sénat »), les
    textes de commission (uid `…BTC…`, URL non dérivable) et les textes du Sénat
    (uid `PIONSN…`) sont écartés — pas d'exposé exploitable.

    `legislatures` couvre typiquement la courante + la précédente : un dossier
    reporté après une dissolution garde son `dossierRef` d'origine — sans ce
    repli, il ne trouverait jamais son texte déposé (donc jamais d'exposé).
    """
    prefixes = tuple(f"DLR5L{leg}" for leg in legislatures)
    par_ref: dict[str, set[str]] = defaultdict(set)
    for brut in documents:
        doc = brut.get("document") or brut
        ref = doc.get("dossierRef") or ""
        uid = doc.get("uid") or ""
        if not ref.startswith(prefixes):
            continue
        # Textes AN uniquement (PIONAN… / PRJLAN… / PNREAN… pour les résolutions).
        if not (
            uid.startswith("PIONAN")
            or uid.startswith("PRJLAN")
            or uid.startswith("PNREAN")
        ):
            continue
        if (doc.get("denominationStructurelle") or "") not in _DENOMINATIONS_TEXTE:
            continue
        if (doc.get("provenance") or "") != "Texte Déposé":
            continue
        # uid dont on sait dériver l'URL du PDF (écarte « …BTC… », etc.).
        if url_page_texte(uid) is None:
            continue
        par_ref[ref].add(uid)
    return {ref: sorted(uids, key=_numero_uid) for ref, uids in par_ref.items()}


# Numéro de distribution AN dans un uid de document : dépôts (« …L17B0525 »)
# et textes de commission (« …L17BTC2866 ») partagent la même série — celle
# que cite le compte rendu des débats (« (n° 525) »). Les textes adoptés
# (« …BTA… », « …TAP… ») ont leur propre série : exclus (collision garantie).
_RE_NUMERO_DOC = re.compile(r"L(\d+)B(?:TC)?0*(\d+)$")


def construire_index_numeros(
    documents: list[dict], legislatures: tuple[int, ...]
) -> dict[str, set[int]]:
    """Table `dossierRef → numéros de distribution AN de ses documents`.

    Sert à relier un débat en séance (dont le titre cite « (n° X) ») à son
    dossier de façon certaine, à travers les renumérotations de la navette
    (chaque lecture/dépôt a son numéro, tous rattachés au même dossierRef).
    Un numéro porté par plusieurs dossiers (donnée sale) est écarté.

    `legislatures` couvre typiquement la courante + la précédente (dossier
    reporté après dissolution, cf. `construire_index_textes`).
    """
    prefixes = tuple(f"DLR5L{leg}" for leg in legislatures)
    par_numero: dict[int, set[str]] = defaultdict(set)
    for brut in documents:
        doc = brut.get("document") or brut
        ref = doc.get("dossierRef") or ""
        if not ref.startswith(prefixes):
            continue
        m = _RE_NUMERO_DOC.search(doc.get("uid") or "")
        if m and int(m.group(1)) in legislatures:
            par_numero[int(m.group(2))].add(ref)
    par_ref: dict[str, set[int]] = defaultdict(set)
    for numero, refs in par_numero.items():
        if len(refs) == 1:
            par_ref[next(iter(refs))].add(numero)
    return dict(par_ref)
