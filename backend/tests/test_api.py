"""Tests de l'API — vérifient le contrat consommé par l'app mobile."""
from __future__ import annotations


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_list_dossiers_camel_case(client):
    r = client.get("/dossiers")
    assert r.status_code == 200
    items = r.json()
    assert len(items) >= 1
    # Le contrat est en camelCase (miroir du type frontend).
    first = items[0]
    assert "titreClair" in first
    assert "tempsLectureSec" in first
    assert "nombreScrutins" in first


def test_list_sorted_desc(client):
    r = client.get("/dossiers")
    dates = [i["date"] for i in r.json()]
    assert dates == sorted(dates, reverse=True)


def test_get_dossier_detail(client):
    r = client.get("/dossiers/dos-logement-2026")
    assert r.status_code == 200
    body = r.json()
    assert body["titreClair"] == "Faciliter l'accès au logement"
    assert body["resume"]["resume"][0]["sourceId"]  # ancrage présent
    # Le dossier liste ses votes en version compacte (objet + résultat) ;
    # le détail (groupes, nominatif) se charge via GET /scrutins/{id}.
    assert len(body["scrutins"]) >= 1
    premier = body["scrutins"][0]
    assert "objet" in premier and "resultat" in premier
    assert "positionsGroupes" not in premier


def test_get_scrutin_detail(client):
    r = client.get("/scrutins/scr-2026-0412b")
    assert r.status_code == 200
    body = r.json()
    assert body["dossierId"] == "dos-logement-2026"
    assert body["objet"] == "Vote sur l'ensemble du texte"
    assert len(body["positionsGroupes"]) >= 1


def test_get_scrutin_404(client):
    r = client.get("/scrutins/inexistant")
    assert r.status_code == 404


def test_dossier_mise_a_jour_expose(client):
    # Le dossier logement porte un badge « mis à jour » dans le seed (§7.7).
    r = client.get("/dossiers/dos-logement-2026")
    assert r.json()["miseAJour"]["label"]


def test_get_dossier_404(client):
    r = client.get("/dossiers/inexistant")
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
