# Décrypté — guide de travail sur le dépôt

Application mobile qui répond en 30 secondes à **« Sur quoi les parlementaires
ont-ils voté, et que dit le texte ? »**. Chaque affirmation est reliée à une source
officielle, et l'app ne produit aucune opinion. À terme, ce doit être le
« Duolingo de la démocratie ». Le MVP doit prouver qu'on peut faire comprendre un
vote en 30 s sans trahir les faits.

## Où est la vérité

| Document | Rôle |
|---|---|
| [`MVP_Assemblee_Nationale_v2.md`](MVP_Assemblee_Nationale_v2.md) | **Fait foi** pour le périmètre, la neutralité et les priorités. Les `§x.y` du code y renvoient. |
| Ce fichier | Fait foi là où le produit a dépassé le MVP : l'app est **centrée sur le dossier** (pas sur le scrutin), le badge « mis à jour » (§7.7), le suivi de dossier et le compte facultatif en V1 (levée du verrou §2.4). |
| [`backend/README.md`](backend/README.md) | Détail de chaque source, de l'ingestion, de l'IA et des endpoints. **À lire avant de toucher `app/ingestion` ou `app/ai`.** |
| [`README.md`](README.md) | Présentation du produit et tableau des sources open data. |

Pour le *pourquoi* d'une décision, regarde d'abord les commentaires du code
(ils citent la section du MVP), puis le backend README, puis l'historique git de
ce fichier.

## Doctrine éditoriale (non négociable)

Ces règles priment sur toute préférence esthétique ou technique.

1. **Neutralité (§2.5).** Aucune phrase ne s'affiche si elle ne peut pas être
   rattachée à une source officielle. Quand une donnée manque, on **masque le
   bloc** ou on écrit « information non disponible ». On ne suppose jamais rien.
   Face à un appariement ambigu, on **n'attache rien**. On ne devine jamais.
2. **Symétrie entre groupes (§7.4).** Tous les groupes et toutes les origines
   reçoivent le même gabarit et la même longueur (`GroupVoteRow`, `InitiativeLigne`).
3. **Jamais la couleur seule (RGAA, §8).** Un statut porte toujours un glyphe et
   un libellé (`StatusBadge`, `Legend`).
4. **Réversibilité (§7.5).** La source officielle est à un tap (`SourceLink`).
5. **Transparence IA (§7.6).** Tout contenu généré affiche `AiNotice`.
6. **Nominatif réservé aux scrutins publics (§5.2).** C'est `scrutinPublic` qui
   le conditionne. Sinon, on explique l'absence : `modalite` dit comment la
   décision a été prise (main levée, 49.3, art. 151-7), et
   `constants/modalites.ts` écrit la phrase. Le `resultat` d'un tel vote vaut 0
   par contrat : **ne l'affiche jamais comme des voix**.
7. **Langue simple (§8).** Un terme de jargon s'explique via le glossaire,
   jamais par une définition écrite en dur dans un écran.
8. **Mise à jour factuelle (§7.7).** Le badge dit « Nouveau vote ». Il n'évalue
   jamais.

Ce qui en découle concrètement :
- **Aucun adjectif évaluatif.** Cela vaut pour les données, les libellés et le
  seed. La liste noire est `LEXIQUE_ORIENTE` dans `app/ai/guardrails.py`
  (« ambitieux », « nécessaire », « historique », « massif »…).
- **La parole d'un auteur reste attribuée.** L'exposé des motifs et l'exposé
  sommaire s'affichent en bloc cité, jamais fondus dans le texte neutre. Le fait
  officiel prime sur la parole du déposant, et la loi votée prime sur le texte
  déposé.
- **Jamais de prédiction.** Aucun champ ne décrit une étape à venir, aucune
  phrase n'est au futur. Le calendrier parlementaire est une décision politique,
  pas une donnée.
