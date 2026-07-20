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
cascade : le `dossierRef` officiel quand il existe ; sinon **réconciliation** via
l'archive *dossiers législatifs* (le titre cité dans l'objet, comparé aux titres
officiels de la législature — **fold exact puis signature** : fold sans espaces ni
ponctuation, tolérant aux apostrophes et fautes de frappe de l'archive (« afin
de​garantir »), sans confondre ordinaire/organique ; non ambigu — retrouve le
vrai `dossierRef` et son lien officiel ; +24 dossiers récupérés) ; sinon le
**texte de rattachement**
(dossier reconstitué `TXT-…`, mention de lecture ignorée) ; sinon un dossier
singleton (motion de censure, déclaration…). Le fil n'expose ainsi que des
textes — jamais un vote d'amendement isolé — et ~60 % ont leur page officielle.
L'archive sert **uniquement** à retrouver le `dossierRef` : ses titres (en
minuscules, fragmentés) ne sont pas importés.
**Exposé des motifs** (`app/ingestion/textes_an.py`) : l'archive ne porte pas le
corps des textes (métadonnées seules), mais le **PDF du texte déposé** est
public et son URL se **dérive de l'`uid`** du document (`…L17B0369` →
`…/dyn/17/textes/l17b0369_proposition-loi.pdf` — les **zéros de tête sur
4 chiffres sont indispensables**, sans eux le site répond 404). On en extrait l'exposé des
motifs (via `pypdf`) en essayant les textes déposés du **dépôt initial** au plus
récent (l'exposé n'est que dans le dépôt initial ; les versions de navette ne
l'ont pas). **Repli Sénat** (`app/ingestion/textes_senat.py`) : quand le texte
AN n'est qu'une **transmission du Sénat** (dispositif seul, en-tête « PROPOSITION
DE LOI ADOPTÉE PAR LE SÉNAT, TRANSMISE PAR… »), l'exposé vit sur senat.fr ; le
PDF de transmission cite les numéros Sénat (« Sénat : 452 … (2024-2025) »), d'où
on dérive l'URL `senat.fr/leg/{ppl|pjl}{AA}-{num}.pdf` (les deux préfixes essayés)
et on extrait l'exposé avec le même découpage. Récupère ~38 dossiers d'origine
sénatoriale. Contenu **non neutre** (point de vue de l'auteur, §4.3) : stocké dans
un bloc `Dossier.expose_motifs` **cité et attribué** (source « Texte déposé » AN
ou « Texte déposé au Sénat »), jamais fondu dans le résumé neutre. Best-effort
(§2.5) : un dossier n'en porte pas si le PDF est absent ou illisible. Pas besoin
de Légifrance pour ça — Légifrance/PISTE ne servirait que pour le **texte
consolidé** (ce que la loi change dans le code), besoin différent.
Les votes d'amendement sont classés depuis l'objet officiel (amendement vs
sous-amendement, numéro et auteur extraits quand sans ambiguïté) ; chaque
**sous-amendement est rattaché à son amendement parent** (« … à l'amendement
n° X »), et le scrutin du parent embarque ses sous-amendements.

**Contenu des amendements** (`amendements.py`) : l'archive open data
`amendements_div_legis` (~300 Mo) fournit, par amendement, son **dispositif** (ce
qu'il change), son **exposé sommaire** (le pourquoi, côté auteur) et l'**article
visé** — sans Légifrance. Liaison au vote par **(dossierRef, numéro)** parmi les
amendements de **séance** (préfixe d'organe « AN », `numeroLong` numérique =
numéro cité dans l'objet du vote) ; deux lectures d'une même navette peuvent
partager la clé → désambiguïsation par la **date** du vote (fenêtre ± 3 j), sinon
rien n'est attaché (§2.5). Le HTML des champs est nettoyé (entités, `<p>`, espace
insécable). ~77 % des votes d'amendement (5,5 k) sont ainsi enrichis. L'exposé
sommaire est **non neutre** (§4.3) : affiché en bloc attribué côté app, jamais
fondu dans le résumé. Best-effort : un échec de téléchargement (archive lourde)
n'est pas fatal et **préserve l'enrichissement déjà en base** (fusion inter-runs).
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
    llm.py           Abstraction fournisseur (MockLLM · OllamaLLM local · Anthropic à venir)
    guardrails.py    Garde-fous : ancrage, lexique orienté, cohérence chiffres
    generation.py    Orchestration RAG → LLM → garde-fous → publier/revue
    theme.py         Classification de thème par LLM (liste fermée, repli heuristique)
    questions.py     Les 4 questions citoyennes (Q3 déterministe · Q1/Q4 LLM validées) + questions d'un vote d'amendement
    review_queue.py  File de revue humaine (§4.6)
  ingestion/         Alimentation depuis les sources officielles (§5)
    assemblee.py     Open data AN : download + parse_scrutin (pur, nominatif inclus) → ScrutinParse
    debats.py        Comptes rendus (SyceronBrut) : explications de vote par groupe + liaison au vote
    amendements.py   Contenu des amendements (dispositif + exposé sommaire + article visé) : archive AN → index (dossierRef, numéro)
    textes_an.py     Exposé des motifs : uid → URL du PDF officiel → extraction (pypdf)
    textes_senat.py  Repli exposé : texte de transmission Sénat → PDF senat.fr → extraction
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

**Exposé des motifs — bloc attribué (en place)**
- Récupéré du PDF officiel du texte déposé (`textes_an.py`), affiché comme un bloc
  **cité et attribué à l'auteur** — jamais fondu dans le résumé neutre (§4.3).
  Option (a) : contenu non neutre isolé. Option (b) différée : quand un LLM assez
  fiable sera dispo, l'exposé servira de **contexte** pour un « que change le
  texte » neutre passant les garde-fous — jamais affiché tel quel.

**Classification de thème par LLM local — Ollama (en place)**
- `app/ai/theme.py` : à l'ingestion, les dossiers que l'heuristique laisse en
  « Autre » sont soumis à un LLM local (Ollama) qui choisit un thème dans
  la **liste fermée**. Tâche à **faible risque éditorial** (une étiquette de
  rangement, pas de prose) : toute sortie hors-liste ou verbeuse est **rejetée**
  (repli « Autre »), et le badge du dossier n'est jamais un jugement. Actif via
  `LLM_PROVIDER=ollama` (`.env`) ; Ollama éteint → repli silencieux sur
  l'heuristique.

**Les 4 questions citoyennes — qwen3 local, sorties validées (en place)**
- `app/ai/questions.py`, rempli à l'ingestion dans `resume.questions` : «
  Pourquoi les députés ont-ils débattu ? · Quel était le principal désaccord ? ·
  Quel est le résultat du vote ? · Qu'est-ce que ça change concrètement ? » (§2.2).
- **Résultat (Q3)** : composé de façon **déterministe** depuis le vote décisif
  (recalculé à chaque run). **Désaccord (Q2)** : issu des **comptes rendus des
  débats** (`debats.py`, archive « SyceronBrut ») — la section « Explications de
  vote » (variantes « Explication de vote », « … communes » comprises), où
  chaque groupe explique lui-même sa position, est reliée au dossier d'abord par
  le **numéro de texte** cité au CR (« (n° 525) »), joint aux numéros de tous
  les documents du dossier (`construire_index_numeros` — robuste aux
  renumérotations de la navette, et au **vote solennel** tenu quelques jours
  après le débat, fenêtre 14 j) ; à défaut par **date de séance + recoupement
  du titre** (coefficient de recouvrement — labels courts du CR). Un candidat
  unique le jour J **ne suffit jamais** sans recoupement : plusieurs textes
  sont votés le même jour et l'archive ne capture pas toutes les séances
  (leçon d'un mauvais rattachement constaté en réel) ; cas ambigus écartés,
  §2.5. Chaque
  explication est **paraphrasée en une phrase par le LLM et validée**
  (`generer_desaccord` → `valider_reponse`), **attribuée à son groupe** (§7.4,
  même gabarit pour tous) ; le **sens pour/contre vient du scrutin**, jamais du
  LLM. Aucune synthèse éditoriale (« qui a raison ») : on juxtapose les positions
  que les groupes formulent eux-mêmes. Source = le compte rendu officiel (§7.5).
  **Pourquoi (Q1)** et **Changement (Q4)** : générés par
  `qwen3:14b` **uniquement depuis l'exposé des motifs** (+ titre), puis soumis à
  des **contrôles déterministes** (`valider_reponse`) : tout chiffre de la
  réponse doit exister dans la source, nature du texte non inversée
  (proposition↔projet), lexique évaluatif interdit, aucun caractère hors
  français (fuite CJK vue en épreuve), longueur bornée, et Q4 obligatoirement
  préfixée « Selon l'auteur du texte » (point de vue du déposant, §4.3, au
  conditionnel). Rejet → réponse absente (§2.5), jamais publiée. Les réponses
  validées sont **persistées et réutilisées** entre runs (pas de rappel du
  modèle sur une source stable).
- **Questions d'un vote d'amendement** (fiche vote) : mêmes principes,
  adaptés — `generer_questions_amendement` remplit `questions` sur le **scrutin**
  de chaque vote d'amendement (servi par `GET /scrutins/{id}`). **Pourquoi** :
  LLM depuis l'**exposé sommaire**, préfixe imposé et vérifié « Selon son
  auteur » (§4.3). **Changement** : LLM depuis le **dispositif** (extrait
  officiel), au conditionnel. **Résultat** : déterministe, camp **gagnant en
  premier** (« rejeté par 268 voix contre 188 » — jamais l'inverse, trompeur).
  Le « qui était pour / contre » n'est **pas** généré : l'app le rend depuis
  `positionsGroupes` (déterministe, sourcé par le scrutin). Réponses validées
  persistées et réutilisées entre runs ; sans contenu enrichi, seules les
  réponses déterministes existent (§2.5).
- Pourquoi qwen3 et pas mistral : épreuves comparées (2026-07-18) — mistral 7B
  changeait la nature du texte, convertissait les chiffres en lettres et glissait
  du cadrage ; qwen3:14b (raisonnement coupé, température 0) a tenu « information
  non disponible », l'attribution et les chiffres exacts. **On ne génère toujours
  PAS le résumé neutre par LLM** : le gabarit déterministe reste seul maître du
  résumé — seules des réponses **attribuables à une source unique et vérifiables
  déterministiquement** passent par le modèle.

**Stubs à interface stable (Phase 2)**
- Légifrance/PISTE : **texte consolidé** des dossiers (ce que la loi change dans
  le code — besoin distinct de l'exposé des motifs, déjà couvert). OAuth2 esquissé.
  *(Le **contenu** des amendements — dispositif, exposé sommaire, article visé —
  est désormais couvert par l'open data AN, cf. `amendements.py`, sans
  Légifrance.)*

## Règles produit qui contraignent le backend

Voir `../CLAUDE.md`. En résumé : neutralité (aucune phrase non sourcée), pas de
comblement quand une donnée manque (champ vide + `champs_non_documentes`), scrutins
publics uniquement pour le nominatif, données non opposables (seul le JO signé fait
foi). Les données de `app/data/seed.py` sont **fictives**.
