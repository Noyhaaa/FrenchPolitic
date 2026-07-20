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
(`src/api` + hooks `src/hooks`), avec cache offline (AsyncStorage), états
chargement / erreur / hors-ligne, et **pull-to-refresh** sur l'accueil comme
sur les fiches (les hooks exposent `refresh` — état `refreshing` distinct,
les données restent affichées pendant le rafraîchissement).

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
2. **Fiche dossier** (`DossierDetailScreen` → `useDossier`) : en tête, la
   **frise « Trajectoire à l'Assemblée »** (`TrajectoireNavette` +
   `phasesNavette` dans `format.ts`) — les phases de navette documentées par
   les libellés officiels des votes (1re lecture, CMP, lecture définitive…),
   statut d'une phase = son vote sur l'ensemble uniquement ; pas de données
   Sénat → pas d'étape Sénat, frise masquée si aucune phase documentée (§2.5).
   Puis résumé du texte,
   et **trois sections distinctes** — les **votes sur le texte**, avec le
   **vote décisif mis en avant** (`VoteDecisifCard` + `voteDecisif` dans
   `format.ts`, miroir de `_vote_decisif` backend : le vote sur l'ensemble le
   plus récent, carte accentuée + phrase explicative factuelle — c'est lui qui
   scelle l'adoption/le rejet, pas les votes d'articles ni les motions ; sans
   vote sur l'ensemble, rien n'est désigné §2.5) suivi de la **liste compacte
   des autres votes** (titre = **type du vote en clair** via `libelleScrutin` :
   « Vote sur l'ensemble », « Motion de censure », « Article 2 »… + statut +
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
   titre = type du vote en clair, **objet officiel complet en dessous**, puis —
   **sur toutes les fiches, quel que soit le type de vote** — le **Résultat du
   vote EN TÊTE** (§2.2 : voir le résultat tout de suite ; verdict, décomptes
   pour/contre/abstention, barre combinée + échelle, décomptes officiels).
   Ensuite, deux visages selon le vote :
   — **Vote sur le texte** : section **Vote par groupe**
   avec la **ligne de fracture** (`LigneFracture` : quels groupes ont
   majoritairement voté pour / contre / se sont abstenus — factuel, sourcé par
   le scrutin, jamais un jugement §7.4, masquée si unanimité), la ventilation
   détaillée par groupe et les **noms des votants** dépliables groupe par
   groupe quand le nominatif est disponible (§5.2).
   — **Vote d'amendement / sous-amendement** : PAS de section « Vote par
   groupe » — après le résultat, la carte **« L'amendement en 4 questions »**
   (`QuestionsAmendementCard`, `Scrutin.questions`) : « Pourquoi ? » (exposé
   sommaire, préfixé « Selon son auteur » §4.3), « Qu'est-ce qu'il
   changerait ? » (dispositif, conditionnel), « Qui était pour, qui était
   contre ? » (rendu déterministe depuis `positionsGroupes` via `LigneFracture`,
   unanimité affichée aussi), « Quel est le résultat ? » (déterministe, camp
   gagnant en premier). Suivent **ce qu'il change** (`dispositif`, factuel, en
   **carte** — même niveau visuel que le bloc auteur), **ce que dit l'auteur**
   (exposé sommaire, bloc attribué non neutre §4.3), et
   **ses sous-amendements** (chacun ouvrant sa propre fiche vote, empilée via
   `navigation.push`).
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
officiel quand il existe ; sinon **réconciliation** — le titre cité dans l'objet
du vote (« … de la proposition de loi visant à… ») est comparé aux titres
officiels de l'archive **dossiers législatifs** (`app/ingestion/dossiers_legislatifs.py`,
correspondance exacte **puis par signature** — fold sans espaces/ponctuation, qui
rattrape la saleté de l'archive : apostrophes, fautes de frappe « afin de​garantir »,
tirets — sans confondre ordinaire/organique ; non ambiguë) pour
retrouver le vrai `dossierRef` (et son lien officiel §7.5) ; sinon **texte de rattachement** →
dossier reconstitué à id stable `TXT-…` (dérivé de la **signature** du titre, pas
du simple fold — un même texte cité avec une apostrophe droite sur un scrutin et
courbe sur un autre fusionne en un seul dossier, ne se scinde pas en deux) ;
sinon singleton (motion de censure, déclaration — événements autonomes
légitimes dans le fil). La réconciliation couvre la législature **courante et
la précédente** (archive `download_dossiers` téléchargée deux fois, best-effort
sur la précédente) : un dossier **reporté après une dissolution** garde son
`dossierRef` d'origine (cas réel : « simplification de la vie économique »,
ref L16, encore voté en L17) — sans ce repli, un tel texte ne serait jamais
retrouvé par titre et se fragmenterait en `TXT-…`, perdant au passage son
exposé des motifs et l'enrichissement de ses amendements (la clé de jointure de
l'archive amendements est justement le `dossierRef`). Le garde-fou d'ambiguïté
(un titre → un seul dossier, jamais deviné) protège déjà contre une collision
de titre entre deux législatures. ~60 % des dossiers ont
ainsi leur page officielle. On n'importe PAS les titres de l'archive (minuscules,
fragmentés) : le libellé du scrutin est plus propre. Le fil ne montre donc que des
textes/dossiers, jamais un amendement isolé. Les votes d'amendement sont classés à
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
(`relu_par_humain`), sinon elle régénère. **Exposé des motifs** (le « pourquoi »
du texte) récupéré du **PDF officiel du texte déposé** (`app/ingestion/textes_an.py`
— URL dérivée de l'`uid` du document, extraction `pypdf`, dépôt initial d'abord ;
**repli Sénat** `app/ingestion/textes_senat.py` quand le texte AN n'est qu'une
transmission du Sénat → exposé récupéré sur senat.fr via le numéro cité)
et stocké dans `Dossier.expose_motifs` : contenu **non neutre** (point de vue de
l'auteur, §4.3), affiché en **bloc cité et attribué** (`ExposeMotifsCard`), jamais
fondu dans le résumé neutre. Pas besoin de Légifrance pour ça (option a ; la
neutralisation par LLM — option b — viendra avec un LLM assez fiable). **LLM local
(Ollama, `qwen3:14b`) branché sur deux tâches vérifiables** : (1) la
**classification de thème** (`app/ai/theme.py`) — les dossiers « Autre » de
l'heuristique reçoivent un thème choisi dans la **liste fermée**, sortie
hors-liste/verbeuse rejetée (repli) ; (2) les **4 questions citoyennes**
(`app/ai/questions.py`, servies dans `resume.questions`, affichées par
`QuestionsCard` en tête de fiche dossier) : « Pourquoi ont-ils débattu ? » (Q1)
et « Qu'est-ce que ça change ? » (Q4, toujours préfixée « Selon l'auteur du
texte », au conditionnel) sont générées **depuis l'exposé des motifs seul** puis
passées à des **contrôles déterministes** (`valider_reponse` : chiffres présents
dans la source, nature du texte non inversée, lexique, caractères hors français,
attribution) — rejet → « information non disponible » ; le **résultat** (Q3) est
composé **déterministiquement** depuis le vote décisif ; le **désaccord** (Q2)
vient des **comptes rendus des débats** (archive « SyceronBrut »,
`app/ingestion/debats.py`) : la section **« Explications de vote »** (chaque
groupe explique lui-même sa position) est reliée au dossier par le **numéro de
texte** cité au CR (joint aux numéros de tous les documents du dossier — robuste
à la navette et au vote solennel à J+n), sinon par **date de séance +
recoupement du titre** avec le vote sur l'ensemble — un candidat unique le
jour J ne suffit **jamais** sans recoupement (ambiguïtés écartées, §2.5),
puis chaque explication est **paraphrasée en une phrase, validée et attribuée à
son groupe** (§7.4) — le **sens pour/contre vient du scrutin**, jamais du LLM, et
jamais de synthèse éditoriale (« qui a raison »). ⚠️ On **ne génère toujours PAS** le
résumé/prose neutre par LLM (mistral 7B distordait les faits invisiblement ; seul
ce qui est attribuable à une source unique ET vérifiable déterministiquement
passe par le modèle) — le **gabarit déterministe reste seul maître du résumé**.
Les **votes d'amendement sont enrichis** de leur **contenu** (dispositif : ce que
l'amendement change), de leur **exposé sommaire** et de l'**article visé**, tirés
de l'open data AN (`app/ingestion/amendements.py` — archive
`amendements_div_legis`, ~300 Mo, **sans Légifrance**). Liaison au vote par
**(dossierRef, numéro)** parmi les amendements de **séance** (préfixe d'organe
« AN », numéro numérique = celui cité dans l'objet du vote) ; l'ambiguïté entre
lectures d'une même navette est levée par la **date** du vote (fenêtre ± 3 j),
sinon on n'attache rien (§2.5). ~77 % des votes d'amendement (5,5 k) reçoivent
ainsi leur contenu. Le **dispositif** est un extrait officiel factuel ; l'**exposé
sommaire** est le point de vue de l'auteur (non neutre, §4.3), affiché en **bloc
attribué** — déplié à la demande dans la liste (`AmendementRow`) **et** sur la
**fiche vote** de l'amendement/sous-amendement (`ScrutinDetailScreen`, où le
contenu est aussi porté par le `Scrutin`) —, jamais fondu dans le résumé neutre —
même traitement que l'exposé des motifs. Best-effort : un échec de
téléchargement de l'archive préserve l'enrichissement déjà en base. Chaque **vote
d'amendement porte aussi ses questions citoyennes** (`Scrutin.questions`,
générées à l'ingestion par `generer_questions_amendement`) : « pourquoi » (LLM ←
exposé sommaire, préfixe vérifié « Selon son auteur »), « changement » (LLM ←
dispositif, conditionnel) — mêmes contrôles déterministes (`valider_reponse`) —
et « résultat » déterministe (**camp gagnant en premier** : « rejeté par 268
voix contre 188 », jamais l'inverse) ; réponses validées réutilisées entre runs.
Le « qui était pour / contre » n'est pas généré : l'app le rend depuis
`positionsGroupes` (`LigneFracture`). Détails dans `backend/README.md`.

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
sort, `cible?` (article visé) + `dispositif?` (ce que l'amendement change) +
`exposeSommaire?` (le « pourquoi » côté auteur, non neutre) tirés de l'open data
AN quand disponibles, `scrutinId` vers la fiche vote, et `sousAmendements?` — les
**sous-amendements rattachés** à cet amendement, même forme), `sources`,
`statut`, `theme`, `dateDernierScrutin`, `miseAJour?` (badge §7.7). La partition
texte / amendement / sous-amendement se fait à l'ingestion (`est_amendement`,
`est_sous_amendement`, `numero_amendement_parent` sur l'objet du scrutin).
Un `Scrutin` est **vote-niveau** : `dossierId`, `objet` (ce sur quoi on a voté),
`statut`, `scrutinPublic`, `resultat`, `positionsGroupes` (avec `nomsPour` /
`nomsContre` / `nomsAbstention` optionnels — le **nominatif**, absent = masqué,
§2.5), `sousAmendements?` (pour le vote d'un amendement : ses sous-amendements),
`cible?` / `dispositif?` / `exposeSommaire?` (pour un vote d'amendement : son
contenu enrichi, cf. `amendements.py` — miroir des mêmes champs sur `Amendement`),
`questions?` (`QuestionsAmendement` : les questions citoyennes du vote
d'amendement — `pourquoi` / `changement` / `resultat`, générées à l'ingestion),
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
- **Enrichissement ingestion** : Légifrance/PISTE pour le **texte consolidé** des
  dossiers (ce que la loi change dans le code — l'**exposé des motifs** est déjà
  couvert via le PDF AN, cf. `textes_an.py`, et le **contenu des amendements** via
  l'open data AN, cf. `amendements.py`) ; planification du job de synchro
  (plusieurs fois/jour). *(La classification de thème est déjà affinée par un LLM
  local — cf. ci-dessous.)*
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
