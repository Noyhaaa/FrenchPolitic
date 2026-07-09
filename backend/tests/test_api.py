"""Tests de l'API — vérifient le contrat consommé par l'app mobile."""
from __future__ import annotations


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_list_scrutins_camel_case(client):
    r = client.get("/scrutins")
    assert r.status_code == 200
    items = r.json()
    assert len(items) >= 1
    # Le contrat est en camelCase (miroir du type frontend).
    first = items[0]
    assert "titreClair" in first
    assert "tempsLectureSec" in first
    assert "nonVotants" in first["resultat"]


def test_list_sorted_desc(client):
    r = client.get("/scrutins")
    dates = [i["date"] for i in r.json()]
    assert dates == sorted(dates, reverse=True)


def test_get_scrutin_detail(client):
    r = client.get("/scrutins/scr-2025-0412")
    assert r.status_code == 200
    body = r.json()
    assert body["titreClair"] == "Faciliter l'accès au logement"
    assert body["resume"]["resume"][0]["sourceId"]  # ancrage présent
    assert "positionsGroupes" in body


def test_get_scrutin_404(client):
    r = client.get("/scrutins/inexistant")
    assert r.status_code == 404


def test_recherche(client):
    r = client.get("/recherche", params={"q": "logement"})
    assert r.status_code == 200
    results = r.json()
    assert any("logement" in i["titreClair"].lower() for i in results)


def test_recherche_vide_renvoie_tout(client):
    r = client.get("/recherche", params={"q": ""})
    assert r.status_code == 200
    assert len(r.json()) >= 1


def test_recherche_insensible_aux_accents(client):
    # « energie » (sans accent) doit trouver « Baisser la facture d'énergie ».
    r = client.get("/recherche", params={"q": "energie"})
    assert r.status_code == 200
    assert any("énergie" in i["titreClair"].lower() for i in r.json())
