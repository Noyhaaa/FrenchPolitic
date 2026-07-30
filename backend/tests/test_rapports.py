"""Rapports de commission (purs, sans réseau).

Les documents ci-dessous reprennent la structure réelle de l'archive « dossiers
législatifs » : un `uid`, une `provenance` et une `classification.famille.depot`
qui distingue le rapport **sur le texte** (`RAPINIT`) des autres.
"""
from __future__ import annotations

from app.ingestion.rapports import (
    construire_index_rapports,
    numero_rapport,
    source_rapport,
    url_document,
)


def _document(
    uid: str,
    ref: str = "DLR5L17N50001",
    provenance: str = "Commission",
    depot: str | None = "RAPINIT",
) -> dict:
    return {
        "document": {
            "uid": uid,
            "dossierRef": ref,
            "provenance": provenance,
            "classification": {
                "famille": {"depot": {"code": depot}} if depot else None,
                "type": {"code": "RAPP"},
            },
        }
    }


def test_l_url_passe_par_le_resolveur_du_site():
    """Le slug de la commission n'est dans aucun champ de l'archive : c'est le
    site qui le résout (`/dyn/docs/{uid}` → 302 vers la page canonique).

    ⚠️ Sans `.pdf` : cette variante-là renvoie le fichier, celle-ci la page
    lisible — c'est elle que §7.5 demande.
    """
    assert url_document("RAPPANR5L17B0912") == (
        "https://www.assemblee-nationale.fr/dyn/docs/RAPPANR5L17B0912"
    )
    assert not url_document("RAPPANR5L17B0912").endswith(".pdf")


def test_le_numero_perd_ses_zeros_de_tete():
    """Ils comptent dans les URLs de textes, pas dans le libellé qu'on affiche —
    et c'est ce numéro-là que citent les comptes rendus (« (n° 912) »)."""
    assert numero_rapport("RAPPANR5L17B0912") == "912"
    assert numero_rapport("RAPPANR5L17B2732") == "2732"
    assert numero_rapport("RAPPANR5L17") is None


def test_le_libelle_porte_toujours_le_numero():
    """Même quand le dossier n'a qu'un rapport : c'est la clé qui relie ce lien
    au reste de ce qu'on affiche, et elle distingue les lectures."""
    source = source_rapport("RAPPANR5L17B0912")
    assert source is not None
    assert source.libelle == "Rapport de la commission (n° 912)"
    assert source.type == "texte"


def test_un_uid_sans_numero_ne_produit_pas_de_lien():
    """On ne devine pas une URL (§2.5)."""
    assert source_rapport("RAPPANR5L17") is None


def test_seuls_les_rapports_sur_le_texte_sont_retenus():
    """`RAPAUT` et `RAPTACOM` (50 documents dans l'archive) ne répondent pas à la
    même question, et rien dans la source ne dit comment les nommer sans se
    tromper. Un rapport d'information (`RINFAN…`) n'est pas non plus un rapport
    sur l'initiative, pas plus qu'un document de provenance « Séance »."""
    documents = [
        _document("RAPPANR5L17B0912"),
        _document("RAPPANR5L17B0913", depot="RAPAUT"),
        _document("RAPPANR5L17B0914", depot="RAPTACOM"),
        _document("RAPPANR5L17B0915", depot=None),
        _document("RINFANR5L17B0916"),
        _document("RAPPANR5L17B0917", provenance="Séance"),
        # Rapport du Sénat : pas d'URL dérivable de la même façon.
        _document("RAPPSNR5S479B0918"),
    ]
    index = construire_index_rapports(documents, (17,))
    assert index == {"DLR5L17N50001": ["RAPPANR5L17B0912"]}


def test_les_rapports_sont_ordonnes_par_numero():
    """Un dossier peut en porter plusieurs (80 cas) : un par lecture. L'ordre des
    numéros est celui dans lequel le texte les a produits."""
    documents = [
        _document("RAPPANR5L17B2732"),
        _document("RAPPANR5L17B0912"),
        _document("RAPPANR5L17B1450"),
    ]
    index = construire_index_rapports(documents, (17,))
    assert index["DLR5L17N50001"] == [
        "RAPPANR5L17B0912",
        "RAPPANR5L17B1450",
        "RAPPANR5L17B2732",
    ]


def test_la_legislature_precedente_est_couverte():
    """Un dossier reporté après une dissolution garde son `dossierRef` d'origine :
    ses rapports vivent dans l'archive de la législature précédente."""
    documents = [
        _document("RAPPANR5L16B0500", ref="DLR5L16N49866"),
        _document("RAPPANR5L15B0400", ref="DLR5L15N40000"),
    ]
    index = construire_index_rapports(documents, (17, 16))
    assert set(index) == {"DLR5L16N49866"}
