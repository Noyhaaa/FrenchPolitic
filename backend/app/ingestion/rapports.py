"""Le rapport de commission d'un dossier — le document qui manquait vraiment.

Tous les autres documents d'un dossier (texte déposé, compte rendu, texte voté,
Légifrance) étaient déjà quelque part dans le payload ; le rapport de commission,
lui, n'était pas ingéré. Il est pourtant dans l'archive *dossiers législatifs*
déjà téléchargée à chaque run : 584 rapports `RAPPAN…` de provenance
« Commission », dont 534 classés `RAPINIT` — le rapport **sur l'initiative**,
c'est-à-dire sur le texte. 203 de nos 255 dossiers officiels en ont un.

⚠️ **Le slug de la commission n'est dans aucun champ de l'archive.** L'URL
publique d'un rapport est `/dyn/17/rapports/cion_lois/l17b0912_rapport-fond`, et
rien ne donne `cion_lois` — pas même l'`organeRef` du rapport, dont 4 des 12
valeurs les plus fréquentes ne sont même pas des commissions (`due`, `ots`…).
Une table de slugs codés en dur vieillirait mal et ne couvrirait pas les
commissions spéciales, dont il se crée une par texte.

Mais le site **résout le slug lui-même** : `/dyn/docs/{uid}` répond 302 vers la
page canonique, et 404 sur un uid inconnu. C'est donc, comme partout ailleurs,
une **dérivation depuis l'`uid`** — et elle se vérifie.
"""
from __future__ import annotations

import asyncio
import re
from collections import defaultdict

import httpx

from app.schemas import SourceOfficielle

# Résolveur canonique de l'Assemblée : il connaît le slug de commission et le
# type de rapport, nous non. ⚠️ **Sans `.pdf`** — cette variante-là renvoie le
# fichier, celle-ci la page lisible, qui est ce que §7.5 demande.
_URL_DOCUMENT = "https://www.assemblee-nationale.fr/dyn/docs/{uid}"

# Numéro de distribution dans l'uid d'un rapport (« RAPPANR5L17B0912 » → 912).
# Mêmes zéros de tête que partout : ils comptent dans l'URL, pas dans le libellé.
_RE_NUMERO = re.compile(r"L\d+B0*(\d+)$")

# Rapport **sur une initiative** : le rapport qui porte sur le texte examiné.
# Les autres familles présentes dans l'archive (`RAPAUT` — rapport d'une autre
# nature, `RAPTACOM` — texte adopté par la commission, 50 documents en tout) ne
# répondent pas à la même question, et rien dans la source ne dit comment les
# nommer sans se tromper (§2.5).
_FAMILLE_RAPPORT_SUR_TEXTE = "RAPINIT"

# Requêtes de vérification en vol. Même ordre de grandeur que les portraits :
# ~260 HEAD par run complet, quelques secondes.
CONCURRENCE_RAPPORTS = 8


def url_document(uid: str) -> str:
    """URL publique d'un document de l'Assemblée, dérivée de son `uid`."""
    return _URL_DOCUMENT.format(uid=uid)


def numero_rapport(uid: str) -> str | None:
    """Numéro de distribution du rapport (« 912 »), ou None si l'uid n'en porte pas."""
    m = _RE_NUMERO.search(uid)
    return m.group(1) if m else None


def source_rapport(uid: str) -> SourceOfficielle | None:
    """Lien vers un rapport de commission, libellé avec **son numéro**.

    Le numéro y figure toujours, même quand le dossier n'a qu'un rapport : c'est
    lui que cite le compte rendu des débats (« (n° 912) »), donc la clé qui relie
    ce lien au reste de ce qu'on affiche. Sans numéro, pas de lien — un uid dont
    on ne sait rien lire n'a pas d'URL sûre (§2.5).
    """
    numero = numero_rapport(uid)
    if numero is None:
        return None
    return SourceOfficielle(
        type="texte",
        libelle=f"Rapport de la commission (n° {numero})",
        url=url_document(uid),
    )


def construire_index_rapports(
    documents: list[dict], legislatures: tuple[int, ...]
) -> dict[str, list[str]]:
    """Table `dossierRef → uids des rapports de commission`, du plus ancien au plus récent.

    Triés par **numéro croissant**, donc de la première lecture à la dernière —
    l'ordre dans lequel le texte les a produits (80 dossiers en ont plusieurs).

    `legislatures` couvre typiquement la courante + la précédente, comme
    `textes_an.construire_index_textes` : un dossier reporté après une
    dissolution garde son `dossierRef` d'origine.
    """
    prefixes = tuple(f"DLR5L{leg}" for leg in legislatures)
    par_ref: dict[str, set[str]] = defaultdict(set)
    for brut in documents:
        doc = brut.get("document") or brut
        ref = doc.get("dossierRef") or ""
        uid = doc.get("uid") or ""
        if not ref.startswith(prefixes):
            continue
        # Rapports de l'Assemblée seulement : ceux du Sénat (`RAPPSN…`) n'ont pas
        # d'URL dérivable de la même façon, et le Sénat est hors périmètre ici.
        if not uid.startswith("RAPPAN"):
            continue
        if doc.get("provenance") != "Commission":
            continue
        famille = ((doc.get("classification") or {}).get("famille") or {}).get("depot")
        if (famille or {}).get("code") != _FAMILLE_RAPPORT_SUR_TEXTE:
            continue
        if numero_rapport(uid) is None:
            continue
        par_ref[ref].add(uid)
    return {
        ref: sorted(uids, key=lambda u: int(numero_rapport(u) or 0))
        for ref, uids in par_ref.items()
    }


async def verifier_rapports(
    uids: list[str], timeout: float = 15.0
) -> list[SourceOfficielle]:
    """Les rapports dont l'URL **répond**, dans l'ordre reçu.

    Même doctrine que `attacher_portraits` : l'URL est dérivée, donc on ne
    l'attache qu'après l'avoir vérifiée. `/dyn/docs/{uid}` répond 302 vers la page
    canonique quand le document existe, 404 sinon — un 404 ne produit donc aucun
    lien (§2.5), et une panne réseau n'en produit aucun non plus sans faire
    échouer le run.

    On ne suit **pas** la redirection : la présence du `location` suffit à
    prouver que le site sait résoudre l'uid, et c'est l'URL stable
    (`/dyn/docs/…`) qu'on veut stocker, pas la cible du jour.
    """
    semaphore = asyncio.Semaphore(CONCURRENCE_RAPPORTS)
    confirmes: dict[str, SourceOfficielle] = {}

    async def verifier(client: httpx.AsyncClient, uid: str) -> None:
        source = source_rapport(uid)
        if source is None:
            return
        async with semaphore:
            try:
                reponse = await client.head(source.url)
            except httpx.HTTPError:
                return  # injoignable : pas de lien, pas d'échec
        redirige = reponse.is_redirect and bool(reponse.headers.get("location"))
        if reponse.status_code == 200 or redirige:
            confirmes[uid] = source

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            await asyncio.gather(*(verifier(client, uid) for uid in uids))
    except httpx.HTTPError:
        pass
    return [confirmes[uid] for uid in uids if uid in confirmes]
