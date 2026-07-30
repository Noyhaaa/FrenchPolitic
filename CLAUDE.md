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

Six écrans du cœur de valeur :
1. **Accueil façon Netflix** (`HomeScreen` → `useAccueil`, `GET /accueil`) :
   l'écran complet arrive en **une réponse** (affichage atomique, pas de
   remplissage progressif) — hero « à la une », rangées horizontales
   **Aujourd'hui** / **Hier** (masquées si vides, §2.5), rangée **« Les votes
   les plus disputés »** (`VoteDisputeTile`, `Accueil.votesDisputes`), carte
   **récap du dernier mois actif** (`useRecap`, `GET /recap`), puis **une rangée
   par thème**. La rangée des votes disputés est ordonnée par
   `app/domain/division.py` — **arithmétique pure sur les décomptes officiels**
   (écart de voix, abstention, fracture entre groupes, pondérés par l'ampleur),
   jamais un jugement sur la mesure (§4.3) : chaque carte affiche ses chiffres à
   côté du rang, et un sous-titre dit sur quoi porte le classement. Sont exclus
   les votes à main levée, ceux de moins de 50 votants et ceux de **conduite de
   séance** (suspension, prolongation au-delà de minuit, seconde délibération —
   très serrés mais ils ne décident de rien) ; 2 votes maximum par dossier. La
   **dispersion interne** des groupes est affichée mais **pas classante** :
   incalculable au Sénat (délégation), la pondérer classerait les deux chambres
   sur des critères différents. Pas de défilement infini : la recherche sert à aller au-delà.
   Les cartes et le hero affichent la **nature du texte** (« Projet de loi »…)
   en label, **servie par l'API** (`DossierListItem.natureTexte`, dérivée du
   titre officiel — rien d'affiché sinon, on ne déduit pas). Le **titre affiché**
   (`titreClair`) est le titre officiel **débarrassé de cette nature et de son
   connecteur** (« Proposition de loi visant à améliorer la sécurité des
   trains » → « Améliorer la sécurité des trains », `titre_court` dans
   `normalize.py`) : liste fermée de connecteurs, sinon titre intact (« Projet de
   loi **de finances** pour 2025 » n'est pas amputé). Sous le titre vient
   l'**accroche** — le **but du texte en une phrase, tirée de la Q1** dont
   l'amorce (« Les députés ont examiné ce texte pour… ») est retirée
   (`accroche_depuis_q1`) : rien n'est régénéré, la Q1 est déjà validée. Pas de
   Q1 → **pas d'accroche**, la ligne disparaît (§2.5).
2. **Fiche dossier** (`DossierDetailScreen` → `useDossier`) : en tête, la
   **frise « Trajectoire au Parlement »** (`TrajectoireNavette`, alimentée par
   `Dossier.trajectoire` **servie par l'API**) — les étapes officielles du
   dossier, **les deux chambres comprises** (1re lecture à l'Assemblée puis au
   Sénat, CMP, Conseil constitutionnel, promulgation), chacune avec sa chambre
   écrite en toutes lettres. Le statut n'est posé que si la source le
   documente ; frise masquée si aucune étape ne l'est (§2.5). Chaque étape dont
   le libellé officiel est du jargon (**12/12 de ceux présents en base**) s'ouvre
   sur sa **définition de procédure** (`constants/glossaire.ts`), affichée sous
   la frise — les pastilles s'enchaînent horizontalement et n'ont pas la place
   d'un paragraphe ; une seule ouverte à la fois. ⚠️ Elle n'est
   plus dérivée côté app des objets de vote (`phasesNavette` a été supprimé de
   `format.ts`) : les scrutins d'une chambre ne peuvent pas documenter l'autre.
   La frise **se clôt sur « Où en est le texte ? »** (`Dossier.etat` servi par
   l'API) : à elle seule elle ne raconte que le passé et laissait sans réponse
   la question suivante. Cinq états, chacun un fait des mêmes actes officiels —
   **« C'est la loi »** (sans autre précision : le numéro, la date et le
   *Journal officiel* vivent dans la carte « La loi » juste en dessous, et les
   répéter ici dirait deux fois la même chose à deux centimètres), « Résolution
   adoptée », « Texte retiré par son auteur », « Devant le Conseil
   constitutionnel », ou « En cours d'examen » suivi de la **dernière étape
   enregistrée**. ⚠️ **Jamais l'étape suivante** : le calendrier parlementaire
   est une décision politique, pas une donnée — l'annoncer serait une
   prédiction (§2.5). Ce que la source ne dit pas est dit explicitement
   (« Aucune étape postérieure n'est publiée »), pour que le silence se lise
   comme celui de l'archive et non de l'app. Le bloc porte glyphe **et** libellé
   (RGAA §8) et partage l'état « une seule définition ouverte » des pastilles ;
   seul « Résolution » y ouvre son aide, car c'est le seul mot qu'aucune
   pastille de la frise ne porte (la sienne dit « Lecture unique ») — on
   n'explique pas deux fois au même endroit. Une **loi promulguée** remonte
   aussi dans le **badge de tête** (« Promulguée » au lieu d'« Adopté », le
   résultat du dernier vote : exact, mais il laissait croire que le texte était
   encore en chemin). Mesuré : **254/328 dossiers** (96 promulgués · 126 en
   navette · 21 résolutions · 7 au Conseil constitutionnel · 4 retirés) ; les
   74 sans actes (`TXT-…`, `SEN-…`) gardent le bloc masqué.
   Puis, pour une loi promulguée seulement, la carte **« La loi »**
   (`LoiCard`) : « Loi n° 2025-379 du 28 avril 2025 » et son *Journal officiel*.
   ⚠️ **Aucun lien dans cette carte** : le **texte voté par le Parlement**
   (`Dossier.texteAdopte`, la « petite loi ») et le **texte en vigueur**
   (Légifrance, `etat.urlLegifrance`) sont deux documents distincts — ce que le
   Parlement a adopté, et ce qui s'applique aujourd'hui, une loi ayant pu être
   modifiée depuis — mais ils vivent tous deux dans « Les documents du dossier »
   en bas de fiche, avec le reste (cf. plus bas). La **référence écrite** reste
   ici, elle : c'est elle qui permet de retrouver la loi si un lien vieillit.
   Le **corps** de la loi n'est jamais affiché — droit codifié illisible, même
   doctrine que le dispositif.
   Sous le titre, la carte **« À l'origine du texte »** (`InitiativeLigne`,
   `Dossier.initiative` servie par l'API) — **qui porte le texte**, la première
   question qu'on se pose devant un vote : le **Gouvernement** (tout projet de
   loi, art. 39), le **parlementaire auteur** (sa **photo officielle** — celle
   du référentiel, jamais une URL dérivée ici —, repli sur les initiales, avec
   la pastille **et le libellé** de son groupe ; la carte ouvre sa fiche), ou le
   **Sénat**. Même
   gabarit dans les trois cas (§7.4) — médaillon, intitulé, précision : le
   médaillon d'une institution est l'`Avatar` réduit à son initiale, pour
   qu'aucune origine ne reçoive un traitement plus flatteur. ⚠️ **Pas** le
   liseré d'accent d'`ExposeMotifsCard` : là-bas il signale un contenu non
   neutre, ici c'est un fait — et un liseré teinté du groupe laisserait croire
   que la carte porte son opinion. Pas de `deputeId` → pas de chevron et carte
   non pressable : jamais d'affordance qui ne mène nulle part. Origine sans
   personne nommable → **carte masquée** plutôt qu'« un parlementaire », qui
   n'apprendrait rien (§2.5). Mesuré : **242/255 dossiers officiels**
   (49 Gouvernement · 124 parlementaires dont 110 nommés · 69 Sénat) ; les
   dossiers reconstitués et les motions n'en ont pas.
   Puis résumé du texte,
   et **trois sections distinctes** — les **votes sur le texte**, avec le
   **vote décisif mis en avant** (`VoteDecisifCard` + `voteDecisif` dans
   `format.ts`, miroir de `_vote_decisif` backend : le vote sur l'ensemble le
   plus récent, carte accentuée + phrase explicative factuelle — c'est lui qui
   scelle l'adoption/le rejet, pas les votes d'articles ni les motions ; sans
   vote sur l'ensemble, rien n'est désigné §2.5) suivi de la **liste compacte
   des autres votes** (titre = **type du vote en clair** via `libelleScrutin` :
   « Vote sur l'ensemble », « Motion de censure », « Article 2 »… + **chambre** +
   statut + micro-résultat ; objet non reconnu restitué tel quel, §2.5), les
   **Amendements** (ligne compacte via `AmendementRow` : numéro + sort + auteur,
   sans répéter la formule « l'amendement n° X de M. Y »), et les
   **Sous-amendements** (avec rappel de l'amendement parent). Chaque ligne ouvre
   la fiche vote. Un vote d'amendement n'apparaît **que** dans sa section (un
   sous-amendement que dans la sienne), et les listes longues sont repliées
   au-delà de 4 éléments (« Voir les N autres… »). La fiche se clôt sur
   **« Les documents du dossier »** (§7.5) — **tous** les documents officiels du
   texte, dans l'**ordre de sa vie** : dossier législatif → texte déposé →
   **rapports de commission** (un par lecture, chacun avec son numéro) → compte
   rendu de séance → texte voté → texte en vigueur. La liste est **dérivée** de
   ce que le dossier porte déjà (`app/domain/sources.py`, `documents_du_dossier`,
   idempotente) : rien n'y est écrit à la main, une URL n'y paraît qu'une fois
   (l'exposé et le dispositif sortent du même PDF), et un document absent laisse
   sa place vide (§2.5). ⚠️ C'est le **seul endroit de la fiche** où un document
   du dossier est lié : `ExposeMotifsCard`, `QuestionsCard` et `LoiCard` ne
   portent plus de `SourceLink` — la même URL deux ou trois fois sur une page
   n'ajoutait rien. Ce qui reste dans les cartes, c'est ce qu'un lien ne dit
   pas : la **provenance en toutes lettres** (« Selon l'auteur du texte »,
   « seuls les groupes qui se sont exprimés en séance », et pour la Q4 le **nom**
   du document dont elle sort — « D'après : Texte voté par le Parlement » —, car
   lequel des trois a servi change le sens de la phrase). Vérifié en base : les
   URLs qu'affichaient les cartes sont **toutes** dans la liste, zéro orpheline.
   Ce qui reste hors d'ici, c'est la source de chaque **vote** — elle vit sur sa
   propre fiche. Mesuré : de **1,17 à 4,12 liens** par dossier, et de **313 à
   36** dossiers réduits à une seule source.
3. **Fiche vote** (`ScrutinDetailScreen` → `useScrutin`, `GET /scrutins/{id}`) :
   titre = type du vote en clair — **cliquable quand c'est un terme de
   procédure** (« Motion de rejet préalable », « Vote sur l'ensemble »…), il
   déplie alors sa définition (`constants/glossaire.ts`, §8) ; la recherche se
   fait sur le **titre**, jamais sur l'objet officiel, dont les mots
   déclencheraient des définitions sans rapport avec le type de vote —,
   **objet officiel complet en dessous**, la
   **chambre** (`scrutin.chambre` via `libelleChambre`, jamais « Assemblée
   nationale » en dur), puis —
   **sur toutes les fiches, quel que soit le type de vote** — le **Résultat du
   vote EN TÊTE** (§2.2 : voir le résultat tout de suite ; verdict, décomptes
   pour/contre/abstention, barre combinée + échelle, décomptes officiels),
   clos par la **forme du scrutin** : « Scrutin public ordinaire · 42 votants »,
   **dépliable** sur sa définition (`termeTypeVote`, `constants/glossaire.ts`).
   C'est la réponse à « 42 voix contre 0, pourquoi seulement 42 ? » — un scrutin
   **ordinaire** se tient en séance parmi les députés alors présents (médiane
   **132** votants), un scrutin **solennel** est annoncé à l'avance (médiane
   **528**). ⚠️ **Jamais un taux de participation** : la source ne recense que
   les votants d'un scrutin public, un ratio se lirait comme un score
   d'absentéisme qu'elle ne soutient pas (§7.4, même règle que la fiche député).
   Forme absente (Sénat, dont la page ne la nomme pas) → « 42 votants » seul.
   ⚠️ **Une motion de censure ne se raconte PAS pour/contre** : l'article 49 de
   la Constitution ne fait recenser que les voix **favorables**, si bien que
   `contre` et `abstention` y valent 0 **par construction** (vérifié : les
   23 motions de la législature). La fiche montre alors « 267 voix pour ·
   289 requises », une barre mesurée **contre le seuil**, ni colonne « Contre »
   ni écart — c'est ce 0-là qui trompait. Le glossaire le disait déjà
   (`motion-de-censure` : « Seules les voix POUR sont comptées »), les chiffres
   le contredisaient deux lignes plus bas.
   Ensuite, deux visages selon le vote :
   — **Vote sur le texte** : section **Vote par groupe**
   avec la **ligne de fracture** (`LigneFracture` : quels groupes ont
   majoritairement voté pour / contre / se sont abstenus — factuel, sourcé par
   le scrutin, jamais un jugement §7.4, masquée si unanimité), la ventilation
   détaillée par groupe et les **noms des votants** dépliables groupe par
   groupe quand le nominatif est disponible (§5.2). Chaque nom **ouvre la fiche
   du député** (souligné, jamais la couleur seule §8/RGAA) — mais **seulement**
   si le backend a joint son `deputeId`, c'est-à-dire s'il siège encore : un
   ancien député garde son nom sans lien, jamais de cul-de-sac vers un 404. Le
   décompte affiché en tête de chaque position est le **chiffre officiel du
   groupe**, pas la longueur de la liste : un votant que la source ne sait pas
   nommer en est absent (on n'affiche jamais une référence machine `PA…` en
   guise de nom, §2.5). Sur un vote du **Sénat**, une mention factuelle suit la
   ventilation : les bulletins d'un scrutin public ordinaire y sont déposés par
   un délégué de groupe pour tous ses membres, les noms reflètent donc la
   position du groupe — sans elle, la liste dirait autre chose que ce qu'elle
   dit (§7.4).
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
4. **Explorer** (`ExplorerScreen` → `useRecherche` + `useThemes`, avec debounce ;
   remplace l'ancien `SearchScreen`, supprimé) : tant que rien n'est cherché,
   l'écran ne montre plus un vide en attente d'un mot — quatre **portes
   d'entrée** (Dossiers, Élus, Assistant, Glossaire), puis les **catégories**,
   la plus fournie en vedette et les suivantes en rangées, écrêtées à 5 avec un
   « Voir les N autres » qui **déplie vraiment** la liste. Le libellé de la
   vedette dit ce que la donnée dit — « la plus fournie en dossiers », un
   décompte de `useThemes` —, pas « la plus suivie », qui demanderait une
   analytique qu'on n'a pas (§2.5). ⚠️ **Explorer n'interroge pas la
   recherche** : la tuile *Dossiers*, la validation du champ et le tap sur une
   catégorie **ouvrent l'écran `Dossiers`**. Explorer fait découvrir, `Dossiers`
   montre ce qu'on a trouvé — les afficher au même endroit ferait disparaître la
   découverte au premier mot tapé, et le retour arrière n'aurait plus de sens.
4ter. **Dossiers** (`DossiersScreen` → `useRecherche`, route
   `{ query, theme? }`) : les **résultats**, délibérément dissemblables
   d'Explorer — barre d'outils `surface` portant la requête, onglets soulignés
   *Textes* / *Députés* avec leur décompte, puis une **chronologie** de lignes
   denses (`DossierChronoRow`, pas de cartes : `DossierCard` reste au fil
   d'accueil). Les deux vides = parcourir tous les textes ; `theme` seul =
   parcourir une catégorie. Le groupage (« Cette semaine », « Plus tôt en
   juillet ») vient de `utils/periodes.ts`, **seule source du tri** : libellés de
   groupe et ordre des lignes sortent du même calcul, ils ne peuvent pas se
   contredire. Une ligne n'affiche sa **barre pour/contre** que si
   `resultatDernierScrutin` est présent ; sinon la mention qui l'explique la
   remplace — « Pas encore mis aux voix » si `nombreScrutins === 0`, sinon
   « Vote à main levée — pas de nominatif » (§5.2, §2.5). Cet écran demande
   `LIMITE_MAX` (100) à l'API là où le défaut est 20 : il annonce des catégories
   entières (« Justice · 51 dossiers » côté Explorer) et n'en rendrait sinon que
   20, se contredisant à l'écran. Quand le plafond est atteint, le titre dit
   « Les 100 plus récents » au lieu d'un décompte qui se lirait comme un total.
   Les *députés* viennent de `GET /deputes?q=` (plafonné à 5), onglet vide masqué.
   La requête est **multi-termes** : tous les mots sont exigés mais pas
   forcément côte à côte ni dans le titre, car l'index de recherche
   (`app/domain/recherche.py`, source unique de `search_index`) couvre aussi les
   réponses **Q1/Q4** et les **publics concernés** — c'est là qu'est le
   vocabulaire du lecteur (« logement », « hôpital »), pas dans les titres
   officiels. Les résultats sont **classés par pertinence** (titre > accroche et
   thème > réponses citoyennes ; à égalité, le plus récent), et un **thème seul**
   parcourt le thème. L'exposé des motifs est hors index (trop de bruit). Le
   filtre de thème ne s'applique pas aux personnes : les députés disparaissent
   quand il est actif.
4bis. **Glossaire** (`GlossaireScreen` l'index, `GlossaireTermeScreen` la fiche —
   au niveau du stack racine, atteints depuis Explorer **et** depuis l'aide en
   ligne). L'index : un **mot du jour** déterministe (index sur le numéro de
   jour — même mot pour tous, changement à minuit, aucun stockage), des chips de
   famille (Procédure · Institutions · Budget · Vote), puis les termes groupés
   par lettre avec leur définition courte, pour comprendre **sans ouvrir la
   fiche**. La fiche : la définition en une phrase, le déroulé « Concrètement »
   (`etapes`), les faux amis (« À ne pas confondre » — un voisin sans fiche
   reste affiché mais **atténué et non cliquable**, il ne doit pas promettre un
   lien qui n'existe pas), et surtout **les dossiers où le mot apparaît**
   (`useRecherche` sur `requete ?? libelle`) : une définition ne doit pas être un
   cul-de-sac, on repart lire un texte. Bloc sans contenu → masqué (§2.5).
5. **Annuaire des parlementaires** (`DeputesScreen` → `useDeputes`,
   `GET /deputes`) : recherche par nom (debounce), **chips de chambre**
   (Les deux / Assemblée nationale / Sénat) **puis** chips de groupe
   (`GET /groupes`, pastille de couleur **+ libellé**) — les groupes proposés
   suivent la chambre choisie, et changer de chambre invalide un filtre de
   groupe devenu sans objet (§2.5). Une ligne par parlementaire (`DeputeRow` :
   `Avatar` — **photo officielle**, repli sur les initiales —, nom, groupe,
   circonscription). L'effectif affiché est celui réellement servi, jamais
   « 577 » ni « 925 » en dur.
6. **Fiche parlementaire** (`DeputeDetailScreen` → `useDepute`, `GET /deputes/{id}`) :
   identité (groupe, circonscription, **commission**, début de mandat — chaque
   champ masqué s'il n'est pas documenté, et les deux chambres ne documentent pas
   les mêmes : la **commission** n'existe qu'au Sénat, le **début de mandat** qu'à
   l'Assemblée), puis le **portrait de vote** sur 12 mois glissants
   (`PortraitVoteCard` : votes exprimés, part **avec son groupe**, ventilation
   pour/abstention/contre avec légende) et l'**historique de vote**
   (`VoteHistoryFil` : fil groupé par mois, rail + nœud coloré par position,
   pastille de sens **écrite**, tag de nature et date, titre officiel), filtrable
   Tous / Dossiers / Amendements / Sous-amend. et **paginé** (« Charger les votes
   plus anciens », `GET /deputes/{id}/votes`). Chaque entrée ouvre le dossier
   concerné. ⚠️ **Aucun taux de participation n'est affiché** : l'open data ne
   recense que les votants physiques d'un scrutin public (268 en moyenne sur
   577), si bien qu'un ratio de présence se lirait comme un score d'absentéisme
   que la source ne soutient pas (§7.4). « Contre son groupe » (pastille ambre)
   est en revanche un **fait déduit** du même scrutin, jamais un jugement —
   mais **jamais au Sénat** : la délégation de vote par groupe y rend le fait
   indéfendable, `contreSonGroupe` et `cohesionGroupe` y sont toujours absents
   et l'app masque alors ces indications (mécanique §2.5 déjà en place).

L'URL de l'API est dérivée de l'hôte Metro en dev (`src/api/config.ts`),
surchargeable via `EXPO_PUBLIC_API_URL`. **Le backend doit tourner** pour un
premier chargement ; ensuite le cache prend le relais hors-ligne. (L'ancien mock
`src/data/mockScrutins.ts` a été supprimé — la référence de données fictives est
désormais le seed backend `backend/app/data/seed.py`.)

Plus deux écrans « à venir » (`AssistantScreen`, `ProfileScreen`) présents dans la
tab bar mais hors périmètre V1 (§2.3 / §2.4).

**Backend** — API FastAPI servant les endpoints du cœur (`/accueil` — écran
d'accueil complet en une réponse —, `/dossiers`, `/dossiers/{id}`,
`/scrutins/{id}`, `/recherche`, `/recap` — activité du dernier mois actif)
et ceux des **parlementaires** (`/deputes?chambre=`, `/deputes/{id}`,
`/deputes/{id}/votes` — historique paginé —, `/groupes?chambre=`).
Le détail d'un dossier reste
**léger** (liste de `ScrutinResume`) ; le détail complet d'un vote — groupes et
**vote nominatif** (noms des députés, résolus via l'annuaire acteurs de l'archive
AMO, chacun accompagné de son `deputeId` s'il siège encore — c'est le lien du
vote vers la fiche du député) — vit dans la table `scrutin` et est servi à la
demande. Deux backends de
données commutables via
`REPOSITORY_BACKEND` : `memory` (données seed, défaut) ou `postgres` (données
ingérées). En dev, `backend/.env` fixe `REPOSITORY_BACKEND=postgres` + `DATABASE_URL`
pour que l'API serve la base ; **les tests forcent `memory`** (`tests/conftest.py`)
et restent donc sur le seed. **Phase 1 faite** : ingestion réelle de l'open data AN
(17e législature) — scrutins publics + groupes (archive AMO) — parsée, contrôlée,
**regroupée par dossier** et upsertée dans PostgreSQL (SQLAlchemy
async), via `python -m app.ingestion.run` (**commit par dossier** + ligne de
progression `[i/total]` — un run interrompu ne perd que le dossier en cours ;
exposé des motifs et thème sont mis en cache par dossier pour ne pas refaire
un travail déjà acquis à chaque run, cf. `backend/README.md`). Regroupement en cascade : `dossierRef`
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
légitimes dans le fil, marqués `estEvenementAutonome`, cf. plus bas). ⚠️ Le
titre cité est débarrassé de **toutes** ses mentions finales de procédure
(`_RE_MENTION_FINALE`, répétable) : la source en **enchaîne** parfois deux
(« …le droit à l'aide à mourir **(seconde délibération) (deuxième lecture)** »),
et n'en retirer qu'une laissait « (seconde délibération) » dans le titre, dont
la signature ne correspondait plus au titre officiel — le texte se **dédoublait**
alors en un `TXT-…` vide à côté de son vrai dossier (vécu sur l'aide à mourir, le
PLF 2026, le PLFSS 2025 et 2026, Mayotte, le narcotrafic : mesuré, **22 dossiers
sur 54** rejoignent leur dossier officiel une fois la mention retirée). Une
parenthèse **au milieu** du titre est en revanche conservée : elle fait partie de
ce que la source désigne. La réconciliation couvre la législature **courante et
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
textes/dossiers, jamais un amendement isolé — ni un vote de **conduite de séance**
(demande de suspension, de seconde délibération) : quand un tel vote deviendrait un
dossier à lui seul, il est **écarté du fil** (`est_vote_de_conduite_de_seance`, la
même liste fermée que la rangée « votes les plus disputés » — une seule référence
pour les deux). Le même vote formulé pendant l'examen d'un texte reste, lui, un vote
de ce dossier, à sa place dans sa liste. Les votes d'amendement sont classés à
l'ingestion (`est_amendement` / `est_sous_amendement` sur l'objet officiel, avec
extraction du numéro et de l'auteur quand ils sont sans ambiguïté) et chaque
sous-amendement est **rattaché à son amendement parent** (« … à l'amendement
n° X ») ; le scrutin du parent embarque ses sous-amendements pour la fiche vote.
La fusion inter-runs pose le badge « mis à jour » quand un nouveau scrutin
(texte, amendement ou sous-amendement) rejoint un dossier connu.
Chaque scrutin porte enfin sa **forme** (`Scrutin.typeVote`, table fermée
`SPO`/`SPS`/`MOC` → `ordinaire` / `solennel` / `motion_censure` ; code inconnu →
rien, §2.5) et ses **suffrages requis** (`nbrSuffragesRequis`) — deux champs que
l'archive publiait depuis toujours et que l'ingestion ne lisait pas. Ils
répondent à « pourquoi seulement 42 votants ? » (médiane **132** en scrutin
ordinaire contre **528** en solennel) et corrigent surtout la **motion de
censure** : l'article 49 n'y recense que les voix favorables, donc la formule
générale « camp gagnant en premier » écrivait « **rejeté par 0 voix contre
267** » sur les 23 motions de la base — l'inverse du fait. `phrase_motion_censure`
(partagée par la Q3 et le résumé) dit désormais « recueilli 267 voix sur les
289 requises », `division()` **écarte** les motions du classement des votes
disputés (l'écart entre deux camps n'a pas de sens quand un seul est compté), et
le garde-fou des chiffres admet le seuil parmi les décomptes officiels. Le
`suffragesRequis` n'est **affiché que sur une motion** : ailleurs il vaut
exactement `exprimés // 2 + 1` (mesuré : 100 % des 8 411 autres scrutins).
Rattrapage : `python -m app.ingestion.types_vote`. Les **sources
du dossier** sont de niveau dossier uniquement — la source de chaque vote reste
sur son scrutin, servie par sa fiche vote — mais elles les rassemblent **toutes**
(§7.5) : `Dossier.sources` est une liste **dérivée**, recomposée à chaque
écriture par `app/domain/sources.py` depuis les documents que le dossier porte
déjà (page du dossier, texte déposé, `rapportsCommission`, compte rendu de la Q2,
texte voté, Légifrance). ⚠️ Ne rien y ajouter à la main : ce serait perdu au run
suivant. Le seul document qu'il a fallu **ingérer** pour ça est le **rapport de
commission** (`app/ingestion/rapports.py`) — il était dans l'archive des dossiers
téléchargée à chaque run, sous la famille `RAPINIT` (« rapport sur une
initiative », à distinguer des `RAPAUT`/`RAPTACOM`). Son URL publique contient le
slug de la commission, que **rien** dans l'archive ne donne (et 4 des 12 organes
les plus fréquents ne sont même pas des commissions : `due`, `ots`…) ; on passe
donc par le **résolveur du site**, `/dyn/docs/{uid}`, qui redirige vers la page
canonique et répond 404 sur un uid inconnu — dérivation depuis l'`uid` comme
partout, **vérifiée par HEAD** avant d'être attachée (doctrine
`attacher_portraits`). Mesuré : 287 rapports sur 205 dossiers, **0 non résolu**.
Le compte rendu de séance est typé `debats` (pas `texte`) : son icône le
distingue dans la liste. Le
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
fondu dans le résumé neutre. Le **même PDF** livre aussi le **dispositif** (les
articles du texte : `decouper_dispositif`, `Dossier.dispositif`) — lui est un
**fait officiel**, jamais affiché brut (droit codifié illisible) mais servant de
**source vérifiable** à la Q4. Un dispositif au-delà de `_MAX_DISPOSITIF`
(10 000 car. : budget, PLFSS) n'est **pas stocké du tout** — le modèle ne doit
jamais voir un texte partiel qu'il présenterait comme le tout (§2.5 ; à 15 700
car. mistral-small part en rapport de 3 000 car., rejeté par les garde-fous).
Le **même document de dépôt** livre enfin l'**initiative** — qui porte le texte
(`app/ingestion/initiative.py`, `Dossier.initiative`) : le champ `auteurs` de
l'archive donne soit un `acteurRef` (résolu en nom + groupe + `deputeId` par
l'annuaire AMO, exactement comme un votant nominatif), soit un `organeRef`.
Trois origines, aucune autre : **Gouvernement** dès que le texte est un *projet*
de loi (art. 39 — on ne descend **jamais** au ministre déposant, dont la qualité
n'est documentée dans aucune de nos sources et que 7 cas sur 48 seulement
permettraient de nommer) ; **parlementaire** quand la source désigne **un seul**
auteur de `qualite="auteur"` (plusieurs → l'origine reste, le nom disparaît :
même règle que `auteur_amendement`, §2.5 ; les `qualite="rapporteur"` de la même
liste ne sont jamais des auteurs) ; **Sénat** quand l'auteur est l'organe
`PO838901` **et** que le dépôt est classé `INITNAV` — les deux indices sont
exigés. L'initiative est lue sur le **dépôt initial** (plus petit numéro), jamais
sur un document de navette : un texte renvoyé par le Sénat après une 1re lecture
à l'Assemblée y est signé du Sénat, s'y rabattre ferait passer un texte né à
l'Assemblée pour un texte sénatorial. Mesuré : **242/255 dossiers officiels**
(49 · 124 · 69), zéro contradiction avec la nature écrite dans le titre.
Préservée entre runs comme l'exposé (un run sans archive ne l'efface pas), et
rattrapable seule par `python -m app.ingestion.initiatives`.
Pas besoin de Légifrance pour ça (option a ; la
neutralisation par LLM — option b — viendra avec un LLM assez fiable). **LLM local
(Ollama, `qwen3:14b`) branché sur trois tâches vérifiables** : (1) la
**classification de thème** (`app/ai/theme.py`) — les dossiers « Autre » de
l'heuristique reçoivent un thème choisi dans la **liste fermée**, sortie
hors-liste/verbeuse rejetée (repli) ; (1bis) les **publics concernés**
(`app/ai/publics.py`, `resume.public_concerne` → section « Qui est concerné ? ») —
même doctrine : liste fermée de 19 publics (miroir `publicEmoji` côté front),
validation exact-match, cap 3, rien de valide → section masquée ; (2) les
**4 questions citoyennes**
(`app/ai/questions.py`, servies dans `resume.questions`, affichées par
`QuestionsCard` en tête de fiche dossier — dont le **titre de la Q2 suit ce
qu'elle montre** : « Quel était le principal désaccord ? » seulement si les
groupes affichés ont plusieurs sens de vote, sinon « Ce que les groupes ont
dit », et jamais « unanimité », que cette liste ne prouve pas ; une mention y
rappelle que **seuls les groupes qui se sont exprimés en séance** y figurent —
mesuré, ils sont en moyenne 6 de moins que les groupes ayant voté, et la carte se
lisait sinon comme le panorama de l'hémicycle, §7.4) :
« Pourquoi ont-ils débattu ? » (Q1,
depuis l'exposé) et « Qu'est-ce que ça change ? » (Q4, au conditionnel) sont
passées à des **contrôles déterministes** (`valider_reponse` : chiffres présents
dans la source, nature du texte non inversée, lexique, caractères hors français,
attribution, **glose entre parenthèses** absente de la source, **déposant non
requalifié**) — rejet → « information non disponible ». Les deux derniers
garde-fous appliquent la même règle que les chiffres — *le modèle reformule, il
n'ajoute rien* : un sigle ne se développe pas tout seul (cas réel : « l'Anses
(Agence nationale de sécurité du médicament…) », développement absent de la
source et qui est celui de l'**ANSM**), et un amendement « du Gouvernement »
n'est pas déposé par « le député » (`deposant()` dans `normalize.py` lit le
déposant dans l'objet officiel ; sur un vote d'amendement la **nature du texte
est ignorée** — un député amende couramment un projet de loi —, et deux indices
contradictoires donnent `None`, donc aucun contrôle §2.5). Contrôle
**asymétrique**, appliqué aux seules réponses **attribuées** : la Q1 garde son
amorce « Les députés ont examiné ce texte… ». Les réponses validées étant
réutilisées entre runs, tout nouveau garde-fou s'applique au passé via
`python -m app.ingestion.revalider` (175 réponses fautives effacées à
l'introduction de ces deux-là). **Q4 a trois sources, dans
cet ordre** — chacune plus proche de ce qui s'applique réellement que la
suivante : (1) le **texte définitivement voté** (`Dossier.texteAdopte`, la
« petite loi ») — fait, *sans* attribution et à l'**indicatif** (« La loi
interdit… »), car le texte s'applique ; (2) le **dispositif du texte déposé**
(fait aussi, mais d'une version que la navette a modifiée, d'où le
**conditionnel**) ; (3) l'**exposé** (parole du déposant — réponse
obligatoirement préfixée « Selon l'auteur du texte »). C'est le prolongement de
la règle « le fait officiel prime sur la parole du déposant » : **la loi votée
prime sur le texte déposé**. Une réponse déjà en base **remonte** l'échelle dès
qu'une source plus haute apparaît (`peut_mieux_faire` compare la
`changementSource` stockée à la meilleure disponible). Sans cette échelle, la
fiche d'une loi en vigueur affichait le pitch de son auteur au conditionnel sur
une *proposition* — mesuré, 83 des 96 lois promulguées. Quand la source est un
texte officiel (loi votée, dispositif de texte
ou d'amendement), un mot du lexique évaluatif est admis **s'il figure tel quel
dans la source** (`lexique_de_la_source_admis`) : on interdit au modèle
d'**ajouter** un jugement, pas de reprendre les mots de la loi (cas réel :
« contenus dangereux », écrit dans l'article unique d'une résolution) ; le **résultat** (Q3) est
composé **déterministiquement** depuis le vote décisif ; le **désaccord** (Q2)
vient des **comptes rendus des débats** (archive « SyceronBrut »,
`app/ingestion/debats.py`), par **trois viviers de prises de position** dans cet
ordre : la section **« Explications de vote »** (chaque groupe explique lui-même
sa position), sinon la **discussion générale**, sinon seulement les débats **sans
section dédiée** — motion de rejet préalable et paroles placées directement sous
le titre de discussion (motion de censure, déclaration art. 50-1). Les morceaux
consécutifs d'un même orateur sont **recollés** et la **présidence de séance est
écartée** (elle est députée, donc résoluble en groupe : ses annonces d'ordre du
jour ne sont pas une position, §7.4). Le débat est relié au **vote conclusif** du
dossier (`_vote_conclusif` : ensemble > article unique > texte cité directement >
vote procédural > motion ; **jamais** un vote d'article numéroté) par le **numéro
de texte** cité au CR — joint aux numéros de tous les documents du dossier,
dédoublonnés par **(législature, numéro)** car la série redémarre à chaque
législature, et robuste à la navette comme au vote solennel à J+n —, sinon par
**date de séance + recoupement du titre** ; un candidat unique le jour J ne
suffit **jamais** sans recoupement (ambiguïtés écartées, §2.5), mais un même
texte rouvert plusieurs fois le même jour (reprise de séance) est **fusionné**
avant l'index plutôt que traité comme deux candidats ambigus. Chaque explication
est ensuite **paraphrasée en une phrase, validée et attribuée à
son groupe** (§7.4) — le **sens pour/contre vient du scrutin**, jamais du LLM, et
jamais de synthèse éditoriale (« qui a raison ») ; l'**objet du vote d'ancrage**
accompagne les positions (`desaccordObjet`), sans quoi « pour » sur une motion de
rejet se lirait comme « pour le texte ». La validation d'un argument
(`valider_argument`, règle unique partagée par la génération et la revalidation)
ajoute aux contrôles communs un **ancrage lexical** : une part minimale des mots
de contenu de la paraphrase doit se retrouver dans la phrase réellement
prononcée. Même règle que les chiffres — *le modèle reformule, il n'ajoute rien* —
mais c'est la seule qui attrape une phrase **plausible et fabriquée** : mesuré en
base avant garde-fou, « le texte ne répond pas aux attentes des Français en
matière de sécurité et d'immigration » était servi tel quel sur trois dossiers
sans rapport (dont un texte sur les honoraires d'expert-comptable), attribué à un
groupe qui avait voté **pour** — aucun contrôle de forme ne pouvait le voir. Pour
que ce garde-fou (et les suivants) s'applique au passé, l'**extrait de compte
rendu** qui a produit chaque argument est conservé hors payload
(`dossier.desaccord_sources`) : la Q2 se revalide donc hors ligne comme la
Q1/Q4 le font depuis l'exposé. Un argument sans source stockée est
**invérifiable**, donc effacé par `revalider` (1 476 arguments l'ont été à
l'introduction de l'ancrage). Le seuil est volontairement **permissif** au départ,
le resserrer ne coûtant plus aucun appel au modèle. ⚠️ On **ne génère toujours
PAS** le
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
`positionsGroupes` (`LigneFracture`).

Les **députés** (§5.2) ont leur propre référentiel (table `depute`, construite
depuis l'archive AMO : nom, groupe du mandat GP en cours, circonscription, début
de mandat, plus la **photo officielle** — seule URL *dérivée* de l'`acteurRef`,
donc attachée uniquement après vérification HEAD, sinon `null` : 576/577) et leurs **votes nominatifs** (table `vote_depute`, une ligne par
député × scrutin — 577 députés et ~1,27 M de votes sur la base de dev). Ces
lignes portent le fait déduit **« contre son groupe »** (position ≠
`positionMajoritaire` du groupe sur le MÊME scrutin, calculé pour les seules
positions exprimées, `null` si le groupe n'a pas de position majoritaire
exploitable). Alimentés par le run normal **et** par une commande autonome
`python -m app.ingestion.deputes` (AMO + archive scrutins seulement, ni LLM ni
dossiers : quelques minutes au lieu d'un run complet). Détails dans
`backend/README.md`.

**Le Sénat** (`app/ingestion/senat.py`, `senateurs.py`) — **Phase 1bis faite** :
les scrutins publics du Sénat sont ingérés et **rejoignent le dossier où vivent
déjà les votes de l'Assemblée**, si bien qu'un texte en navette ne se dédouble
pas dans le fil. Le Sénat ne publie pas d'archive groupée : on lit, par scrutin,
sa page HTML (objet, date de séance, sort, résultat, **analyse par groupe**, lien
vers le dossier) et son JSON nominatif (une ligne par matricule, codes
`p`/`c`/`a`/`n`), plus l'annuaire `api-senat/senateurs.json` (avec la **photo
officielle donnée par la source**, contrairement à l'AN où l'URL est dérivée).
⚠️ L'année des URLs est celle du **début de session** (oct.→sept.) : le scrutin
n° 340 de la session « 2025 » date du 21 juillet **2026** (`session_pour`).
Rattachement en cascade, miroir de celle de l'AN : (1) `titreDossier.senatChemin`
des `dossierParlementaire` de l'archive AN — **l'Assemblée publie elle-même
l'URL du dossier Sénat**, 873 dossiers appariés sans une requête ; (2) le lien
inverse (la page dossier du Sénat cite l'URL AN, résolue via `titreChemin`, casse
repliée) ; (3) la réconciliation **par titre** déjà en place — les objets de vote
du Sénat sont structurellement identiques à ceux de l'AN au préfixe « sur » près,
qu'on retire à l'entrée pour que tout l'aval s'applique tel quel ; (4) sinon un
**dossier d'origine sénatoriale** `SEN-{slug}` (le slug du Sénat est stable — pas
de hachage, contrairement aux `TXT-…`) ; (5) sinon un singleton. Mesuré : 12/12
des derniers scrutins rattachés à un dossier AN. Cas nouveau, absent de l'AN :
les **amendements identiques** portent plusieurs numéros → on n'en retient
**aucun** (§2.5). ⚠️ **Jamais de « contre son groupe » ni de cohésion au
Sénat** : les bulletins d'un scrutin public ordinaire y sont déposés par un
délégué pour tout le groupe, et la source ne distingue pas ces scrutins de ceux à
la tribune — le fait serait un artefact de procédure présenté comme un fait
politique (§7.4). Les sénateurs vivent dans les **mêmes tables** que les députés
(`depute`, `vote_depute`, `groupe`), discriminés par `chambre`, ids préfixés
`SEN-…`. Commande autonome `python -m app.ingestion.senat` (~10 s pour
40 scrutins), ou intégrée au run complet (`--sans-senat` pour s'en passer).
L'annuaire livre aussi les `organismes` de chaque sénateur, d'où la **commission
permanente** (`Depute.commission`, 346/348) : les sept permanentes portent un
`ordre` 7001-7007, la commission des affaires européennes — à laquelle 41
sénateurs appartiennent **en plus** de la leur — ouvre une autre série (8001), si
bien que retenir le plus petit `ordre` donne la permanente sans lister de libellés
en dur, qui vieilliraient mal.

Hors périmètre pour l'instant : les **débats du Sénat** (donc pas de Q2 sur un
dossier purement sénatorial) et l'enrichissement des **amendements** (base Ameli).
⚠️ Le **début de mandat** d'un sénateur n'est pas un trou d'ingestion : `senateurs.json`
ne publie **aucune date de mandat** (vérifié à la source). Le combler demanderait
une autre source (`data.senat.fr`, ODSEN) — d'ici là `depuis` reste `None` et
l'app masque le champ, ce qui est le comportement correct (§2.5).

**Trajectoire au Parlement** (`app/ingestion/navette.py`) — la frise est
calculée à l'ingestion depuis les **`actesLegislatifs`** des
`dossierParlementaire`, que l'archive *dossiers législatifs* (déjà téléchargée à
chaque run) contenait sans qu'on les lise. Ils donnent l'enchaînement officiel
**des deux chambres** avec dates et `statutConclusion` (AN1 · SN1 · CMP · CC ·
PROM). Liste fermée de 11 codes d'étape (on écarte « Travaux », « Débat » et
« Mise en application de la loi ») ; un libellé de conclusion non reconnu — dont
les avis du Conseil constitutionnel, qui ne sont ni adoption ni rejet — laisse
l'étape **sans statut** (§2.5). Repli pour les dossiers sans actes (`TXT-…`,
`SEN-…`) : les mentions de navette des objets de vote, **distinguées par
chambre**. C'est la raison du déplacement côté backend : les scrutins d'une
chambre ne peuvent pas documenter l'autre. ⚠️ Quand un dossier figure dans les
**deux** archives téléchargées (193 cas : un texte reporté après la dissolution
garde son `dossierRef` L16), c'est la copie de la législature **courante** qui
prime — celle de la précédente est un instantané figé, et 36 dossiers y sont
sans leur promulgation.

**Où en est le texte** (`etat_du_texte`, même module) — les mêmes actes donnent
l'état **d'aujourd'hui**, que la frise seule ne disait pas : `promulgue` (96 —
`PROM-PUB` livre `codeLoi`, la date, le JO et l'URL Légifrance, présents
ensemble sur 96/96, d'où la **source du texte en vigueur** posée sur le
dossier), `en_navette` (126 — la dernière étape retenue, telle quelle),
`resolution` (21), `conseil_constitutionnel` (7 — saisi sans conclusion
publiée), `retire` (4 — un `…RTRINI` **dans la dernière étape** seulement : un
retrait suivi d'autres actes ne conclut rien). Soit **254/328** ; sans actes,
pas d'état (§2.5). `resolution` mérite son état parce qu'une résolution est
conclue dès sa lecture unique — ni transmise à l'autre chambre, ni promulguée :
la ranger « en navette » ferait passer 21 textes terminés pour des textes en
attente. Le **code de procédure** (8 ou 22) est le seul indice retenu, jamais le
libellé de l'étape. ⚠️ **Aucun champ ne décrit une étape à venir** — un test le
vérifie sur la liste des champs elle-même. Préservé entre runs comme
l'initiative, et rattrapable seul par `python -m app.ingestion.etats`.

**La loi finale** (`app/ingestion/textes_adoptes.py`) — tout ce qui précède
décrit le texte **déposé** (exposé, dispositif, Q4) ; sur une loi promulguée,
cette version n'existe plus. `PROM-PUB.texteLoiRef` désigne le **texte
définitivement voté** (la « petite loi »), dont l'URL se dérive de l'`uid` comme
celle du texte déposé : `PIONANR5L17BTA0075` → `…/l17t0075_texte-adopte-seance`,
`PRJLSNR5S459BTA0040` → `senat.fr/leg/tas24-040`. `TexteAdopte` dissocie le
**lien** (posé dès que l'archive désigne le texte : 76/96) et le **corps** (stocké
seulement sous `_MAX_DISPOSITIF`, 45/76, car il sert de source à la Q4 et doit
être lu *entièrement* par le modèle). Q4 réécrite sur 44 (1 rejetée par les
garde-fous). ⚠️ Côté Sénat l'année de l'URL est celle de la **session**, jamais
approchée : la numérotation redémarre à chaque session, et un décalage d'un an
attrape un texte sans rapport (vérifié : `tas24-159` est une résolution
européenne sur la subsidiarité). ⚠️ Les **20 lois sans `texteLoiRef`** ne sont
pas devinées — leur dossier porte 2 à 4 textes adoptés (un par lecture), et le
plus récent est parfois la version *modifiée par le Sénat*, qui n'est pas la loi.
`decouper_loi` n'est pas `decouper_dispositif` : une petite loi n'a pas d'exposé,
son en-tête est administratif, et le découpage part du **premier article** —
repéré **sans** `IGNORECASE`, car les titres d'article sont capitalisés là où une
référence en prose ne l'est pas (« à l'article 45 de la Constitution », qui figure
justement dans cet en-tête). Préservé entre runs, rattrapable par
`python -m app.ingestion.lois`.

⚠️ **Pas d'Alembic** dans le dépôt (`init_models` = `create_all`, qui ne touche
jamais une table existante). Les colonnes ajoutées au modèle s'appliquent via
`python -m app.db.migrations` — DDL **additives et idempotentes**, à jouer après
un `git pull` qui change `db/models.py`.

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
python -m app.db.migrations               # colonnes ajoutées au modèle (additif, idempotent)
python -m app.ingestion.run --limit 300   # ingère l'open data AN + Sénat dans Postgres
python -m app.ingestion.senat --limit 40  # sénateurs + scrutins du Sénat seuls (~10 s)
python -m app.ingestion.deputes           # référentiel députés + votes nominatifs seuls
python -m app.ingestion.reformater        # recalcule titre court + accroche en base (ni réseau ni LLM)
python -m app.ingestion.revalider         # repasse les garde-fous sur les réponses en base, efface les fautives
python -m app.ingestion.divisions         # recalcule l'indice de division (rangée « votes les plus disputés »)
python -m app.ingestion.initiatives       # renseigne « qui porte le texte » en base (archive 10 Mo, ni PDF ni LLM)
python -m app.ingestion.etats             # renseigne « où en est le texte » en base (même archive de 10 Mo)
python -m app.ingestion.lois              # attache la LOI FINALE (texte voté) + réécrit la Q4 à l'indicatif
python -m app.ingestion.sources           # rapports de commission + recompose « les documents du dossier »
python -m app.ingestion.types_vote        # forme des scrutins (ordinaire/solennel/motion) + recompose la Q3
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
  api/                       Client HTTP : config (URL), client (fetch+timeout), dossiers+scrutins,
                             deputes, cache offline
  hooks/                     useDossiers / useDossier / useScrutin / useRecherche + useThemes
                             + useDeputes / useDepute (chargement + cache + états)
  constants/themes.ts        Emoji + teintes par thème
  constants/glossaire.ts     Glossaire : contenu + reconnaissance des libellés (§8)
  types/glossaire.ts         Types du glossaire (PAS un miroir backend — contenu local)
  utils/format.ts            Formatage dates, libellés de statut/position/chambre, temps de lecture
                             (⚠️ plus de `phasesNavette` : la trajectoire vient de l'API)
  utils/periodes.ts          Groupage/tri par période de la chronologie (écran Dossiers)
  components/                Composants réutilisables (DossierCard, StateViews…)
  screens/                   Un écran par fichier (barrel dans index.ts)
  navigation/
    types.ts                 Types de navigation (RootStack + MainTabs)
    MainTabs.tsx             Bottom tabs : Accueil · Recherche (→ ExplorerScreen) · Députés · Assistant · Profil
    RootNavigator.tsx        Stack : MainTabs + DossierDetail + ScrutinDetail + DeputeDetail
                             + Dossiers (résultats) + Glossaire + GlossaireTerme
```

Flux : `RootNavigator` → `MainTabs` (tabs) → `DossierDetail` puis `ScrutinDetail`
sont au niveau du stack racine (accessibles depuis Accueil ET Explorer, couvrent
la tab bar). `Dossiers` s'y trouve également : Explorer l'**ouvre** au lieu
d'afficher les résultats sur place, de sorte que la page de découverte reste
derrière et que le retour arrière y ramène.
`Glossaire` / `GlossaireTerme` y sont aussi : on y entre par
Explorer, mais également par l'aide en ligne d'une frise de dossier ou d'un titre
de fiche vote — d'où le libellé de retour **« Retour »** sur la fiche d'un terme
(plusieurs provenances) et « Explorer » sur l'index (une seule).

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
   `constants/glossaire.ts` est la **source unique** du glossaire, pour ses
   **deux surfaces** : les écrans dédiés (on vient y chercher un mot) et
   l'**aide en ligne** là où le mot s'affiche sans être expliqué — une étape de
   `TrajectoireNavette`, le titre d'une fiche vote —, dépliée par
   `DefinitionGlossaire`, qui renvoie vers la fiche complète. Un seul fichier
   pour les deux, sinon la même app explique un mot de deux façons. Les libellés
   affichés ne sont pas les entrées du glossaire (« 1ère lecture (2ème assemblée
   saisie) ») : la table `MOTIFS` fait le pont, **ordre significatif** (le cas
   particulier avant le général), motifs pliés d'avance car la source mélange
   les casses. Terme hors liste → aucune aide, on n'improvise pas d'explication
   (§2.5). Ajouter un terme = une entrée dans ce fichier, jamais une définition
   en dur dans un écran.
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
- **Icônes.** Deux jeux maison, même grammaire (tracés SVG `react-native-svg`,
  monochromes, la couleur vient de l'appelant) : `TabBarIcon` pour la **barre
  d'onglets** (couleur = état actif/inactif) et `IconLigne` / `ThemeIcone` pour
  les **écrans Explorer et Glossaire** (loupe, chevrons, portes d'entrée, et une
  icône par thème qui remplace l'emoji de `themeEmoji` sur ces écrans). Partout
  ailleurs, ce sont des emojis (thèmes, repères décoratifs →
  `importantForAccessibility="no"`). Pas de librairie d'icônes : une nouvelle
  icône se dessine dans l'un de ces deux fichiers.
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
**sous-amendements rattachés** à cet amendement, même forme), `sources` (**les
documents du dossier**, dans l'ordre de la vie du texte — liste **dérivée**, cf.
plus haut), `rapportsCommission?` (les rapports de commission, un par lecture,
URL vérifiée à l'ingestion : ils **alimentent** `sources`, la fiche ne les rend
pas à part), `statut`, `theme`, `dateDernierScrutin`, `trajectoire` (les étapes du texte au
Parlement, **les deux chambres**, calculées à l'ingestion — vide = frise
masquée), `etat?` (**où en est le texte aujourd'hui**, la clôture de la frise :
`etat` — `promulgue` | `resolution` | `retire` | `conseil_constitutionnel` |
`en_navette` — plus `date` / `etape` / `chambre` / `statut`, et pour une loi
`numeroLoi` / `dateJournalOfficiel` / `urlLegifrance`. ⚠️ **Aucun champ ne
décrit une étape à venir** : n'en ajoutez pas, et ne composez pas de phrase au
futur à partir de ceux-là), `miseAJour?` (badge §7.7),
`exposeMotifs?` (parole de l'auteur, bloc attribué), `dispositif?` (les
articles du texte **déposé** — fait officiel, jamais affiché brut, source de la
Q4), `texteAdopte?` (la **loi finale**, « petite loi » : `source` **toujours** —
le lien vers ce que le Parlement a voté — et `texte?` seulement sous le cap ;
prime sur `dispositif` comme source de la Q4, car celui-ci décrit une version que
la navette a modifiée. Jamais affiché brut non plus),
`initiative?` (**qui porte le texte** : `origine` — `gouvernement` |
`parlementaire` | `senat` — plus `nom` / `deputeId` / `groupeNom` /
`groupeCouleur` / `portraitUrl` quand l'auteur est un parlementaire identifié ;
`deputeId` suit la règle de `Votant`, posé **seulement s'il siège encore**),
`titreOfficiel` (la formulation d'origine, toujours conservée et affichée sur la
fiche §7.5), `titreClair` (titre d'affichage raccourci), `accroche?`
(le but du texte, tiré de la Q1 — **optionnelle**, absente = ligne masquée §2.5)
et `estEvenementAutonome` (motion de censure, déclaration : le dossier ne porte
**aucun texte de loi**). Ce dernier n'est pas un détail : une motion n'a ni
articles, ni exposé des motifs, ni trajectoire — non pas parce qu'on ne les a pas
trouvés, mais parce qu'ils n'existent pas. `QuestionsCard` **retire** alors les
questions sans objet (« pourquoi ce texte ? », « qu'est-ce que ça change ? ») et
renumérote les restantes, au lieu d'afficher « information non disponible », qui
ferait passer une absence de sens pour une lacune de nos données (§2.5). Le champ
est posé à l'ingestion — **jamais déduit de la forme de l'id** (`VTA-…`) : un
artefact d'ingestion n'est pas une sémantique. La partition
texte / amendement / sous-amendement se fait à l'ingestion (`est_amendement`,
`est_sous_amendement`, `numero_amendement_parent` sur l'objet du scrutin).
Un `Scrutin` est **vote-niveau** : `dossierId`, `objet` (ce sur quoi on a voté),
`statut`, `chambre` (`assemblee` | `senat` — un dossier agrège les votes des deux
assemblées, et « 214 pour » n'a pas la même échelle selon l'hémicycle),
`scrutinPublic`, `typeVote?` (`ordinaire` | `solennel` | `motion_censure` — la
**forme** du scrutin, qui explique le nombre de votants ; absente au Sénat),
`suffragesRequis?` (le seuil — **n'a d'intérêt que sur une motion de censure**),
`resultat`, `positionsGroupes` (avec `votantsPour` /
`votantsContre` / `votantsAbstention` optionnels — le **nominatif**, absent =
masqué, §2.5 ; chaque `Votant` porte son `nom` et, **uniquement s'il siège
encore**, son `deputeId`, seule clé qui rend le nom cliquable vers sa fiche),
`sousAmendements?` (pour le vote d'un amendement : ses sous-amendements),
`cible?` / `dispositif?` / `exposeSommaire?` (pour un vote d'amendement : son
contenu enrichi, cf. `amendements.py` — miroir des mêmes champs sur `Amendement`),
`questions?` (`QuestionsAmendement` : les questions citoyennes du vote
d'amendement — `pourquoi` / `changement` / `resultat`, générées à l'ingestion),
`sources`. La fiche dossier n'embarque que des `ScrutinResume` (liste
compacte) ; le `Scrutin` complet est servi par `GET /scrutins/{id}`. Le fil et la
recherche renvoient un `DossierListItem` allégé (dont `nombreScrutins`,
`miseAJour`, `accroche?`, `natureTexte?` et `chambres` — les chambres qui ont
voté le texte, sans quoi une carte du fil se lirait comme un vote de
l'Assemblée ; il ne porte PAS `titreOfficiel`, d'où la nature calculée côté API ;
il porte en revanche `typeVoteDernierScrutin?` / `suffragesRequisDernierScrutin?`,
sans quoi une motion de censure se lirait « 267 pour, 0 contre » jusque dans le
fil).
Côté **parlementaires** : `Depute` (identité + `chambre` + groupe +
circonscription + `commission?` + `depuis?` — le type garde son nom historique,
`chambre` est le discriminant ; ⚠️ `commission` n'est servie qu'au **Sénat**
(l'annuaire senat.fr la publie dans `organismes` : 346/348) et `depuis` qu'à
l'**Assemblée** — l'annuaire du Sénat **ne publie aucune date de mandat**, ce
n'est donc pas un trou d'ingestion à combler mais une absence de source),
`DeputeListItem` (annuaire — **photo comprise**, la liste doit
être identifiable sans charger chaque fiche), `DeputeDetail` (= `Depute` +
`portrait` + `historique` paginé), `PortraitVote` (12 mois glissants : `votes`,
`pour` / `contre` / `abstention`, `cohesionGroupe` — **pas de participation**, et
jamais de cohésion au Sénat, cf. « État actuel ») et `VoteDepute` (`objetType`,
`titre`, `dossierId?`, `position`, `contreSonGroupe?`). Types clés :
`StatutScrutin` (`adopte` | `rejete` | `en_cours`), `Chambre` (`assemblee` |
`senat`), `PositionVote`, `ObjetVote` (`dossier` | `amendement` |
`sous_amendement`), `NiveauConfiance`. Ce modèle est le **contrat de l'API** (miroir
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
- **Commission des députés** : `Depute.commission` n'est servie qu'au Sénat.
  Côté AN, l'archive AMO porte les mandats d'organe `COMPER`, mais
  `GroupResolver` ne garde que les organes `codeType == "GP"` — il faudrait
  l'étendre pour résoudre un `organeRef` de commission en libellé. Tant que ce
  n'est pas fait, la fiche d'un député masque simplement la ligne (§2.5).
- **Dossiers `TXT-` restants** (44 après le correctif des mentions finales, qui
  en a résorbé 10). Deux causes **mesurées**, de natures opposées :
  - **32** dont le titre est réellement absent de l'archive, dont quelques
    **coquilles de la source** (« de **ss**implification », « fin **des**
    gestion ») que `signature_titre` ne rattrape pas. Une distance d'édition
    tolérante à 1 caractère les récupérerait, au prix d'un risque de faux
    appariement à évaluer (§2.5 : ne jamais deviner).
  - **12** que l'archive contient pourtant, mais que le **garde-fou d'ambiguïté
    entre législatures** écarte : le même titre existe en L17 et en L16 (cas
    mesuré : « lutter contre la pédocriminalité » → `DLR5L17N50627` **et**
    `DLR5L16N49866`), donc la table s'abstient. C'est le **prix du repli sur la
    législature précédente** — il rattrape les textes reportés après une
    dissolution, mais fait perdre ceux dont le titre a été réutilisé. Piste :
    quand les candidats s'étalent sur plusieurs législatures, préférer la
    **courante** — ce n'est pas deviner (un scrutin de la 17e vote un dossier de
    la 17e ; un dossier L16 n'est pertinent que si AUCUN candidat L17 n'existe,
    ce qui est justement le cas du report après dissolution).
- **Sénat, suite** : les **comptes rendus** (`data.senat.fr/data/debats/cri.zip`,
  schéma XML distinct de SyceronBrut) pour que la Q2 « principal désaccord »
  existe aussi sur un dossier purement sénatorial ; l'enrichissement des
  **amendements** du Sénat (base Ameli) ; **Monalisa**
  (`senat.fr/akomantoso/{slug}.akn.xml`, XML structuré) qui remplacerait
  avantageusement le grattage PDF pour les textes déposés depuis déc. 2019.
- **V1.1** : filtres de recherche, partage. *(La fiche parlementaire en lecture
  seule est faite — cf. « État actuel ».)*
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
- ⚠️ **Ne jamais calculer « contre son groupe », de cohésion ou de dissidence au
  Sénat.** Le nominatif y est formellement par sénateur mais résulte d'une
  **délégation de vote par groupe**, et la source ne dit pas quels scrutins y
  échappent (ceux « à la tribune »). Le chiffre existerait, il ne voudrait rien
  dire — c'est exactement le piège que §7.4 interdit. Même famille de raisonnement
  que le refus du taux de participation côté AN.
- ⚠️ **Sur une motion de censure, `contre` et `abstention` valent 0 par
  construction** (art. 49 de la Constitution : seules les voix favorables sont
  recensées). Vérifié sur les 23 motions de la législature. Toute formule
  générique « X voix contre Y », tout écart pour/contre, toute barre pour/contre
  et tout indice de division y disent le contraire du fait — la comparer au
  **seuil** (`suffragesRequis`) est la seule lecture juste. Vécu : la Q3
  annonçait « rejeté par 0 voix contre 267 » sur les 23 motions.
- ⚠️ **Pas d'Alembic** : ajouter une colonne à `db/models.py` ne suffit pas, la
  base existante ne la verra jamais (`create_all` ne modifie pas une table). Il
  faut un énoncé dans `app/db/migrations.py` (additif et idempotent).
- Le nom `Depute` / `deputeId` / table `depute` couvre **les deux chambres** :
  c'est historique, `chambre` est le discriminant. Ne pas en déduire qu'un
  `Votant.deputeId` désigne un député — il peut valoir `SEN-…`.
- ⚠️ La « législature » d'un `ScrutinParse` **sénatorial** est en réalité une
  **session** (le Sénat ne numérote pas par législature). Ne jamais s'en servir
  pour bâtir une URL de l'Assemblée : utiliser `legislature_du_ref(dossierRef)`,
  qui la lit dans le `dossierRef` lui-même (`DLR5L17N…` → 17). Régression vécue :
  13 dossiers pointaient vers `/dyn/2025/dossiers/…`, une URL morte.
- L'URL d'un scrutin du Sénat prend l'année de **début de session**
  (oct.→sept.) : `scr2025-340` date du 21 juillet **2026**, et `scr2026.html`
  répond 404. Passer par `session_pour(annee, mois)`.
- ⚠️ Le fichier `MVP_Assemblee_Nationale_v2.md` est désormais **versionné** (commit
  `ff9c2a1`) : les `§x.y` y renvoient et sont vérifiables. Mais il n'a **pas** été
  mis à jour du décalage introduit ici (dossier-centré + §7.7 + levée §2.4) — sur
  ces trois points, c'est ce fichier-ci qui décrit le produit réel.