- **Pas de métrique que la source ne soutient pas.**
  - Aucun **taux de participation** : l'open data ne recense que les votants
    d'un scrutin public.
  - Au **Sénat**, ni « contre son groupe » ni cohésion : les bulletins y sont
    déposés par un délégué de groupe.
- **Une préférence ordonne, elle ne filtre jamais.** Les thèmes suivis remontent
  sur l'accueil, aucun n'est masqué, et l'écran dit que l'ordre a changé.
- **On ne promet rien que l'app ne fasse pas.** Pas de « en direct »
  (l'ingestion est par lots), pas de push (rien n'émet), et pas de
  `expo-notifications` tant que rien n'émet.

### Ce que le LLM a le droit de faire

- Le **résumé neutre** est **déterministe** : `app/ai/` enchaîne faits → rag →
  gabarit → garde-fous. **Ne jamais le confier à un LLM** : un modèle déforme les
  faits d'une manière que les garde-fous lexicaux ne voient pas. L'échafaudage
  qui le permettait a été supprimé, ne le réintroduis pas.
- Le LLM (Ollama, config `LLM_*` dans `backend/.env`, `mistral-small:24b` sur un
  serveur distant) ne sert qu'à des **tâches vérifiables** :
  - le **thème**, dans la liste fermée `THEMES` ;
  - les **publics concernés**, dans une liste fermée de 19, 3 au plus ;
  - la **Q1** et la **Q4** ;
  - les **arguments de la Q2** ;
  - le « pourquoi » et le « changement » des **amendements**.
- Tout passe par `valider_reponse` / `valider_argument` (`app/ai/questions.py`).
  Une réponse rejetée produit « rien ». La règle de fond : **le modèle reformule,
  il n'ajoute rien**. Concrètement :
  - les chiffres doivent figurer dans la source ;
  - pas de glose ni de développement de sigle absents de la source ;
  - le déposant n'est pas requalifié ;
  - un argument de Q2 doit être ancré lexicalement dans ce qui a été prononcé.
- La **Q3** (le résultat) est composée de façon déterministe. Dans la Q2, le sens
  pour/contre vient du **scrutin**, jamais du modèle.
- La Q4 a trois sources possibles, par ordre de préférence :
  1. le texte adopté, à l'indicatif ;
  2. le dispositif déposé, au conditionnel ;
  3. l'exposé des motifs, préfixé « Selon l'auteur du texte, ».
- Après l'ajout d'un garde-fou, lance `python -m app.ingestion.revalider` : les
  réponses validées sont réutilisées entre runs, et sans ce passage les
  anciennes resteraient en base.
- Si le serveur LLM est injoignable, **demande avant de changer de modèle**. Ne
  bascule pas sur un modèle local.

## Dépôt, stack, commandes

```
/          Frontend Expo / React Native / TypeScript strict (src/)
backend/   API FastAPI + ingestion open data (Python 3.12, SQLAlchemy async, PostgreSQL)
```

- Frontend : Expo SDK 54, React Native 0.81, React 19, `@react-navigation`
  (native-stack + bottom-tabs) et `react-native-svg`. L'alias `@/*` → `src/*`
  est résolu par TypeScript **et** par Metro.
- Backend : FastAPI, Pydantic, SQLAlchemy async. **Pas d'Alembic.**

```bash
# Frontend (racine)
npm start                  # Metro (QR code, Expo Go / dev client)
npm run ios                # expo run:ios : build dev client + simulateur
npm run start:clear        # Metro sans cache
npx tsc --noEmit           # vérification de types — à lancer avant de conclure
npx expo export            # bundle : attrape les erreurs d'import/résolution

# Backend (dans backend/, venv OBLIGATOIRE — sinon ModuleNotFoundError)
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload --host 0.0.0.0   # :8000/docs ; --host pour un iPhone physique
pytest                                        # tests forcés sur le seed (conftest)
python -m app.db.migrations                   # après un pull qui change db/models.py
```

