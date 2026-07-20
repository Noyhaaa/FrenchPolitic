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
    assert body["objet"] == "Vote sur l'ensemble du texte (première lecture)"
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


def test_recap_mensuel(client):
    """La carte récap de l'accueil : votes du dernier mois actif, en camelCase.

    Les comptes sont recalculés depuis le seed pour ne pas figer de valeurs.
    """
    from app.data.seed import SEED_SCRUTINS

    r = client.get("/recap")
    assert r.status_code == 200
    body = r.json()
    assert body is not None

    mois_max = max(s.date[:7] for s in SEED_SCRUTINS if s.date)
    du_mois = [s for s in SEED_SCRUTINS if s.date[:7] == mois_max]
    assert body["annee"] == int(mois_max[:4])
    assert body["mois"] == int(mois_max[5:7])
    assert body["votes"] == len(du_mois)
    assert body["adoptes"] == sum(1 for s in du_mois if s.statut.value == "adopte")
    assert body["rejetes"] == sum(1 for s in du_mois if s.statut.value == "rejete")
    assert body["textes"] == len({s.dossier_id for s in du_mois})
    # Cohérence interne : adoptés + rejetés ≤ votes (le reste = en cours).
    assert body["adoptes"] + body["rejetes"] <= body["votes"]


def test_accueil_complet_en_une_reponse(client):
    """L'accueil est servi en une réponse : à la une + rangées par thème
    (l'affichage client est atomique, pas de remplissage progressif)."""
    r = client.get("/accueil")
    assert r.status_code == 200
    body = r.json()

    # À la une = dossier le plus récent du fil.
    fil = client.get("/dossiers").json()
    assert body["aLaUne"]["id"] == fil[0]["id"]

    # La une n'est pas répétée dans Aujourd'hui / Hier.
    ids_jour = {d["id"] for d in body["aujourdhui"]} | {
        d["id"] for d in body["hier"]
    }
    assert body["aLaUne"]["id"] not in ids_jour

    # Chaque thème présent a sa rangée ; « Autre » (si présent) est en dernier.
    themes = [s["theme"] for s in body["sections"]]
    assert set(themes) == {d["theme"] for d in fil}
    if "Autre" in themes:
        assert themes[-1] == "Autre"
    # Contenu en camelCase, borné par parSection.
    for section in body["sections"]:
        assert 1 <= len(section["dossiers"]) <= 10
        assert all(d["theme"] == section["theme"] for d in section["dossiers"])
