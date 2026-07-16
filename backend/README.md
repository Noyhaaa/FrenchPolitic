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

L'ingestion télécharge l'archive des scrutins + l'archive AMO (organes **et
acteurs** : groupes + annuaire des députés pour le vote nominatif), parse,
contrôle la cohérence des décomptes, **regroupe les scrutins par dossier** et
upsert (idempotent) : les dossiers (liste compacte des votes) et le détail de
chaque vote (table `scrutin`, avec les noms des votants). Regroupement en
cascade : le `dossierRef` officiel quand il existe ; sinon le **texte de
rattachement extrait de l'objet du vote** (« … de la proposition de loi visant
à… » → dossier reconstitué, id stable `TXT-…`, mention de lecture ignorée) ;
sinon le scrutin reste un dossier singleton (motion de censure, déclaration…).
Le fil n'expose ainsi que des textes — jamais un vote d'amendement isolé.
Les votes d'amendement sont classés depuis l'objet officiel (amendement vs
sous-amendement, numéro et auteur extraits quand sans ambiguïté) ; chaque
**sous-amendement est rattaché à son amendement parent** (« … à l'amendement
n° X »), et le scrutin du parent embarque ses sous-amendements.
Les sources du dossier se limitent au **niveau dossier** (page du dossier
législatif) — la source de chaque vote reste sur son scrutin, pas de doublon.
Lorsqu'un nouveau scrutin rejoint un dossier déjà en base, celui-ci est marqué
« mis à jour » (§7.7). Chaque exécution est journalisée dans la table `sync_run`.

> Le modèle de tables a évolué (dossiers allégés + table `scrutin` au format
> vote-détaillé). Après mise à jour du code, **relancer l'ingestion** pour
> recréer/remplir les tables (les payloads précédents ne sont plus au bon format ;
> au besoin `DROP TABLE dossier; DROP TABLE scrutin;` avant).

- Documentation interactive : http://localhost:8000/docs
- Santé : http://localhost:8000/health

## Endpoints (cœur produit, §3 du MVP)

| Méthode | Route              | Écran            | Description                                   |
|---------|--------------------|------------------|-----------------------------------------------|
| GET     | `/accueil`         | Accueil (1)      | Écran complet en une réponse : à la une, aujourd'hui/hier, rangées par thème |
| GET     | `/recap`           | Accueil (1)      | Activité du dernier mois actif (votes, adoptés/rejetés, textes) |
| GET     | `/dossiers`        | Fil paginé       | Derniers dossiers, du plus récent au plus ancien |
| GET     | `/dossiers/{id}`   | Fiche dossier (2)| Résumé sourcé + votes sur le texte + amendements |
| GET     | `/scrutins/{id}`   | Fiche vote (3)   | Détail d'un vote (texte ou amendement) : groupes + nominatif |
| GET     | `/recherche?q=`    | Recherche (4)    | Plein texte sur titre clair + officiel + thème |
| GET     | `/health`          | —                | Statut du service                             |

Le JSON est en **camelCase**, miroir exact des types `Dossier` / `Scrutin` du
frontend (`src/types/index.ts`) : l'app consomme l'API sans transformation.
L'unité exposée est le **dossier** (texte de loi) ; sa fiche liste les votes **sur
le texte** en version compacte (`ScrutinResume`) et, à part, les **amendements**
(numéro/auteur extraits de l'objet officiel, `scrutinId` de leur vote, et leurs
**sous-amendements** imbriqués). Le détail d'un vote (ventilation par groupe,
noms des votants) se charge à la demande via `/scrutins/{id}` — un vote
d'amendement n'apparaît donc pas dans la liste des votes du texte, et le scrutin
d'un amendement expose `sousAmendements` pour que sa fiche vote les liste.

## Organisation