Le frontend n'a **pas de suite de tests** : on le vérifie avec `tsc --noEmit` et
`expo export`. L'URL de l'API est dérivée de l'hôte Metro (`src/api/config.ts`),
surchargeable par `EXPO_PUBLIC_API_URL`. Le backend doit tourner pour le premier
chargement, puis le cache AsyncStorage prend le relais hors-ligne.

### Ingestion et rattrapages ciblés

Le run complet (`python -m app.ingestion.run`) couvre AN + Sénat + LLM et dure
des heures sur toute la législature. Il **committe par dossier** : on peut
l'interrompre sans risque. Options : `--limit N`, `--sans-senat`,
`--plafond-amendements-sans-scrutin N` (borne les ~9 000 amendements votés à
main levée dont on interroge le LLM ce run ; les suivants reprennent).

Les commandes ciblées ci-dessous évitent un run complet. Le README backend
détaille ce que chacune télécharge.

| Commande `python -m app.ingestion.…` | Fait | Réseau | LLM |
|---|---|---|---|
| `deputes` | référentiel députés + votes nominatifs | archives AN | – |
| `senat --limit 40` | sénateurs + scrutins du Sénat (+ reclasse leurs motions) | senat.fr | – |
| `reformater` | titre court + accroche | – | – |
| `revalider` | repasse les garde-fous, efface les réponses fautives | – | – |
| `divisions` | indice « votes les plus disputés » | – | – |
| `positions` | position des groupes depuis les décomptes + résumé + sens Q2 | – | – |
| `commissions` | amendements tranchés en commission saisie au fond | amendements + dossiers + AMO | – |
| `mises_au_point` | déclarations des députés après le vote (AN) | scrutins + AMO | – |
| `motions` | classe les motions (ne déclasse jamais) | – | – |
| `initiatives` / `etats` | qui porte le texte / où il en est | archive dossiers (10 Mo) | – |
| `sources` | rapports de commission + « documents du dossier » | idem + HEAD | – |
| `types_vote` | forme du scrutin + seuil, recompose la Q3 | archive scrutins | – |
| `lois` | loi finale + Q4 à l'indicatif (`--dry-run`, `--sans-llm`) | archive + PDF | oui |

## Architecture frontend

```
App.tsx                 Racine : ProfilProvider + RootNavigator (monté après polices + accueil + profil)
src/theme/              Source unique du visuel : colors, spacing, typography
src/types/index.ts      Contrat de données — miroir de backend/app/schemas/ (camelCase)
src/api/                Client HTTP (timeout), endpoints, cache offline (cache.ts)
src/hooks/              Un hook par ressource : chargement + cache + refresh (état `refreshing` distinct)
src/session/            ProfilContext — le seul provider applicatif (session + préférences)
src/storage/            Préférences du lecteur (≠ api/cache.ts, qui garde des données publiques)
src/constants/          glossaire.ts (source unique, §8), motions.ts, themes.ts, sorts.ts
src/utils/              format.ts (libellés, badgeDossier, voteDecisif), periodes.ts, validation.ts
src/components/         Composants réutilisables (barrel index.ts)
src/screens/            Un écran par fichier (barrel index.ts)
src/navigation/         MainTabs (Accueil · Recherche · Députés · Assistant · Profil) + RootNavigator
```

Les fiches (`DossierDetail`, `ScrutinDetail`, `DeputeDetail`, `Dossiers`,
`Glossaire*`, `Onboarding`, `Connexion`) vivent dans le **stack racine** : on les
atteint depuis plusieurs onglets et elles couvrent la tab bar.

