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


def test_dossier_dit_qui_porte_le_texte(client):
    """L'initiative traverse l'API en camelCase — c'est le contrat que lit l'app.

    Trois formes coexistent volontairement dans le seed : un auteur parlementaire
    nommé et cliquable, le Gouvernement (sans personne), et un dossier sans
    initiative du tout — dont la fiche masque la ligne (§2.5).
    """
    depose = client.get("/dossiers/dos-logement-2026").json()["initiative"]
    assert depose["origine"] == "parlementaire"
    assert depose["nom"] == "Léa Marchand"
    # C'est `deputeId` — et lui seul — qui autorise l'app à ouvrir une fiche.
    assert client.get(f"/deputes/{depose['deputeId']}").status_code == 200
    assert depose["groupeNom"] and depose["groupeCouleur"]

    projet = client.get("/dossiers/dos-energie-2026").json()["initiative"]
    assert projet["origine"] == "gouvernement"
    # Le Gouvernement n'est pas une personne : ni nom, ni lien (§2.5).
    assert projet["nom"] is None and projet["deputeId"] is None

    assert client.get("/dossiers/dos-ecoles-2026").json()["initiative"] is None


def test_dossier_dit_ou_en_est_le_texte(client):
    """L'état traverse l'API en camelCase — la frise dit le passé, lui le présent.

    Trois formes dans le seed : une loi promulguée (avec sa référence complète et
    sa source Légifrance, §7.5), un texte encore en circulation, et un dossier
    sans état — dont la fiche masque le bloc (§2.5).
    """
    loi = client.get("/dossiers/dos-sante-2026").json()
    assert loi["etat"]["etat"] == "promulgue"
    assert loi["etat"]["numeroLoi"] == "2026-630"
    assert loi["etat"]["dateJournalOfficiel"] == "2026-07-14"
    # Le lien vers le texte en vigueur : porté par l'état, et affiché dans la
    # SEULE liste des documents du dossier. La carte « La loi » n'en montre que
    # la référence écrite — un lien lui suffisait à faire doublon (§7.5).
    assert loi["etat"]["urlLegifrance"]
    lien_en_vigueur = [
        s for s in loi["sources"] if s["url"] == loi["etat"]["urlLegifrance"]
    ]
    assert [s["libelle"] for s in lien_en_vigueur] == ["Texte en vigueur (Légifrance)"]

    en_cours = client.get("/dossiers/dos-energie-2026").json()["etat"]
    assert en_cours["etat"] == "en_navette"
    assert en_cours["etape"] == "Commission Mixte Paritaire"
    # Rien ne décrit l'étape suivante : ce n'est pas une donnée (§2.5).
    assert en_cours["numeroLoi"] is None

    assert client.get("/dossiers/dos-ecoles-2026").json()["etat"] is None


def test_loi_promulguee_porte_le_texte_vote(client):
    """La loi finale traverse l'API en camelCase — et c'est elle, non le texte
    déposé, qui fait foi sur un texte en vigueur.

    Le lien et le corps sont dissociés : le premier vaut pour toute loi dont
    l'archive désigne le texte, le second seulement s'il tient sous le cap.
    """
    loi = client.get("/dossiers/dos-sante-2026").json()
    assert loi["texteAdopte"]["source"]["libelle"] == "Texte voté par le Parlement"
    assert loi["texteAdopte"]["texte"] is not None

    # La Q4 en découle : aucune attribution (c'est un fait), à l'indicatif (le
    # texte s'applique), et sa source est la loi votée — pas le dépôt (§7.5).
    q4 = loi["resume"]["questions"]["changement"]
    assert not q4.startswith("Selon")
    assert q4.startswith("La loi punit")
    assert (
        loi["resume"]["questions"]["changementSource"]["url"]
        == loi["texteAdopte"]["source"]["url"]
    )

    # Un texte encore en navette n'a pas de loi finale : le bloc disparaît (§2.5).
    assert client.get("/dossiers/dos-energie-2026").json()["texteAdopte"] is None


def test_les_documents_du_dossier_sont_servis_dans_l_ordre(client):
    """§7.5 : la fiche indexe TOUS les documents du dossier, pas seulement la
    page du dossier législatif — et dans l'ordre de la vie du texte.

    Le compte rendu est typé `debats` (l'app lui associe 💬) ; les autres sont
    des textes. Chaque URL n'apparaît qu'une fois, même quand deux champs la
    portent (l'exposé des motifs et le dispositif sortent du même PDF).
    """
    loi = client.get("/dossiers/dos-sante-2026").json()
    assert [s["libelle"] for s in loi["sources"]] == [
        "Dossier législatif",
        "Texte déposé",
        "Rapport de la commission (n° 902)",
        "Rapport de la commission (n° 1450)",
        "Compte rendu de la séance (Assemblée nationale)",
        "Texte voté par le Parlement",
        "Texte en vigueur (Légifrance)",
    ]
    urls = [s["url"] for s in loi["sources"]]
    assert len(urls) == len(set(urls))
    par_type = {s["libelle"]: s["type"] for s in loi["sources"]}
    assert par_type["Compte rendu de la séance (Assemblée nationale)"] == "debats"

    # Les rapports traversent aussi l'API en camelCase — ils nourrissent la
    # liste, la fiche ne les rend pas à part.
    assert [s["libelle"] for s in loi["rapportsCommission"]] == [
        "Rapport de la commission (n° 902)",
        "Rapport de la commission (n° 1450)",
    ]


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


