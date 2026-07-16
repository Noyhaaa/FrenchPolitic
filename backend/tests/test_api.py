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
    # Les votes sur le texte n'incluent pas les votes d'amendement.
    assert all("amendement" not in s["objet"].lower() for s in body["scrutins"])
    # Les amendements sont listés à part, avec un lien vers leur scrutin.
    assert len(body["amendements"]) >= 1
    assert body["amendements"][0]["scrutinId"]


def test_amendement_scrutin_accessible(client):
    # Le vote d'un amendement (lié via scrutinId) est servi comme un scrutin.
    dossier = client.get("/dossiers/dos-logement-2026").json()
    sid = dossier["amendements"][0]["scrutinId"]
    r = client.get(f"/scrutins/{sid}")
    assert r.status_code == 200
    assert "amendement" in r.json()["objet"].lower()


def test_dossier_expose_les_sous_amendements(client):
    # Les sous-amendements sont rattachés à leur amendement parent (pas mélangés
    # au premier niveau), chacun lié à son propre scrutin.
    body = client.get("/dossiers/dos-logement-2026").json()
    am = next(a for a in body["amendements"] if a["id"] == "am-01")
    assert am["numero"] == "12"
    assert [sa["id"] for sa in am["sousAmendements"]] == ["sam-01"]
    assert am["sousAmendements"][0]["scrutinId"] == "scr-2026-0412-sam1"
    assert all(a["id"] != "sam-01" for a in body["amendements"])


def test_scrutin_amendement_liste_ses_sous_amendements(client):
    # La fiche vote d'un amendement liste ses sous-amendements…
    r = client.get("/scrutins/scr-2026-0412-am1")
    assert r.status_code == 200
    sous = r.json()["sousAmendements"]
    assert [sa["scrutinId"] for sa in sous] == ["scr-2026-0412-sam1"]
    # …et le vote du sous-amendement est servi comme n'importe quel scrutin.
    r2 = client.get("/scrutins/scr-2026-0412-sam1")
    assert r2.status_code == 200
    assert "sous-amendement" in r2.json()["objet"].lower()


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
