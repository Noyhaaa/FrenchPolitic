"""Tests de l'exposé des motifs d'origine sénatoriale (textes_senat)."""
from __future__ import annotations

from app.ingestion.textes_senat import (
    ReferenceSenat,
    reference_senat,
    source_senat,
    urls_pdf_senat,
)

# Extrait type d'un PDF de transmission AN (dispositif seul, cite le Sénat).
_TRANSMISSION = (
    "N° 1435\nASSEMBLÉE NATIONALE\nPROPOSITION DE LOI\nADOPTÉE PAR LE SÉNAT,\n"
    "relative à la raison impérative d'intérêt public majeur,\n"
    "TRANSMISE PAR M. LE PRÉSIDENT DU SÉNAT\n"
    "Voir les numéros :\nSénat : 452, 584, 585 et T.A. 121 (2024-2025).\n"
    "Article unique\nLe code est ainsi modifié…"
)


def test_reference_senat_prend_le_premier_numero_et_la_session():
    ref = reference_senat(_TRANSMISSION)
    assert ref == ReferenceSenat(annee="24", numero=452)


def test_reference_senat_none_si_pas_une_transmission():
    # Un texte AN normal (avec son propre exposé) ne cite pas le Sénat ainsi.
    texte = "PROPOSITION DE LOI\nEXPOSÉ DES MOTIFS\nMesdames, Messieurs, …"
    assert reference_senat(texte) is None


def test_reference_senat_none_si_numero_absent():
    texte = "PROPOSITION DE LOI ADOPTÉE PAR LE SÉNAT, TRANSMISE PAR…"
    assert reference_senat(texte) is None


def test_urls_proposition_essaie_ppl_puis_pjl():
    ref = ReferenceSenat(annee="24", numero=452)
    assert urls_pdf_senat(ref, projet=False) == [
        "https://www.senat.fr/leg/ppl24-452.pdf",
        "https://www.senat.fr/leg/pjl24-452.pdf",
    ]


def test_urls_projet_essaie_pjl_puis_ppl():
    ref = ReferenceSenat(annee="25", numero=470)
    assert urls_pdf_senat(ref, projet=True) == [
        "https://www.senat.fr/leg/pjl25-470.pdf",
        "https://www.senat.fr/leg/ppl25-470.pdf",
    ]


def test_urls_numero_court_est_zero_padde():
    """Un numéro Sénat < 100 doit être zéro-paddé sur 3 chiffres (« pjl25-024.pdf »,
    pas « pjl25-24.pdf ») — sans ça, l'URL répond 404 sur senat.fr (vécu en
    production : les 5 URLs testées avec un numéro court échouaient toutes ;
    même piège que les zéros de tête obligatoires côté AN, `textes_an.py`)."""
    ref = ReferenceSenat(annee="25", numero=24)
    assert urls_pdf_senat(ref, projet=True) == [
        "https://www.senat.fr/leg/pjl25-024.pdf",
        "https://www.senat.fr/leg/ppl25-024.pdf",
    ]
    ref_tres_court = ReferenceSenat(annee="24", numero=7)
    assert urls_pdf_senat(ref_tres_court, projet=False) == [
        "https://www.senat.fr/leg/ppl24-007.pdf",
        "https://www.senat.fr/leg/pjl24-007.pdf",
    ]


def test_source_senat_pointe_la_page_lisible():
    src = source_senat("https://www.senat.fr/leg/ppl24-452.pdf")
    assert src.url == "https://www.senat.fr/leg/ppl24-452"
    assert src.libelle == "Texte déposé au Sénat"