| Écran | Hook → endpoint | À respecter |
|---|---|---|
| `HomeScreen` | `useAccueil` → `/accueil`, `useRecap` → `/recap` | Affichage **atomique** : une seule réponse, pas de remplissage progressif. Rangées vides masquées. Pas de défilement infini. La rangée « votes les plus disputés » vient de `app/domain/division.py`, de l'arithmétique sur les décomptes : chiffres affichés, motions de censure et votes de conduite de séance exclus. |
| `DossierDetailScreen` | `useDossier` → `/dossiers/{id}` | Ordre : frise + « Où en est le texte » → « En bref » → loi → initiative → questions → votes (vote décisif mis en avant) → amendements de commission → amendements → sous-amendements → **documents du dossier**. « En bref » (`EnBref`) ne rend que deux phrases du résumé neutre (gabarit, sans LLM) : `trajectoire` et `positions_groupes`, celle-ci titrée par le vote décisif. Les autres phrases répètent un bloc de la fiche. C'est le **seul** endroit de la fiche avec des liens vers des documents. |
| `ScrutinDetailScreen` | `useScrutin` → `/scrutins/{id}` | Résultat **en tête**. Vote sur le texte : groupes + `LigneFracture` + nominatif. Vote d'amendement : `QuestionsAmendementCard` et **pas** de vote par groupe. |
| `ExplorerScreen` | `useThemes` → `/themes` | Découverte uniquement : il **ouvre** `Dossiers`, il ne cherche jamais lui-même. |
| `DossiersScreen` | `useRecherche` → `/recherche`, `/deputes?q=` | Demande `LIMITE_MAX` (100). Le tri et les groupes viennent du seul `utils/periodes.ts`. |
| `Glossaire[Terme]Screen` | local + `useRecherche` | Un terme renvoie vers les dossiers où il apparaît. Un voisin sans fiche est atténué et non cliquable. |
| `DeputesScreen` / `DeputeDetailScreen` | `useDeputes`, `useDepute` → `/deputes…`, `/groupes` | Effectif réellement servi, jamais « 577 » en dur. Pas de taux de participation. |
| `Onboarding` / `Profile` / `Connexion` | `ProfilContext` → `/inscription`, `/connexion`, `/moi…` | Tout est facultatif, « Passer » partout. L'anneau du profil est une couverture de corpus, pas un score du lecteur. Pas de « mot de passe oublié ». |
| `AssistantScreen` | — | Placeholder. Hors périmètre V1 (§2.3). |

Points partagés à ne pas dupliquer :
- **Badge de dossier** : `badgeDossier` (`format.ts`) est partagé par la carte,
  la tuile, le hero et la fiche. Ordre : loi promulguée → « Promulguée » ; dernier
  vote = motion → « Motion adoptée/rejetée » ; sinon le statut.
- **Vote décisif** : `voteDecisif` est le miroir de `_vote_decisif` côté backend.
  C'est le vote sur l'ensemble le plus récent ; s'il n'y en a pas, on ne désigne
  rien.
- **Titre d'un vote** : `libelleScrutin(objet, typeMotion)`. Un objet non
  reconnu est restitué tel quel.
- **Glossaire** : `constants/glossaire.ts` alimente les écrans dédiés **et**
  l'aide en ligne (`DefinitionGlossaire`). La table `MOTIFS` est **ordonnée** :
  le cas particulier passe avant le général. Un terme hors liste n'a pas d'aide.
- **Frise et état du texte** : ils sont **servis par l'API**
  (`Dossier.trajectoire`, `Dossier.etat`). Ne les dérive pas côté app : les
  scrutins d'une chambre ne documentent pas l'autre.

## Architecture backend

```
app/main.py            App FastAPI + routers
app/api/routes/        dossiers.py (/dossiers, /scrutins, /recherche, /themes, /accueil, /recap),
                       deputes.py (/deputes, /groupes), comptes.py, health.py
app/schemas/           Pydantic — miroir de src/types (scrutin.py, depute.py, utilisateur.py)
app/repositories/      DossierRepository (LECTURE seule) : memory.py (seed) | postgres.py ;
                       UtilisateurRepository (protocole séparé) : utilisateurs.py
app/db/                models.py, session.py, migrations.py (DDL additives et idempotentes)
app/domain/            Règles pures : division.py, enums.py, recherche.py (search_index), sources.py
app/ai/                Résumé déterministe (faits, rag, gabarit, guardrails) + tâches LLM validées
                       (llm.py, questions.py, theme.py, publics.py)
app/ingestion/         run.py → sync.py (SyncJob) + un module par source (cf. README backend)
app/data/seed.py       Données FICTIVES (backend memory + tests) — ne jamais les présenter comme réelles
```