def test_recherche_termes_non_adjacents(client):
    # LE cas que l'ancienne recherche (un seul LIKE du bloc entier) ratait :
    # les deux mots existent, mais pas côte à côte.
    r = client.get("/recherche", params={"q": "acces logement"})
    assert r.status_code == 200
    assert any("logement" in i["titreClair"].lower() for i in r.json())


def test_recherche_atteint_les_reponses_citoyennes(client):
    # « zones tendues » n'apparaît que dans la Q1 du dossier logement : c'est
    # l'élargissement de l'index qui le rend trouvable (§3.3).
    r = client.get("/recherche", params={"q": "zones tendues"})
    assert r.status_code == 200
    assert [i["theme"] for i in r.json()] == ["Logement"]


def test_recherche_titre_avant_reponse_citoyenne(client):
    # Un mot présent dans un titre doit sortir avant le même mot trouvé
    # ailleurs dans l'index : la pertinence prime sur la date.
    r = client.get("/recherche", params={"q": "logement"})
    results = r.json()
    assert len(results) >= 1
    assert "logement" in results[0]["titreClair"].lower()


def test_recherche_tous_les_termes_exiges(client):
    r = client.get("/recherche", params={"q": "logement narcotrafic"})
    assert r.status_code == 200
    assert r.json() == []


def test_recherche_filtre_theme_seul(client):
    r = client.get("/recherche", params={"theme": "Logement"})
    assert r.status_code == 200
    results = r.json()
    assert results and all(i["theme"] == "Logement" for i in results)


def test_recherche_filtre_theme_avec_requete(client):
    r = client.get("/recherche", params={"q": "logement", "theme": "Énergie"})
    assert r.status_code == 200
    assert r.json() == []  # le thème restreint, il n'élargit pas


def test_themes(client):
    r = client.get("/themes")
    assert r.status_code == 200
    themes = r.json()
    # Uniquement des thèmes réellement présents (§2.5) : jamais un filtre vide.
    assert themes and all(t["nombre"] > 0 for t in themes)
    assert "Logement" in [t["nom"] for t in themes]


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


def test_accueil_votes_disputes_factuels_et_ordonnes(client):
    """La rangée « Les votes les plus disputés » ne sert que des faits.

    Chaque entrée porte ses décomptes officiels et son écart ; l'ordre suit
    l'indice de division, jamais un jugement sur la mesure (§4.3). Un même texte
    n'occupe pas la rangée à lui seul.
    """
    body = client.get("/accueil").json()
    votes = body["votesDisputes"]
    assert votes, "le seed doit produire au moins un vote classable"

    ecarts = []
    par_dossier = {}
    for v in votes:
        r = v["resultat"]
        # L'écart affiché est bien celui des décomptes servis.
        assert v["ecart"] == abs(r["pour"] - r["contre"])
        assert v["camps"] >= 1
        # Le vote s'ouvre : la fiche existe et porte les mêmes chiffres.
        fiche = client.get(f"/scrutins/{v['scrutinId']}")
        assert fiche.status_code == 200
        assert fiche.json()["resultat"] == r
        # Au Sénat, jamais de groupes divisés (délégation de vote, §7.4).
        if v["chambre"] == "senat":
            assert v.get("groupesDisperses") is None
        ecarts.append(v["ecart"])
        par_dossier[v["dossierId"]] = par_dossier.get(v["dossierId"], 0) + 1

    assert len(votes) <= 10
    assert max(par_dossier.values()) <= 2
    # L'ordre est déterministe : deux appels donnent la même rangée (l'indice
    # ne dépend que des décomptes, jamais de l'ordre de lecture en base).
    encore = client.get("/accueil").json()["votesDisputes"]
    assert [v["scrutinId"] for v in encore] == [v["scrutinId"] for v in votes]


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


def test_motion_de_censure_ne_se_lit_pas_comme_un_vote_pour_contre(client):
    """« 267 voix contre 0 » : l'article 49 de la Constitution ne fait recenser
    que les voix FAVORABLES à une motion de censure.

    L'app disait donc, sur les fiches les plus lues du pays, « rejeté par 0 voix
    contre 267 » — l'inverse du fait. La forme du scrutin traverse désormais
    l'API en camelCase, avec le seul rapport qui décide : voix recueillies /
    requises (§7.4).
    """
    dossier = client.get("/dossiers/dos-censure-2026").json()
    assert dossier["estEvenementAutonome"] is True
    q3 = dossier["resume"]["questions"]["resultat"]
    assert "289 requises" in q3
    assert "0 voix" not in q3

    scrutin = client.get("/scrutins/scr-2026-0420").json()
    assert scrutin["typeVote"] == "motion_censure"
    assert scrutin["suffragesRequis"] == 289
    # Le « contre » est à zéro **par construction** : c'est justement pour ça que
    # l'app ne l'affiche pas comme un camp.
    assert scrutin["resultat"]["contre"] == 0

    # La carte du fil doit pouvoir en faire autant, sans charger la fiche.
    fil = client.get("/dossiers?limit=100").json()
    carte = next(d for d in fil if d["id"] == "dos-censure-2026")
    assert carte["typeVoteDernierScrutin"] == "motion_censure"
    assert carte["suffragesRequisDernierScrutin"] == 289


def test_une_motion_de_censure_n_est_pas_un_vote_disputé(client):
    """L'écart entre deux camps n'a pas de sens quand un seul est compté : la
    rangée « votes les plus disputés » ne doit jamais la remonter."""
    accueil = client.get("/accueil").json()
    ids = {v["scrutinId"] for v in accueil["votesDisputes"]}
    assert "scr-2026-0420" not in ids
