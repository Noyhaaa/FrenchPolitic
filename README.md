# Décrypté

**Le traducteur neutre et mobile des décisions de l'Assemblée nationale.**

Une application mobile qui répond en 30 secondes à une seule question, sans biais :
*« Sur quoi les députés ont-ils voté, et qu'est-ce que le texte dit ? »* — chaque
affirmation reliée à une source officielle, aucune opinion produite.

> Spécification produit complète : [`MVP_Assemblee_Nationale_v2.md`](MVP_Assemblee_Nationale_v2.md).
> Guide pour contribuer (conventions, règles de neutralité) : [`CLAUDE.md`](CLAUDE.md).

## Monorepo

```
/            App mobile — Expo / React Native / TypeScript
  src/       Écrans, composants, client API, hooks
backend/     API — FastAPI / PostgreSQL (voir backend/README.md)
```

Le frontend et le backend partagent le **même contrat de données** (les types
`Dossier` / `Scrutin`, en camelCase des deux côtés). L'unité centrale est le
**dossier** (un texte de loi), qui agrège ses **scrutins** successifs.

## Fonctionnalités (V1 — le « parcours en or »)

- **Fil des dossiers** : les derniers textes de loi, défilement infini. Un dossier
  qui reçoit un nouveau vote remonte avec un badge **« mis à jour »**.
- **Fiche dossier** : résumé neutre du texte, puis trois sections distinctes —
  les votes sur le texte (type du vote en clair : « Vote sur l'ensemble »,
  « Motion de censure », « Article 2 »…), les **amendements** (numéro, auteur,
  sort) et les **sous-amendements** (rattachés à leur amendement). Chaque ligne
  ouvre le détail de son vote ; les longues listes sont repliées (« Voir les N
  autres »). Les sources affichées sont celles du dossier — celles de chaque
  vote vivent sur sa fiche.
- **Fiche vote** : au tap sur un vote (ou un amendement) — type du vote et
  libellé officiel complet, résultat global, vote par groupe politique, et
  **noms des votants** (pour/contre/abstention) quand le scrutin public le
  permet. Le vote d'un amendement liste aussi ses sous-amendements.
- **Recherche** plein texte (titre, thème), tolérante aux accents.

Cache hors-ligne, accessibilité (statut jamais porté par la couleur seule),
transparence sur l'IA et « signaler une erreur ».

## Démarrer

**Backend** (données réelles de l'open data de l'Assemblée) :

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
createdb frenchpolitics                       # PostgreSQL requis
cp .env.example .env                          # puis renseigner DATABASE_URL
python -m app.ingestion.run --limit 300       # ingère 300 scrutins récents
uvicorn app.main:app --reload                 # http://localhost:8000/docs
```

**Application mobile** (dans un autre terminal, à la racine) :

```bash
npm install
npm run ios        # ou : npm run android / npm start
```

En dev, l'app découvre l'API via l'hôte Metro ; surchargeable avec
`EXPO_PUBLIC_API_URL`. Le backend doit tourner pour le premier chargement (ensuite
le cache prend le relais hors-ligne).

## État du projet

- ✅ App mobile V1 branchée sur l'API (fil, fiche, recherche, cache offline),
  centrée sur le **dossier** (texte + ses scrutins + badge « mis à jour »).
- ✅ API + ingestion réelle de l'open data AN (17e législature) dans PostgreSQL,
  **regroupée par dossier** (`dossierRef`).
- 🚧 Phase 2 : génération des résumés neutres (RAG + LLM) avec garde-fous
  éditoriaux et revue humaine, + amendements clés (aujourd'hui vides) — l'ossature
  (garde-fous, file de revue, interface LLM) est en place, la génération reste à
  brancher.

## Sources de données

Open data de l'Assemblée nationale (scrutins, organes) et, à terme, API Légifrance
via PISTE. Données non opposables : seuls les textes signés du Journal officiel font
foi. Voir §5 du MVP.