- **`REPOSITORY_BACKEND`** vaut `memory` (seed, valeur par défaut) ou `postgres`.
  En dev, `backend/.env` fixe `postgres`. Les tests forcent `memory`. Les comptes
  suivent ce réglage : en `memory`, un compte est perdu à l'arrêt.
- **Comptes**, les seules écritures de l'API :
  - minimisation : prénom, nom, e-mail, empreinte bcrypt ;
  - `Compte` n'expose **jamais** l'empreinte ;
  - e-mail inconnu et mot de passe faux renvoient le **même** 401 avec le même
    message ;
  - l'e-mail est stocké en minuscules ;
  - `JWT_SECRET` est obligatoire hors dev. En dev, le secret est éphémère, donc
    il faut se reconnecter après un redémarrage, et ce n'est pas un bug ;
  - les routes de lecture restent publiques, et un test le vérifie.
- **Regroupement d'un vote en dossier**, en cascade : `dossierRef` officiel →
  réconciliation par titre dans l'archive des dossiers législatifs (correspondance
  exacte, puis par signature ; législature courante puis précédente) → dossier
  reconstitué `TXT-…` (id dérivé de la signature du titre) → singleton
  (`estEvenementAutonome` : motion de censure, déclaration). Puis les **votes que
  les actes législatifs citent** (`voteRefs`) corrigent le résultat du titre
  (`rattacher_par_votes_officiels`) : un vote cité rejoint son dossier, les
  autres votes du même texte le suivent si leur date tombe dans la vie du
  dossier. Le Sénat suit la même logique : `senatChemin` publié par l'AN → lien
  inverse → titre → `SEN-{slug}` → singleton. Enfin, un dossier reconstitué
  (`TXT-…`, `SEN-…`) rejoint le dossier officiel qu'une **décision de séance**
  désigne : même chambre, même jour, titre concordant (`rattacher_par_decisions`).
- **Décisions sans scrutin public** (`app/ingestion/decisions.py`). Les actes de
  décision de l'archive (`…-DEBATS-DEC`) deviennent des votes sans décompte
  (`scrutinPublic=false`, `modalite`, `etape`, `conclusion` verbatim) quand
  aucun scrutin public ne les raconte. Les **amendements** votés à main levée
  viennent de l'archive des amendements, rangés dans le dossier où elle les
  range. Conclusion inconnue → rien ; scrutin public possible → rien (§2.5).
  Détail et règles de couverture : README backend.
- **Élus en exercice / élus partis.** Le référentiel servi (`depute`) est
  **taillé** à chaque run sur l'annuaire du jour (`retirer_hors_referentiel`).
  Les **noms** des votants viennent d'annuaires historiques (`AMO30`,
  `ODSEN_GENERAL.csv`) : un élu parti reste nommé sur ses votes, sans lien.
- **Statut d'un dossier** = sort du dernier vote **sur le texte** (jamais d'un
  amendement) ; des amendements votés après lui → `en_cours`. Un vote sans
  scrutin public **découvert** (antérieur à la synchronisation précédente ou
  au dernier vote connu) ne pose pas le badge « Nouveau vote » (§7.7).
- **Préservation entre runs.** Un run sans archive n'efface pas ce qui est en
  base : exposé, initiative, état, loi finale, réponses validées, enrichissement
  des amendements. Le résumé n'est préservé que s'il est `relu_par_humain`.
