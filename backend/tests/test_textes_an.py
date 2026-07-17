"""Tests de l'enrichissement exposé des motifs (textes_an)."""
from __future__ import annotations

from app.ingestion.textes_an import (
    construire_index_textes,
    decouper_expose,
    url_page_texte,
)

# Texte type extrait d'un PDF : page de garde, exposé, puis dispositif.
_TEXTE = (
    "N° 1337\nASSEMBLÉE NATIONALE\nPROPOSITION DE LOI visant à …\n"
    "EXPOSÉ DES MOTIFS\nMESDAMES, MESSIEURS,\n"
    "La présente proposition de loi vise à clarifier le régime applicable. "
    "Elle s'inscrit dans un contexte de réforme.\n"
    "PROPOSITION DE LOI\nArticle 1er\nLe code est ainsi modifié…"
)


def test_url_page_texte_proposition_retire_les_zeros():
    assert (
        url_page_texte("PIONANR5L17B0647")
        == "https://www.assemblee-nationale.fr/dyn/17/textes/l17b647_proposition-loi"
    )


def test_url_page_texte_projet():
    assert url_page_texte("PRJLANR5L17B1154").endswith("l17b1154_projet-loi")


def test_url_page_texte_senat_ou_hors_motif_est_none():
    assert url_page_texte("PIONSNR5S459B0861") is None  # texte du Sénat
    assert url_page_texte("PIONANR5L17BTC2866") is None  # pas de B{num}
    assert url_page_texte("RAPPANR5L17B0001") is None  # ni PION ni PRJL


def test_decoupe_expose_coupe_au_dispositif():
    expose = decouper_expose(_TEXTE)
    assert expose is not None
    # La salutation formulaire est retirée…
    assert not expose.lower().startswith("mesdames")
    assert expose.startswith("La présente proposition de loi")
    # …et le dispositif (en-tête MAJUSCULES + articles) n'est pas inclus.
    assert "Article 1er" not in expose
    assert "Le code est ainsi modifié" not in expose


def test_decoupe_expose_absent_rend_none():
    assert decouper_expose("Un texte sans exposé, juste des articles.") is None


def test_decoupe_expose_tronque_au_mot():
    long_texte = "EXPOSÉ DES MOTIFS\n" + "mot " * 2000
    expose = decouper_expose(long_texte, max_chars=100)
    assert expose is not None
    assert len(expose) <= 101  # 100 + l'ellipse
    assert expose.endswith("…")


def test_index_textes_ne_garde_que_les_textes_deposes_an():
    docs = [
        {  # dépôt initial (numéro le plus petit) : doit venir en tête
            "document": {
                "dossierRef": "DLR5L17N100",
                "uid": "PIONANR5L17B1337",
                "denominationStructurelle": "Proposition de loi",
                "provenance": "Texte Déposé",
            }
        },
        {  # re-dépôt de navette (numéro plus grand) : gardé mais après l'initial
            "document": {
                "dossierRef": "DLR5L17N100",
                "uid": "PIONANR5L17B1400",
                "denominationStructurelle": "Proposition de loi",
                "provenance": "Texte Déposé",
            }
        },
        {  # même dossier, texte adopté : ignoré (pas « Texte Déposé »)
            "document": {
                "dossierRef": "DLR5L17N100",
                "uid": "PIONANR5L17B1450",
                "denominationStructurelle": "Proposition de loi",
                "provenance": "Texte Adopté",
            }
        },
        {  # texte de commission (uid …BTC…, URL non dérivable) : ignoré
            "document": {
                "dossierRef": "DLR5L17N100",
                "uid": "PIONANR5L17BTC1500",
                "denominationStructurelle": "Proposition de loi",
                "provenance": "Texte Déposé",
            }
        },
        {  # texte du Sénat : ignoré (uid non AN)
            "document": {
                "dossierRef": "DLR5L17N200",
                "uid": "PIONSNR5S459B0861",
                "denominationStructurelle": "Proposition de loi",
                "provenance": "Texte Déposé",
            }
        },
        {  # autre législature : ignoré
            "document": {
                "dossierRef": "DLR5L16N300",
                "uid": "PIONANR5L16B0001",
                "denominationStructurelle": "Proposition de loi",
                "provenance": "Texte Déposé",
            }
        },
    ]
    index = construire_index_textes(docs, legislature=17)
    # Un seul dossier retenu, dépôt initial en tête (tri par numéro croissant).
    assert index == {
        "DLR5L17N100": ["PIONANR5L17B1337", "PIONANR5L17B1400"]
    }
