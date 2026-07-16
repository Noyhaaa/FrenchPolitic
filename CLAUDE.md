# Décrypté — Application mobile de compréhension des votes de l'Assemblée nationale

## Le produit en une phrase

Le **traducteur neutre et mobile des décisions de l'Assemblée** : répondre en
30 secondes à « Sur quoi les députés ont-ils voté, et que dit le texte ? », chaque
affirmation reliée à une source officielle, sans opinion produite.

Vision long terme : le « Duolingo de la démocratie ». Le MVP prouve qu'on peut faire
comprendre un vote en 30 s sans trahir les faits.

La spécification complète du produit est dans [`MVP_Assemblee_Nationale_v2.md`](MVP_Assemblee_Nationale_v2.md).
**Ce fichier fait foi** pour toute question de périmètre, de neutralité ou de priorité.

## Structure du dépôt (monorepo)

```
/            Frontend mobile Expo / React Native / TypeScript (racine)
  src/       Code de l'app (voir « Architecture du code » plus bas)
backend/     API FastAPI (Python) — voir backend/README.md
```

Frontend et backend partagent **le même contrat de données** : les types
`Dossier` / `Scrutin` du frontend (`src/types/index.ts`) et les schémas Pydantic
du backend (`backend/app/schemas/`) sont des miroirs (camelCase des deux côtés).
Toute évolution du modèle doit être répercutée **des deux côtés**.

## État actuel

**Frontend** — parcours en or de la V1 (§2.2 du MVP), **branché sur l'API**
(`src/api` + hooks `src/hooks`), avec cache offline (AsyncStorage) et états
chargement / erreur / hors-ligne.

> **Unité centrale = le Dossier (texte de loi)**, pas le scrutin. Un dossier
> agrège ses **scrutins** successifs (navette), ses amendements et un résumé
> neutre. Un dossier remonte dans le fil avec un badge **« mis à jour »** quand un
> nouveau scrutin s'y rattache (§7.7). Ce choix intègre en V1 ce qui était prévu
> en V2 — le verrou §2.4 sur le suivi de dossier est **levé** en conséquence.

