"""Tests de l'enrichissement des amendements (contenu + exposé sommaire)."""
from __future__ import annotations

import io
import json
import zipfile
from datetime import date

from app.ingestion.amendements import (
    AmendementEnrichi,
    construire_index,
    enrichir,
    nettoyer_html,
)


def _amendement_json(
    *,
    dossier_ref: str = "DLR5L17N53940",
    numero_long: str = "80",
    prefixe: str = "AN",
    dispositif: object = "<p>À l'alinéa&#160;2, supprimer les mots&nbsp;:</p>",
    expose: object = "<p>Cet amendement vise &#x00E0; clarifier le texte.</p>",
    division_titre: str = "Article 2",
    date_sort: str = "2026-07-02T18:00:00+02:00",
) -> dict:
    return {
        "amendement": {
            "uid": f"AM-{dossier_ref}-{numero_long}",
            "identification": {
                "numeroLong": numero_long,
                "prefixeOrganeExamen": prefixe,
            },
            "corps": {
                "contenuAuteur": {"dispositif": dispositif, "exposeSommaire": expose}
            },
            "pointeurFragmentTexte": {"division": {"titre": division_titre}},
            "cycleDeVie": {"dateSort": date_sort},
        }
    }


def _zip(*entrees: tuple[str, dict]) -> zipfile.ZipFile:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, contenu in entrees:
            zf.writestr(name, json.dumps(contenu))
    buf.seek(0)
    return zipfile.ZipFile(buf)


# --- nettoyer_html -----------------------------------------------------------


def test_nettoyer_html_decode_entites_et_paragraphes():
    brut = (
        "<p>&#x00C0; l'alin&#x00E9;a&#160;2, supprimer les mots&nbsp;:</p>"
        "<p>&#x00AB;&nbsp;autonomie&nbsp;&#x00BB;.</p>"
    )
    texte = nettoyer_html(brut)
    assert texte is not None
    assert "À l'alinéa 2, supprimer les mots :" in texte
    assert "\xa0" not in texte  # espace insécable normalisé
    assert "<p>" not in texte  # balises retirées
    assert "\n" in texte  # paragraphes séparés


def test_nettoyer_html_absent_renvoie_none():
    # L'open data met un dict {@xsi:nil} là où le champ est vide.
    assert nettoyer_html({"@xsi:nil": "true"}) is None
    assert nettoyer_html("") is None
    assert nettoyer_html("   ") is None
    assert nettoyer_html(None) is None


# --- construire_index --------------------------------------------------------


def test_index_ignore_amendements_de_commission():
    """Seuls les amendements de séance (préfixe « AN », numéro numérique) sont
    indexés — pas ceux de commission (« AE12 »)."""
    zf = _zip(
        ("json/DLR5L17N53940/T/AM1.json", _amendement_json(numero_long="80")),
        (
            "json/DLR5L17N53940/T/AM2.json",
            _amendement_json(numero_long="AE12", prefixe="CION_FIN"),
        ),
    )
    index = construire_index(zf)
    assert ("DLR5L17N53940", "80") in index
    assert ("DLR5L17N53940", "AE12") not in index
    assert len(index) == 1


def test_index_extrait_contenu_et_cible():
    zf = _zip(("json/DLR5L17N53940/T/AM1.json", _amendement_json()))
    [enrichi] = index_valeur(zf, "DLR5L17N53940", "80")
    assert enrichi.cible == "Article 2"
    assert "supprimer les mots" in (enrichi.dispositif or "")
    assert "clarifier le texte" in (enrichi.expose_sommaire or "")
    assert enrichi.date_sort == date(2026, 7, 2)


def index_valeur(zf, dref, num) -> list[AmendementEnrichi]:
    return construire_index(zf)[(dref, num)]


# --- enrichir ----------------------------------------------------------------


def test_enrichir_match_unique():
    zf = _zip(("json/DLR5L17N53940/T/AM1.json", _amendement_json(numero_long="80")))
    index = construire_index(zf)
    a = enrichir(index, "DLR5L17N53940", "80", date(2026, 7, 2))
    assert a is not None
    assert a.cible == "Article 2"


def test_enrichir_sans_ref_officielle_renvoie_none():
    """Un dossier reconstitué (TXT-…) n'a pas de dossierRef officiel → rien."""
    zf = _zip(("json/DLR5L17N53940/T/AM1.json", _amendement_json()))
    index = construire_index(zf)
    assert enrichir(index, "TXT-abc", "80", date(2026, 7, 2)) is None
    assert enrichir(index, None, "80", date(2026, 7, 2)) is None


def test_enrichir_numero_absent_renvoie_none():
    zf = _zip(("json/DLR5L17N53940/T/AM1.json", _amendement_json()))
    index = construire_index(zf)
    assert enrichir(index, "DLR5L17N53940", None, date(2026, 7, 2)) is None


def test_enrichir_ambiguite_resolue_par_date():
    """Deux lectures partagent (dossierRef, numéro) → on prend celle dont le sort
    tombe le jour du vote."""
    zf = _zip(
        (
            "json/DLR5L17N53940/T1/AM1.json",
            _amendement_json(
                numero_long="80", division_titre="Lecture 1",
                date_sort="2025-01-10T18:00:00+01:00",
            ),
        ),
        (
            "json/DLR5L17N53940/T2/AM2.json",
            _amendement_json(
                numero_long="80", division_titre="Lecture 2",
                date_sort="2026-07-02T18:00:00+02:00",
            ),
        ),
    )
    index = construire_index(zf)
    assert len(index[("DLR5L17N53940", "80")]) == 2
    a = enrichir(index, "DLR5L17N53940", "80", date(2026, 7, 2))
    assert a is not None and a.cible == "Lecture 2"


def test_enrichir_ambiguite_non_resolue_renvoie_none():
    """Aucune date de sort proche du vote → on n'attache rien (§2.5)."""
    zf = _zip(
        (
            "json/DLR5L17N53940/T1/AM1.json",
            _amendement_json(numero_long="80", date_sort="2025-01-10T18:00:00+01:00"),
        ),
        (
            "json/DLR5L17N53940/T2/AM2.json",
            _amendement_json(numero_long="80", date_sort="2025-02-10T18:00:00+01:00"),
        ),
    )
    index = construire_index(zf)
    # Vote en juillet 2026 : aucun candidat à ± 3 jours.
    assert enrichir(index, "DLR5L17N53940", "80", date(2026, 7, 2)) is None
