"""Tests de l'enrichissement exposé des motifs (textes_an)."""
from __future__ import annotations

from app.ingestion.textes_an import (
    construire_index_numeros,
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


def test_url_page_texte_garde_les_zeros_de_tete():
    # Le site AN pagine sur 4 chiffres : « l17b0647 » répond, « l17b647 » → 404.
    assert (
        url_page_texte("PIONANR5L17B0647")
        == "https://www.assemblee-nationale.fr/dyn/17/textes/l17b0647_proposition-loi"
    )


def test_url_page_texte_projet():
    assert url_page_texte("PRJLANR5L17B1154").endswith("l17b1154_projet-loi")


def test_url_page_texte_proposition_de_resolution():
    # uid des propositions de résolution déposées : préfixe PNREAN…, pas
    # PION…/PRJL… — suffixe d'URL dédié (vérifié en pratique sur senat.fr : le
    # même piège que « proposition-loi » vs « projet-loi » existe ici aussi).
    assert (
        url_page_texte("PNREANR5L17B0924")
        == "https://www.assemblee-nationale.fr/dyn/17/textes/l17b0924_proposition-resolution"
    )


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
    index = construire_index_textes(docs, legislatures=(17,))
    # Un seul dossier retenu, dépôt initial en tête (tri par numéro croissant).
    assert index == {
        "DLR5L17N100": ["PIONANR5L17B1337", "PIONANR5L17B1400"]
    }


def test_index_textes_inclut_les_propositions_de_resolution():
    """Une proposition de résolution déposée (uid PNREAN…) doit être indexée —
    oubliée jusqu'ici (seuls PIONAN/PRJLAN étaient reconnus), ce qui privait
    tout dossier de résolution de son exposé des motifs malgré un dossierRef
    officiel."""
    docs = [
        {
            "document": {
                "dossierRef": "DLR5L17N500",
                "uid": "PNREANR5L17B0924",
                "denominationStructurelle": "Proposition de résolution",
                "provenance": "Texte Déposé",
            }
        },
    ]
    assert construire_index_textes(docs, legislatures=(17,)) == {
        "DLR5L17N500": ["PNREANR5L17B0924"]
    }


def test_index_numeros_tous_documents_an_du_dossier():
    docs = [
        {"document": {"dossierRef": "DLR5L17N100", "uid": "PIONANR5L17B0525"}},
        # Texte de commission : même série de numérotation que les dépôts.
        {"document": {"dossierRef": "DLR5L17N100", "uid": "PIONANR5L17BTC0611"}},
        # Rapport : numéroté dans la même série, rattaché au dossier.
        {"document": {"dossierRef": "DLR5L17N100", "uid": "RAPPANR5L17B0598"}},
        # Texte adopté (série « TA » distincte) : exclu.
        {"document": {"dossierRef": "DLR5L17N100", "uid": "PIONANR5L17BTA0163"}},
        # Texte du Sénat (numérotation Sénat) : exclu.
        {"document": {"dossierRef": "DLR5L17N100", "uid": "PIONSNR5S459B0143"}},
        # Autre législature : exclue.
        {"document": {"dossierRef": "DLR5L16N300", "uid": "PIONANR5L16B0777"}},
    ]
    assert construire_index_numeros(docs, legislatures=(17,)) == {
        "DLR5L17N100": {525, 611, 598}
    }


def test_index_numeros_ecarte_les_numeros_ambigus():
    docs = [
        {"document": {"dossierRef": "DLR5L17N100", "uid": "PIONANR5L17B0525"}},
        {"document": {"dossierRef": "DLR5L17N200", "uid": "RAPPANR5L17B0525"}},
        {"document": {"dossierRef": "DLR5L17N200", "uid": "PIONANR5L17B0600"}},
    ]
    # 525 pointe deux dossiers (donnée sale) → écarté ; 600 conservé.
    assert construire_index_numeros(docs, legislatures=(17,)) == {
        "DLR5L17N200": {600}
    }