Quatre écrans du cœur de valeur :
1. **Accueil façon Netflix** (`HomeScreen` → `useAccueil`, `GET /accueil`) :
   l'écran complet arrive en **une réponse** (affichage atomique, pas de
   remplissage progressif) — hero « à la une », rangées horizontales
   **Aujourd'hui** / **Hier** (masquées si vides, §2.5), carte **récap du
   dernier mois actif** (`useRecap`, `GET /recap`), puis **une rangée par
   thème**. Pas de défilement infini : la recherche sert à aller au-delà.
   Les vignettes affichent la **nature du texte** (« Projet de loi »…) quand
   le titre la porte (`natureTexte` — rien d'affiché sinon, on ne déduit pas).
2. **Fiche dossier** (`DossierDetailScreen` → `useDossier`) : résumé du texte,
   puis **trois sections distinctes** — la **liste compacte des votes sur le
   texte** (titre = **type du vote en clair** via `libelleScrutin` : « Vote sur
   l'ensemble », « Motion de censure », « Article 2 »… + statut +
   micro-résultat ; objet non reconnu restitué tel quel, §2.5), les
   **Amendements** (ligne compacte via `AmendementRow` : numéro + sort + auteur,
   sans répéter la formule « l'amendement n° X de M. Y »), et les
   **Sous-amendements** (avec rappel de l'amendement parent). Chaque ligne ouvre
   la fiche vote. Un vote d'amendement n'apparaît **que** dans sa section (un
   sous-amendement que dans la sienne), et les listes longues sont repliées
   au-delà de 4 éléments (« Voir les N autres… »). Les **Sources officielles**
   de la fiche sont de **niveau dossier** uniquement (dossier législatif…) — la
   source de chaque vote vit sur sa propre fiche, pas de doublon.
3. **Fiche vote** (`ScrutinDetailScreen` → `useScrutin`, `GET /scrutins/{id}`) :
   titre = type du vote en clair, **objet officiel complet en dessous**, puis
   résultat global, ventilation par groupe, et **noms des votants** dépliables
   groupe par groupe quand le nominatif est disponible (§5.2). Sert aussi bien un
   vote sur le texte qu'un vote d'amendement ; le vote d'un amendement liste en
   plus **ses sous-amendements** (chacun ouvrant sa propre fiche vote, empilée
   via `navigation.push`).
4. **Recherche simple** (`SearchScreen` → `useDossierSearch`, avec debounce)

L'URL de l'API est dérivée de l'hôte Metro en dev (`src/api/config.ts`),
surchargeable via `EXPO_PUBLIC_API_URL`. **Le backend doit tourner** pour un
premier chargement ; ensuite le cache prend le relais hors-ligne. (L'ancien mock
`src/data/mockScrutins.ts` a été supprimé — la référence de données fictives est
désormais le seed backend `backend/app/data/seed.py`.)

Plus deux écrans « à venir » (`AssistantScreen`, `ProfileScreen`) présents dans la
tab bar mais hors périmètre V1 (§2.3 / §2.4).

**Backend** — API FastAPI servant les endpoints du cœur (`/accueil` — écran
d'accueil complet en une réponse —, `/dossiers`, `/dossiers/{id}`,
`/scrutins/{id}`, `/recherche`, `/recap` — activité du dernier mois actif).
Le détail d'un dossier reste
**léger** (liste de `ScrutinResume`) ; le détail complet d'un vote — groupes et
**vote nominatif** (noms des députés, résolus via l'annuaire acteurs de l'archive
AMO) — vit dans la table `scrutin` et est servi à la demande. Deux backends de
données commutables via
`REPOSITORY_BACKEND` : `memory` (données seed, défaut) ou `postgres` (données
ingérées). En dev, `backend/.env` fixe `REPOSITORY_BACKEND=postgres` + `DATABASE_URL`
pour que l'API serve la base ; **les tests forcent `memory`** (`tests/conftest.py`)
et restent donc sur le seed. **Phase 1 faite** : ingestion réelle de l'open data AN
(17e législature) — scrutins publics + groupes (archive AMO) — parsée, contrôlée,
**regroupée par dossier** et upsertée dans PostgreSQL (SQLAlchemy
async), via `python -m app.ingestion.run`. Regroupement en cascade : `dossierRef`
officiel quand il existe, sinon **texte de rattachement extrait de l'objet du
vote** (« … de la proposition de loi visant à… » → dossier reconstitué à id
stable `TXT-…`), sinon singleton (motion de censure, déclaration — événements
autonomes légitimes dans le fil). Le fil ne montre donc que des textes/dossiers,
jamais un amendement isolé. Les votes d'amendement sont classés à
l'ingestion (`est_amendement` / `est_sous_amendement` sur l'objet officiel, avec
extraction du numéro et de l'auteur quand ils sont sans ambiguïté) et chaque
sous-amendement est **rattaché à son amendement parent** (« … à l'amendement
n° X ») ; le scrutin du parent embarque ses sous-amendements pour la fiche vote.
La fusion inter-runs pose le badge « mis à jour » quand un nouveau scrutin
(texte, amendement ou sous-amendement) rejoint un dossier connu. Les **sources
du dossier** sont de niveau dossier uniquement (la page du dossier législatif) —
la source de chaque vote reste sur son scrutin, servie par sa fiche vote. Le
**résumé neutre est généré à l'ingestion par un gabarit déterministe** (`app/ai/`
— `faits` → `rag` → `gabarit` → garde-fous, dans `generer_resume`), ancré
uniquement sur les faits des scrutins (nature, trajectoire, résultat du vote
décisif, positions des groupes, comptes d'amendements), **sans LLM ni clé API** :
5 phrases sourcées, chacune portant son `source_id`, qui passent les **garde-fous
éditoriaux** (§4.4) par construction. Un LLM (AnthropicLLM derrière `LLMClient`)
pourra fluidifier le style plus tard sans changer ce contrat ; la fusion
inter-runs ne préserve un résumé que s'il a été **relu par un humain**
(`relu_par_humain`), sinon elle régénère. Reste vide/non comblé (§2.5) la liste
des **amendements enrichis** (texte complet, exposé sommaire — Phase 2 Légifrance).
Détails dans `backend/README.md`.

## Stack & commandes

- **Expo** SDK 54, **React Native** 0.81, **React** 19, **TypeScript** strict.
- Navigation : `@react-navigation` (native-stack + bottom-tabs).
- Alias d'import : `@/*` → `src/*` (résolu par TypeScript **et** Metro).

```bash
npm start          # démarre Metro (QR code)
npm run ios        # build + simulateur iOS
npm run android    # build + émulateur Android
npx tsc --noEmit   # vérification de types (à lancer avant de conclure)
```

Pas de suite de tests côté frontend. Vérification = `tsc --noEmit` + `expo export`
(le bundle Metro attrape les erreurs de résolution/import).

**Backend** (dans `backend/`, voir son README) :

```bash
cd backend && source .venv/bin/activate   # venv Python 3.12 (indispensable)
python -m app.ingestion.run --limit 300   # ingère l'open data AN dans Postgres
uvicorn app.main:app --reload             # http://localhost:8000/docs (sert la base via .env)
pytest                                     # suite de tests (forcés sur seed)
```

Piège fréquent : lancer une commande backend **sans** activer le venv → le Python
système (sans les deps) est utilisé et échoue (`ModuleNotFoundError`).

## Architecture du code

```
App.tsx                      Racine : GestureHandlerRootView + SafeAreaProvider + RootNavigator
src/
  theme/                     Design system (source unique de vérité visuelle)
    colors.ts                Palette sombre éditoriale (prototype new_screens), statuts, couleurs de vote
    spacing.ts               Échelle d'espacement + rayons
    typography.ts            Échelle typographique (serif titres · sans corps · mono métadonnées)
  types/index.ts             Modèle de données (miroir des schémas backend, §5.3 MVP)
  api/                       Client HTTP : config (URL), client (fetch+timeout), dossiers+scrutins, cache offline
  hooks/                     useDossiers / useDossier / useScrutin / useDossierSearch (chargement + cache + états)
  constants/themes.ts        Emoji + teintes par thème
  utils/format.ts            Formatage dates, libellés de statut/position, temps de lecture
  components/                Composants réutilisables (DossierCard, StateViews…)
  screens/                   Un écran par fichier (barrel dans index.ts)
  navigation/
    types.ts                 Types de navigation (RootStack + MainTabs)
    MainTabs.tsx             Bottom tabs : Accueil · Recherche · Assistant · Profil
    RootNavigator.tsx        Stack : MainTabs + DossierDetail + ScrutinDetail
```

Flux : `RootNavigator` → `MainTabs` (tabs) → `DossierDetail` puis `ScrutinDetail`
sont au niveau du stack racine (accessibles depuis Accueil ET Recherche, couvrent
la tab bar).

## Règles produit qui contraignent le code

Ces règles viennent du MVP et **priment sur les préférences esthétiques**. Toute UI
qui affiche du contenu de scrutin doit les respecter.

1. **Neutralité (§2.5, §7).** On n'affiche jamais une phrase qui ne peut pas être
   rattachée à une source officielle. Donnée manquante → on **masque le bloc** ou on
   affiche « information non disponible », jamais une supposition. Voir les blocs
   conditionnels dans `DossierDetailScreen` (`pourquoi`, `changement`,
   `publicConcerne`, `amendements`).
2. **Symétrie entre groupes (§7.4).** Même gabarit, même longueur pour tous les
   groupes politiques. `GroupVoteRow` est identique pour chacun.
3. **Statut jamais porté par la couleur seule (RGAA, §8).** Toujours icône + libellé
   texte. Voir `StatusBadge` et `Legend` (carrés + labels).
4. **Réversibilité (§7.5).** L'utilisateur atteint la source brute en 1 tap
   (`SourceLink` ouvre l'URL officielle).
5. **Transparence IA (§7.6).** Tout résumé affiche `AiNotice` (« généré
   automatiquement… relu par un humain » + niveau de confiance + « signaler une
   erreur »).
6. **Scrutins publics uniquement pour le nominatif (§5.2).** Le champ
   `scrutinPublic` (au niveau de chaque `Scrutin`) conditionne l'affichage du « vote
   par groupe » ; sinon on explique l'absence de ventilation (vote à main levée).
7. **Langue simple (§8).** Phrases courtes, pas de jargon non expliqué.
8. **Mise à jour factuelle (§7.7).** Le badge « mis à jour » d'un dossier reste
   descriptif (« Nouveau vote »), jamais évaluatif. Il signale qu'un scrutin s'est
   ajouté, pas un jugement sur l'évolution du texte.

## Conventions de code

- **Langue.** Code, données et UI en **français** (identifiants, libellés, commentaires,
  noms de champs de types type `titreClair`, `positionMajoritaire`). On reste cohérent
  avec l'existant.
- **Imports.** Toujours l'alias `@/…`, jamais de chemins relatifs profonds (`../../`).
  Exports groupés via les `index.ts` de `components/` et `screens/`.
- **Style.** `StyleSheet.create` en bas de fichier. **Aucune valeur codée en dur** pour
  couleurs / espacements / typo — tout passe par `@/theme`. Ajouter une couleur = la
  déclarer dans `colors.ts`.
- **Accessibilité.** `accessibilityRole` / `accessibilityLabel` sur les éléments
  interactifs et les badges ; `importantForAccessibility="no"` sur les emojis
  décoratifs.
- **Safe area.** Les écrans gèrent eux-mêmes `useSafeAreaInsets` (padding top/bottom).
- **Icônes.** Emojis (pas de librairie d'icônes installée). Si on ajoute des icônes
  vectorielles un jour, passer par `@expo/vector-icons`.
- **Commentaires.** Référencer la section du MVP concernée (`§3.2`, `§4.5`…) quand un
  choix découle d'une règle produit — c'est la convention en place.

## Modèle de données (résumé)

Défini dans `src/types/index.ts`. **Entité centrale `Dossier`** (un texte de loi) :
`resume` (résumé neutre ancré + confiance + `champsNonDocumentes`), `scrutins`
(les **votes sur le texte**, résumés), `amendements` (les **votes d'amendement** :
`numero?` + `auteur?` extraits de l'objet officiel quand sans ambiguïté, objet,
sort, `scrutinId` vers la fiche vote, et `sousAmendements?` — les
**sous-amendements rattachés** à cet amendement, même forme), `sources`,
`statut`, `theme`, `dateDernierScrutin`, `miseAJour?` (badge §7.7). La partition
texte / amendement / sous-amendement se fait à l'ingestion (`est_amendement`,
`est_sous_amendement`, `numero_amendement_parent` sur l'objet du scrutin).
Un `Scrutin` est **vote-niveau** : `dossierId`, `objet` (ce sur quoi on a voté),
`statut`, `scrutinPublic`, `resultat`, `positionsGroupes` (avec `nomsPour` /
`nomsContre` / `nomsAbstention` optionnels — le **nominatif**, absent = masqué,
§2.5), `sousAmendements?` (pour le vote d'un amendement : ses sous-amendements),
`sources`. La fiche dossier n'embarque que des `ScrutinResume` (liste
compacte) ; le `Scrutin` complet est servi par `GET /scrutins/{id}`. Le fil et la
recherche renvoient un `DossierListItem` allégé (dont `nombreScrutins` et
`miseAJour`). Types clés : `StatutScrutin` (`adopte` | `rejete` | `en_cours`),
`PositionVote`, `NiveauConfiance`. Ce modèle est le **contrat de l'API** (miroir
camelCase des schémas Pydantic backend, à répercuter des deux côtés).

## Prochaines étapes (backlog priorisé, cf. §10 MVP)

- **Backend Phase 2** : brancher la génération réelle des résumés (RAG pgvector +
  client LLM Anthropic derrière `LLMClient`) au niveau du **dossier**, puis publier
  via les garde-fous / file de revue (déjà en place). Objectif : remplir le résumé
  aujourd'hui vide des dossiers Postgres.
- **Enrichissement ingestion** : Légifrance/PISTE (texte des dossiers) et
  **métadonnées d'amendement** (texte complet, exposé sommaire — aujourd'hui
  l'amendement se résume à l'objet du scrutin, son numéro/auteur extraits de ce
  libellé, et son sort), classification de thème plus fine
  (beaucoup de dossiers ressortent en « Autre »), planification du job de synchro
  (plusieurs fois/jour).
- **V1.1** : fiche député (lecture seule), filtres de recherche, partage.
- **V2** : assistant IA en questions pré-cadrées.

## Pièges à éviter

- Le suivi de dossier (badge « mis à jour ») est **intégré en V1** — c'était une
  levée assumée du verrou §2.4. Restent hors périmètre V1 : notifications push,
  suivi de député, comparateur, assistant à champ libre, prédiction d'impact.
- Ne pas introduire d'adjectifs évaluatifs ou de jugements dans les données seed ou
  les libellés (« ambitieux », « insuffisant », « controversé »… interdits, §4.3).
  Cela vaut aussi pour le label de `miseAJour` (rester factuel).
- Les données de `backend/app/data/seed.py` sont **fictives et illustratives** — ne
  pas les présenter comme réelles.
- ⚠️ Le fichier `MVP_Assemblee_Nationale_v2.md` cité comme référence **n'est pas
  présent dans le dépôt** (jamais committé). Les `§x.y` renvoient à ce document
  externe. Le décalage introduit ici (dossier-centré + §7.7 + levée §2.4) doit y
  être reporté quand il sera versionné.