- **Champs dérivés** : `Dossier.sources` est recomposé à chaque écriture par
  `domain/sources.py`. **N'y ajoute rien à la main**, ce serait perdu au run
  suivant.
- **Nouvelle colonne** : ajoute aussi l'énoncé dans `app/db/migrations.py`, car
  `create_all` ne modifie jamais une table existante.

## Modèle de données

Le contrat est `src/types/index.ts` ⇄ `backend/app/schemas/`, en camelCase des
deux côtés. **Toute évolution se répercute des deux côtés.**

- **`Dossier`** est l'entité centrale (un texte). Il porte :
  - `resume`, avec `questions` et `publicConcerne` ;
  - `scrutins` (des `ScrutinResume`), `amendements` (avec `sousAmendements`) ;
  - `amendementsCommission` : le seul **décompte** (adoptés, rejetés) de la
    commission saisie **au fond** à l'AN, nommée. Ni les commissions pour avis
    (elles ne modifient pas le texte), ni le Sénat, ni un organe d'examen que
    les actes ne désignent pas (`app/ingestion/commission.py`) ;
  - `trajectoire`, `etat`, `initiative`, `texteAdopte` ;
  - `exposeMotifs` (parole de l'auteur) et `dispositif` (fait officiel, jamais
    affiché brut, source de la Q4) ;
  - `titreOfficiel` (toujours affiché), `titreClair`, `accroche?` (tirée de la Q1 :
    pas de Q1, pas d'accroche) ;
  - `statutMotion?`, `miseAJour?`, `estEvenementAutonome` (posé à l'ingestion,
    **jamais déduit de la forme de l'id**).
- **`Scrutin`** est la fiche vote complète, servie par `/scrutins/{id}`. Il porte :
  - `chambre`, `scrutinPublic`, `typeVote?`, `suffragesRequis?` (utile seulement
    pour une motion de censure), `typeMotion?` ;
  - sans scrutin public : `modalite` (`main_levee`, `article_49_3`,
    `article_151_7`), `etape?` et `conclusion?` (libellés de l'archive) ;
  - `positionsGroupes` avec leurs `Votant` ;
  - `misesAuPoint` (AN seulement) : ce qu'un député déclare après le vote
    (« a fait savoir qu'il avait voulu « voter contre » », dysfonctionnement).
    `phrase` est la formule de l'Assemblée mot pour mot. Un fait **à côté** du
    vote : aucune statistique n'en tient compte (art. 68 RAN), et l'app ne dit
    jamais ce que le résultat « aurait été » ;
  - pour un amendement : `questions?`, `dispositif?`, `exposeSommaire?`, `cible?`.
- **`DossierListItem`**, l'objet allégé du fil et de la recherche, porte
  `natureTexte`, `chambres`, `statutMotion`, et le résultat, le type de vote et
  de motion du **dernier vote sur le texte** — ou `modaliteDernierScrutin` s'il
  s'est fait sans scrutin public (jamais les voix d'un vote plus ancien). Sans
  ces champs, une carte trompe.
- **`Votant.deputeId`** n'est posé **que si l'élu siège encore**. C'est la seule
  clé qui rend un nom cliquable. On n'affiche jamais une référence machine
  `PA…` en guise de nom.
- **`Depute`** couvre **les deux chambres**. `chambre` est le discriminant, et les
  ids du Sénat sont préfixés `SEN-…`. `commission` n'existe qu'au Sénat ;
  `depuis` (début de mandat) qu'à l'Assemblée, parce que la source du Sénat n'a
  aucune date. `PortraitVote` n'a pas de participation, et pas de cohésion au
  Sénat.
- **`Dossier.etat`** : **aucun champ ne décrit une étape à venir**, et un test
  vérifie la liste des champs. N'en ajoute pas.
- **Compte** : `Preferences` (`themes`, `departement`, `alertes`), `Compte`,
  `SessionOuverte`. On ne stocke ni historique de lecture, ni téléphone, ni date
  de naissance.

## Pièges connus

- **Une motion inverse la lecture de son résultat.** « Adopté » sur une motion de
  rejet préalable veut dire que le **texte** est rejeté. Il faut donc toujours
  **nommer** la motion (badge, titre, pastille dans l'historique d'un élu) ;
  `constants/motions.ts` dit ce que le vote emporte. Dans `build_dossier`, **à
  date égale, un vote sur le texte passe devant une motion**.
- **La classification d'une motion se fait sur l'objet entier**, avant la
  troncature à 120 caractères : au Sénat, la nature de la motion n'arrive
  qu'après. `app.ingestion.motions` ne déclasse donc jamais.
- **`positionMajoritaire` de l'AN est faux sur 3 % des groupes** (contredit
  ses propres décomptes, « pour » sur un groupe sans voix). La position se
  **déduit des décomptes** (`position_par_decompte`), aux deux chambres. Une
  égalité n'a pas de position (`non_votant` côté données, « voix partagées à
  égalité » à l'écran, `egaliteDeVoix`) : jamais « n'a pas pris part ».
- **La Q2 s'ancre sur un vote de l'Assemblée** (`_vote_conclusif`) : ses
  arguments viennent des comptes rendus de l'AN, dont les groupes n'existent
  pas dans un scrutin du Sénat. Le recalage du sens vise d'abord le vote d'où
  viennent les arguments (`_ancre_du_desaccord`).
- **Motion de censure** : `contre` et `abstention` valent 0 **par construction**
  (art. 49). Pas de barre pour/contre, pas d'écart, pas d'indice de division : on
  compare à `suffragesRequis` (`phrase_motion_censure`).
- **Sénat** :
  - l'année dans l'URL d'un scrutin est celle du **début de session**
    (oct.→sept.) : passe par `session_pour` ;
  - la « législature » d'un scrutin du Sénat est une session. Pour une URL de
    l'AN, utilise `legislature_du_ref(dossierRef)` ;
  - deux amendements identiques ont plusieurs numéros : on n'en retient aucun ;
  - l'archive des amendements est celle de l'**Assemblée** : un vote du Sénat
    sur « l'amendement n° 1343 » n'est jamais enrichi par le n° 1343 de l'AN
    (vécu : un amendement du Gouvernement au Sénat recevait l'exposé d'un
    amendement LFI-NFP de l'Assemblée) ;
  - un texte que **seul le Sénat** a examiné (ni vote ni étape à l'Assemblée,
    `examine_par_assemblee`) a une Q1 qui parle des **sénateurs**
    (`_SYS_POURQUOI_SENAT`) — « les députés ont examiné ce texte » y serait
    faux ;
  - **toutes** les sessions qui recouvrent la législature sont lues
    (`sessions_de_la_legislature`), pas seule la session en cours ;
  - le JSON nominatif ne donne pas le groupe du votant : c'est la **page du
    scrutin** qui le dit (listes de noms par groupe, `_groupe_du_jour`), et
    non l'annuaire du jour — les sénateurs changent de groupe. En repli, une
    liste qui dépasserait le décompte officiel du groupe est masquée.
- **Titres cités** : retire **toutes** les mentions finales de procédure
  (`_RE_MENTION_FINALE`, répétable). Sinon le texte se dédouble en un `TXT-…`
  vide. Une parenthèse au milieu du titre reste.
- **Textes trop longs** : au-delà de `_MAX_DISPOSITIF` (10 000 caractères), un
  dispositif ou une loi n'est **pas stocké**. Un texte partiel ne doit jamais être
  présenté comme le tout.
- **URLs dérivées** (photo d'un député AN, rapport de commission) : vérifie-les
  par HEAD avant de les attacher. Sinon, `null`.
- **Loi finale** : une loi sans `texteLoiRef` n'est pas devinée. Une **initiative**
  se lit sur le dépôt initial, jamais sur un document de navette.
- **`colors.rejete` (#FF3040) veut dire « rejeté »**. Ce n'est pas une couleur
  d'accent. L'accent est `colors.brand` (pervenche), et les formulaires ont leurs
  propres tokens (`valide`, `invalide`, `champ*`).
- **Animation sur un onglet jamais démonté** : n'anime jamais une prop SVG, cela
  impose le driver JS et fige l'UI. Anime l'`opacity` d'une `View` avec
  `useNativeDriver: true` (`ProfilCiel`).

## Conventions de code

- **Tout en français** : identifiants, champs, libellés, commentaires. Reste
  cohérent avec l'existant (`titreClair`, `positionMajoritaire`).
- **Commentaires** : cite la section du MVP (`§2.5`, `§7.4`…) quand un choix en
  découle, et explique le *pourquoi*, surtout ce qu'une donnée **ne** dit **pas**.
- **Imports** : toujours via `@/…`, jamais `../../`. Exports groupés par les
  `index.ts` de `components/`, `screens/` et `hooks/`.
- **Style** : `StyleSheet.create` en bas de fichier. Aucune couleur, espacement
  ou taille de police en dur : tout passe par `@/theme`. Une nouvelle couleur se
  déclare dans `colors.ts`.
- **Accessibilité** : `accessibilityRole` / `accessibilityLabel` sur tout élément
  interactif ou badge ; `importantForAccessibility="no"` sur les emojis
  décoratifs.
- **Safe area** : chaque écran gère `useSafeAreaInsets`.
- **Icônes** : pas de librairie. `TabBarIcon` sert la tab bar, `IconLigne` /
  `ThemeIcone` servent Explorer et le Glossaire, et ailleurs on utilise des
  emojis. Une nouvelle icône se dessine dans l'un de ces fichiers (SVG
  monochrome, couleur fournie par l'appelant).
- **Pas d'affordance vers le vide** : sans cible, pas de chevron et rien de
  pressable. Une donnée absente masque le bloc.

## Backlog priorisé (§10 MVP)

- **« Signaler une erreur »** : `AiNotice` accepte `onSignaler`, mais aucun écran
  ne le lui passe.
- **Planifier la synchro** (plusieurs fois par jour), et Légifrance/PISTE pour le
  texte consolidé.
- **Amendements de commission non attribués** (~600) : leur `examenRef`
  désigne un organe que les actes du dossier ne saisissent pas (vécu :
  « simplification de la vie économique », commission spéciale L16 dans les
  actes, affaires économiques dans l'`examenRef`). Non comptés (§2.5).
- **Commission des députés AN** : `GroupResolver` ne garde que les organes `GP`.
  Il faudrait résoudre les mandats `COMPER`.
- **Dossiers `TXT-` restants** (11) : ni cités par les actes législatifs, ni
  désignés par une décision du même jour. Restent des coquilles de la source
  (une distance d'édition à 1 caractère, risque de faux appariement à mesurer)
  et des titres présents en L16 et L17 (piste : préférer la législature
  courante).
- **Questions des amendements votés à main levée** (~9 000, deux appels LLM
  chacun) : le code les génère comme pour un vote public, mais le run d'oct.
  2026 s'est fait sans serveur mistral. À faire tourner par tranches
  (`--plafond-amendements-sans-scrutin`) quand il répond. Leur contenu officiel
  (dispositif, exposé sommaire) s'affiche déjà.
- **Sénat** : comptes rendus (`cri.zip`) pour avoir une Q2 sur les textes
  sénatoriaux, amendements (Ameli), Monalisa (XML structuré) à la place du grattage
  PDF.
- **V1.1** : filtres de recherche, partage. **V2** : assistant à questions
  pré-cadrées. Restent hors V1 : notifications push, suivi de député,
  comparateur, assistant à champ libre, prédiction d'impact.