```
app/
  main.py            Assemblage FastAPI (CORS, routes, repository via lifespan)
  config.py          Réglages (env / .env)
  api/routes/        dossiers.py (fil, fiche dossier, fiche vote, recherche), health.py
  schemas/           Contrat d'API (Pydantic, camelCase) = §5.3 — Dossier + Scrutin
  domain/enums.py    Statuts, positions, niveaux de confiance…
  db/                models.py (dossier, scrutin, groupe, sync_run) · session.py (moteur async)
  repositories/      Protocole + in-memory (seed) + postgres (ingéré) — choix via config
  data/seed.py       Dossiers FICTIFS de démonstration
  ai/                Pipeline de résumé (§4)
    prompts.py       Prompt système neutre (§4.1–4.3)
    rag.py           Construction du contexte ancré (RAG)
    llm.py           Abstraction fournisseur (MockLLM ; Anthropic en Phase 2)
    guardrails.py    Garde-fous : ancrage, lexique orienté, cohérence chiffres
    generation.py    Orchestration RAG → LLM → garde-fous → publier/revue
    review_queue.py  File de revue humaine (§4.6)
  ingestion/         Alimentation depuis les sources officielles (§5)
    assemblee.py     Open data AN : download + parse_scrutin (pur, nominatif inclus) → ScrutinParse
    organes.py       Résolution des groupes (AMO) + couleurs + annuaire des députés
    normalize.py     Thème (heuristique), positions, décomptes
    sync.py          Job download → parse → regroupement par dossier → upsert (idempotent)
    run.py           CLI : python -m app.ingestion.run
    legifrance.py    API Légifrance via PISTE (OAuth2) — stub Phase 2
tests/               Tests API + garde-fous + génération + ingestion (+ repo pg opt-in)
```

## Ce qui est réel vs. à venir

**Implémenté et testé maintenant**
- Les 4 endpoints du cœur, servis au choix depuis l'in-memory (seed) ou
  **PostgreSQL** (données réelles ingérées).
- Le contrat d'API camelCase aligné sur le frontend.
- **Ingestion réelle de l'open data AN** (17e législature) : scrutins publics +
  résolution des groupes **et des députés** (annuaire acteurs) via l'archive AMO,
  parsing pur testé (**vote nominatif** inclus), contrôles de cohérence,
  **regroupement par dossier** + badge « mis à jour » à la fusion, upsert
  idempotent (dossiers + détail des votes), journal `sync_run`.
  Le nominatif n'existe pas dans le seed (on n'invente pas des noms, §2.5) :
  il apparaît sur les données réellement ingérées.
- Les **garde-fous éditoriaux** (ancrage, lexique orienté avec accents, cohérence
  des chiffres, décision de revue) et le pipeline de génération avec `MockLLM`.

**Résumé neutre par gabarit (en place)**
- Généré à l'ingestion, **sans LLM ni clé API** : `app/ai/faits.py` (faits des
  scrutins) → `rag.py` (passages étiquetés) → `gabarit.py` (5 phrases sourcées) →
  garde-fous (`generer_resume`). Chaque phrase porte son `source_id` et passe
  l'ancrage / le lexique / les chiffres par construction (confiance « moyenne »).
- Un LLM (AnthropicLLM derrière `LLMClient`, ou Ollama en local) pourra reformuler
  le style plus tard sans toucher au reste ; la fusion ne préserve un résumé que
  s'il est **relu par un humain**, sinon elle régénère depuis les faits à jour.

**Stubs à interface stable (Phase 2)**
- Enrichissement Légifrance/PISTE : texte consolidé + métadonnées d'amendement
  (le résumé pourra alors s'appuyer sur l'exposé des motifs, pas seulement les
  scrutins).
- Légifrance/PISTE : texte consolidé des dossiers (OAuth2 déjà esquissé).
- Métadonnées d'amendement enrichies (texte complet, exposé sommaire) — pour
  l'instant un amendement = l'objet officiel de son scrutin (numéro/auteur
  extraits de ce libellé) + son sort.

## Règles produit qui contraignent le backend

Voir `../CLAUDE.md`. En résumé : neutralité (aucune phrase non sourcée), pas de
comblement quand une donnée manque (champ vide + `champs_non_documentes`), scrutins
publics uniquement pour le nominatif, données non opposables (seul le JO signé fait
foi). Les données de `app/data/seed.py` sont **fictives**.
