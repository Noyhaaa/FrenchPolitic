# Décrypté — Backend

API du projet **Décrypté** : servir aux clients mobiles des scrutins de
l'Assemblée nationale accompagnés d'un résumé neutre **systématiquement relié aux
sources officielles**. Le produit et ses règles sont décrits dans
[`../MVP_Assemblee_Nationale_v2.md`](../MVP_Assemblee_Nationale_v2.md) (le §6 décrit
cette architecture). Ce README documente le backend ; le [`../CLAUDE.md`](../CLAUDE.md)
donne le contexte global.

## Stack

FastAPI · Pydantic v2 · httpx · SQLAlchemy 2 (async) + asyncpg · PostgreSQL.
Python 3.12 (voir `.python-version`). pgvector prévu en Phase 2 (RAG).

## Démarrer

```bash
cd backend
pyenv shell 3.12.1                 # ou n'importe quel Python >= 3.11
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

uvicorn app.main:app --reload      # http://localhost:8000
pytest                             # tests (toujours sur les données seed)
```

⚠️ **Toujours activer le venv** avant une commande backend (sinon le Python
système sans dépendances est utilisé → `ModuleNotFoundError`).

Le backend de données est choisi par `REPOSITORY_BACKEND` : `memory` (données seed,
défaut) ou `postgres`. Les tests **forcent `memory`** (`tests/conftest.py`), donc ils
restent verts même si le `.env` pointe sur Postgres.

### Données réelles (ingestion open data → PostgreSQL)

```bash
createdb frenchpolitics

# .env (copié depuis .env.example) :
#   DATABASE_URL=postgresql+asyncpg://localhost:5432/frenchpolitics
#   REPOSITORY_BACKEND=postgres

# Ingère les scrutins publics de la 17e législature (open data AN).
python -m app.ingestion.run --limit 300     # 300 récents (~4 s) ; sans --limit = tout

# L'API sert alors la base ingérée (REPOSITORY_BACKEND=postgres via .env).
uvicorn app.main:app --reload
```

L'ingestion télécharge l'archive des scrutins + l'archive AMO (organes) pour
résoudre les noms de groupes, parse, contrôle la cohérence des décomptes et
upsert (idempotent). Chaque exécution est journalisée dans la table `sync_run`.

- Documentation interactive : http://localhost:8000/docs
- Santé : http://localhost:8000/health

## Endpoints (cœur produit, §3 du MVP)

| Méthode | Route              | Écran            | Description                                   |
|---------|--------------------|------------------|-----------------------------------------------|
| GET     | `/scrutins`        | Fil (1)          | Derniers scrutins, du plus récent au plus ancien |
| GET     | `/scrutins/{id}`   | Fiche (2)        | Détail : résumé sourcé, résultats, groupes    |
| GET     | `/recherche?q=`    | Recherche (3)    | Plein texte sur titre clair + officiel + thème |
| GET     | `/health`          | —                | Statut du service                             |

Le JSON est en **camelCase**, miroir exact du type `Scrutin` du frontend
(`src/types/index.ts`) : l'app peut remplacer `@/data` par un client API sans
transformation.

## Organisation

```
app/
  main.py            Assemblage FastAPI (CORS, routes, repository via lifespan)
  config.py          Réglages (env / .env)
  api/routes/        scrutins.py (fil, fiche, recherche), health.py
  schemas/           Contrat d'API (Pydantic, camelCase) = §5.3 du MVP
  domain/enums.py    Statuts, positions, niveaux de confiance…
  db/                models.py (scrutin, groupe, sync_run) · session.py (moteur async)
  repositories/      Protocole + in-memory (seed) + postgres (ingéré) — choix via config
  data/seed.py       Données FICTIVES de démonstration (portage du mock frontend)
  ai/                Pipeline de résumé (§4)
    prompts.py       Prompt système neutre (§4.1–4.3)
    rag.py           Construction du contexte ancré (RAG)
    llm.py           Abstraction fournisseur (MockLLM ; Anthropic en Phase 2)
    guardrails.py    Garde-fous : ancrage, lexique orienté, cohérence chiffres
    generation.py    Orchestration RAG → LLM → garde-fous → publier/revue
    review_queue.py  File de revue humaine (§4.6)
  ingestion/         Alimentation depuis les sources officielles (§5)
    assemblee.py     Open data AN : download + parse_scrutin (pur) → schéma Scrutin
    organes.py       Résolution des groupes (AMO) + couleurs
    normalize.py     Thème (heuristique), positions, décomptes
    sync.py          Job download → parse → cohérence → upsert (idempotent)
    run.py           CLI : python -m app.ingestion.run
    legifrance.py    API Légifrance via PISTE (OAuth2) — stub Phase 2
tests/               Tests API + garde-fous + génération + ingestion (+ repo pg opt-in)
```

## Ce qui est réel vs. à venir

**Implémenté et testé maintenant**
- Les 3 endpoints du cœur, servis au choix depuis l'in-memory (seed) ou
  **PostgreSQL** (données réelles ingérées).
- Le contrat d'API camelCase aligné sur le frontend.
- **Ingestion réelle de l'open data AN** (17e législature) : scrutins publics +
  résolution des groupes via l'archive AMO, parsing pur testé, contrôles de
  cohérence, upsert idempotent, journal `sync_run`.
- Les **garde-fous éditoriaux** (ancrage, lexique orienté avec accents, cohérence
  des chiffres, décision de revue) et le pipeline de génération avec `MockLLM`.

**Stubs à interface stable (Phase 2)**
- Génération réelle des résumés : RAG (pgvector) + client LLM Anthropic. En
  attendant, les scrutins ingérés ont un résumé vide (confiance « faible »,
  jamais comblé — §2.5) ; l'app affiche un placeholder et les données factuelles.
- Légifrance/PISTE : texte consolidé des dossiers (OAuth2 déjà esquissé).
- Amendements clés (nécessite les données de dossier).

## Règles produit qui contraignent le backend

Voir `../CLAUDE.md`. En résumé : neutralité (aucune phrase non sourcée), pas de
comblement quand une donnée manque (champ vide + `champs_non_documentes`), scrutins
publics uniquement pour le nominatif, données non opposables (seul le JO signé fait
foi). Les données de `app/data/seed.py` sont **fictives**.
