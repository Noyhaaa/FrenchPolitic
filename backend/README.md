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

# Applique les colonnes ajoutées au modèle depuis la création de la base
# (`create_all` ne touche jamais une table existante). Additif et idempotent :
# à jouer après un `git pull` qui change `db/models.py`.
python -m app.db.migrations                 # --dry-run pour voir sans écrire

# Ingère les scrutins publics de la 17e législature (open data AN) ET les
# scrutins publics du Sénat de la session en cours.
python -m app.ingestion.run --limit 300     # 300 récents (~4 s) ; sans --limit = tout
python -m app.ingestion.run --sans-senat    # Assemblée seule

# Sénateurs + scrutins du Sénat UNIQUEMENT (annuaire senat.fr + pages de
# scrutins) : ni LLM, ni dossiers, ni amendements, ni débats. ~10 s pour
# 40 scrutins. La jointure vers les dossiers de l'Assemblée est faite, mais
# les dossiers ne sont pas reconstruits — c'est le rôle de `run`.
python -m app.ingestion.senat --limit 40    # --session 2025 pour forcer la session

# Députés + votes nominatifs UNIQUEMENT (référentiel AMO + ventilations des
# scrutins) : ni LLM, ni dossiers, ni amendements, ni débats. ~7 min sur toute
# la législature, là où un run complet dure des heures.
python -m app.ingestion.deputes             # --limit 300 pour les plus récents

# Recalcule le titre d'affichage (titre_court) et l'accroche (depuis la Q1 déjà
# validée) des dossiers DÉJÀ en base : ni réseau ni LLM, quelques secondes.
# Évite d'attendre une ingestion complète après un changement de formatage.
python -m app.ingestion.reformater          # --dry-run pour voir le bilan sans écrire

# Repasse les garde-fous COURANTS sur les réponses citoyennes déjà en base et
# efface celles qui ne passent plus (le run suivant les régénère). À lancer
# après tout ajout de contrôle à `valider_reponse` : les réponses validées sont
# réutilisées d'un run à l'autre, donc une réponse écrite avant un nouveau
# garde-fou y resterait sinon indéfiniment. Couvre aussi les arguments de la Q2,
# jugés contre l'extrait de compte rendu stocké (`dossier.desaccord_sources`) —
# un argument sans source est invérifiable, donc effacé. Ni réseau ni LLM.
python -m app.ingestion.revalider           # --dry-run pour voir le bilan sans écrire

# Recalcule l'indice de division des scrutins déjà en base (rangée « Les votes
# les plus disputés » de l'accueil). Nécessaire une fois après l'ajout de la
# colonne, puis à chaque changement des poids du calcul. Ni réseau ni LLM.
python -m app.ingestion.divisions           # --dry-run pour voir le classement

# Renseigne « qui porte le texte » (Dossier.initiative) sur les dossiers déjà en
# base. Ne télécharge que l'archive des dossiers législatifs (~10 Mo) et lit les
# identités dans la table `depute` : ni scrutins, ni PDF, ni LLM — quelques
# secondes au lieu d'un run complet. À rejouer quand les règles de
# `app/ingestion/initiative.py` changent.
python -m app.ingestion.initiatives         # --dry-run pour voir la répartition

# Renseigne « où en est le texte » (Dossier.etat) sur les dossiers déjà en base,
# et pose la source Légifrance des lois promulguées. Même archive (~10 Mo), même
# coût : ni scrutins, ni PDF, ni LLM. À rejouer quand les règles de
# `etat_du_texte` changent.
python -m app.ingestion.etats               # --dry-run pour voir la répartition

# Attache la LOI FINALE (Dossier.texteAdopte) aux lois promulguées et réécrit
# leur Q4 depuis elle, à l'indicatif. Archive des dossiers (~10 Mo) + les PDF
# des « petites lois ». --dry-run n'écrit rien et n'appelle pas le modèle,
# --sans-llm récupère les textes sans toucher aux questions.
python -m app.ingestion.lois                # --dry-run · --sans-llm

# L'API sert alors la base ingérée (REPOSITORY_BACKEND=postgres via .env).
uvicorn app.main:app --reload
```

L'ingestion télécharge l'archive des scrutins + l'archive AMO (organes **et
acteurs** : groupes + annuaire des députés pour le vote nominatif), parse,
contrôle la cohérence des décomptes, **regroupe les scrutins par dossier** et
upsert (idempotent) : les dossiers (liste compacte des votes), le détail de
chaque vote (table `scrutin`, avec les noms des votants) et — depuis la
fonctionnalité « Députés » — le **référentiel des députés** (table `depute`)
avec leurs **votes nominatifs** (table `vote_depute`, réécrits scrutin par
scrutin). Regroupement en
cascade : le `dossierRef` officiel quand il existe ; sinon **réconciliation** via
l'archive *dossiers législatifs* (le titre cité dans l'objet, comparé aux titres
officiels des législatures — **fold exact, puis signature, puis préfixe** : fold
sans espaces ni ponctuation, tolérant aux apostrophes et fautes de frappe de
l'archive (« afin de​garantir »), sans confondre ordinaire/organique ; le
troisième niveau (préfixe) rattrape les cas où l'**objet du vote lui-même est
tronqué** côté open data AN (constaté aux alentours de 90 caractères sur
plusieurs dossiers réels) — le titre cité s'arrête net en plein mot avant la
fin du titre officiel, plus long ; non ambigu à chaque niveau — retrouve le
vrai `dossierRef` et son lien officiel ; +24 dossiers récupérés via la
signature, +4 via le préfixe) ; sinon le **texte de rattachement**
(dossier reconstitué `TXT-…`, mentions de lecture ignorées, id dérivé de la
**signature** du titre plutôt que du simple fold — un même texte cité avec une
apostrophe droite sur un scrutin et courbe sur un autre fusionne en un seul
dossier au lieu de se scinder en deux) ; sinon un dossier
singleton (motion de censure, déclaration…). Le fil n'expose ainsi que des
textes — jamais un vote d'amendement isolé — et ~60 % ont leur page officielle.

⚠️ **Toutes** les mentions finales de procédure sont retirées du titre cité, pas
seulement la dernière : la source en enchaîne parfois deux (« …le droit à l'aide à
mourir **(seconde délibération) (deuxième lecture)** »). N'en retirer qu'une
laissait « (seconde délibération) » collé au titre, dont la signature ne
correspondait plus au titre officiel — le texte se **dédoublait** alors dans le
fil : une fiche complète et un `TXT-…` vide à côté. Mesuré sur la base de dev,
**10 dossiers `TXT-` sur 54** ont rejoint leur dossier officiel au run suivant
(dont l'aide à mourir, le PLF 2026, le PLFSS 2025 et 2026, Mayotte, le
narcotrafic) — « aide à mourir » est passé de 66 à **69 scrutins**, la somme
exacte des deux fragments. Les 44 restants se répartissent en **32** dont le
titre est absent de l'archive (dont des coquilles de la source : « de
**ss**implification », « fin **des** gestion ») et **12** que l'archive contient
mais que le garde-fou d'ambiguïté écarte, le même titre existant en L17 et en L16
(cf. le backlog de `CLAUDE.md`).

Un vote de **conduite de séance** (demande de suspension, de seconde délibération)
qui deviendrait un dossier à lui seul est **écarté du fil** — il ne décide de rien
et n'a ni texte ni trajectoire. Même prédicat que la rangée « votes les plus
disputés » (`est_vote_de_conduite_de_seance`). Le même vote formulé pendant
l'examen d'un texte reste un vote de ce dossier.
L'archive sert **uniquement** à retrouver le `dossierRef` : ses titres (en
minuscules, fragmentés) ne sont pas importés.

### Le Sénat (`app/ingestion/senat.py`, `senateurs.py`)

Le Sénat ne publie pas d'archive de scrutins comparable à celle de l'Assemblée.
Il expose en revanche, **par scrutin**, deux ressources jointes :

- `senat.fr/scrutin-public/{session}/scr{session}-{n}.html` — objet du vote, date
  de séance, sort, résultat global, **analyse par groupe** et lien vers le
  dossier législatif ;
- `…/scr{session}-{n}.json` — le **vote nominatif**, une ligne par matricule
  (codes `p` / `c` / `a` / `n`).

L'annuaire des sénateurs vient de `senat.fr/api-senat/senateurs.json` (matricule,
nom, groupe, circonscription, `organismes`, **photo officielle donnée par la
source** — pas dérivée, donc pas à vérifier comme côté AN). Endpoint non documenté
par data.senat.fr : traité en best-effort.

La **commission permanente** (`Depute.commission`, 346/348) se lit dans
`organismes` : les sept permanentes portent un `ordre` 7001-7007, tandis que la
commission des affaires européennes — à laquelle 41 sénateurs siègent **en plus**
de la leur — ouvre une autre série (8001). Retenir le plus petit `ordre` donne donc
la permanente, sans liste de libellés en dur qui vieillirait mal.

> ⚠️ L'annuaire **ne publie aucune date de début de mandat** (vérifié à la
> source : les champs servis sont matricule, nom, groupe, circonscription,
> organismes, avatar). `depuis` reste donc `None` pour les 348 sénateurs et l'app
> masque le champ — ce n'est **pas** un trou d'ingestion à combler, et le déduire
> de la série d'élection serait une supposition (§2.5). Il faudrait une autre
> source (`data.senat.fr`, jeu ODSEN).

> ⚠️ **`{session}` est l'année de DÉBUT de session** (octobre → septembre), pas
> l'année civile : le scrutin n° 340 de la session « 2025 » a eu lieu le
> **21 juillet 2026**, et `scr2026.html` répond 404. Même famille de piège que
> les zéros de tête des URLs de l'AN.

**Un texte, un dossier.** Le rattachement suit la même cascade que côté AN, pour
qu'un texte examiné dans les deux chambres ne se dédouble pas dans le fil :

1. la **jointure officielle** `titreDossier.senatChemin` des
   `dossierParlementaire` de l'archive AN (`construire_jointure_senat`) — l'AN
   publie elle-même l'URL du dossier Sénat correspondant : **873 dossiers
   appariés**, zéro requête réseau ;
2. le **lien inverse** : la page du dossier Sénat cite l'URL du dossier AN, dont
   le slug se résout via `titreDossier.titreChemin` (casse repliée : le Sénat
   écrit `PJL_relance_…`, l'archive `pjl_relance_…`) ;
3. la **réconciliation par titre** déjà en place — les objets de vote du Sénat
   citent leur texte exactement comme ceux de l'AN ;
4. sinon un **dossier d'origine sénatoriale** `SEN-{slug}` (le slug du Sénat est
   stable, contrairement au titre : pas besoin de le hacher) ;
5. sinon le scrutin est son propre dossier (motion, débat).

Mesuré sur les 12 derniers scrutins de la session : **12/12 rattachés** à un
dossier de l'Assemblée.

Les objets de vote du Sénat sont **structurellement identiques** à ceux de l'AN
au préfixe « sur » près (« sur l'ensemble du projet de loi… ») : on le retire à
l'entrée, et tout l'aval (classement texte/amendement, vote décisif,
rattachement par titre) s'applique sans adaptation. Deux différences traitées à
part : l'auteur s'écrit « présenté par M. Prénom Nom » (l'AN écrit « de M. Nom »),
et l'**article visé** est cité par l'objet lui-même (côté AN il vient de
l'archive des amendements). Nouveau cas, absent de l'AN : les **amendements
identiques** (« les amendements identiques n° 154…, n° 207… et n° 410 ») portent
plusieurs numéros — on n'en retient **aucun** plutôt que de laisser croire que le
vote ne portait que sur le premier (§2.5).

> ⚠️ **Pas de « contre son groupe » ni de cohésion au Sénat.** Dans un scrutin
> public **ordinaire**, les bulletins sont déposés par un délégué de groupe pour
> l'ensemble de ses membres : le nominatif y reflète la position du **groupe**,
> pas l'acte individuel. La source ne permet pas non plus de distinguer ces
> scrutins de ceux **à la tribune** (art. 59), qui seuls sont individuels. Une
> divergence calculée là-dessus serait un artefact de procédure présenté comme un
> fait politique : `contre_son_groupe` et `cohesion` restent **toujours `None`**
> (§7.4), et la fiche vote porte une mention factuelle expliquant la lecture.

Les sénateurs vivent dans **les mêmes tables** que les députés (`depute`,
`vote_depute`, `groupe`), discriminés par `chambre` ; leurs identifiants sont
préfixés (`SEN-…`) pour ne jamais heurter les `acteurRef` (PA…) et `organeRef`
(PO…) de l'Assemblée. L'annuaire du Sénat ne publiant pas de couleur de groupe,
`COULEURS_GROUPES_SENAT` en fixe une par code — choix de présentation assumé et
symétrique (§7.4), comme `GROUP_COLORS` côté AN, pas une donnée de la source.

### Trajectoire au Parlement (`app/ingestion/navette.py`)

La frise de la fiche dossier était dérivée côté app des **objets des votes AN**,
ce qui la condamnait à une seule chambre. Elle est désormais calculée à
l'ingestion depuis les **`actesLegislatifs`** des `dossierParlementaire` — que
l'archive *dossiers législatifs*, déjà téléchargée à chaque run, contenait sans
qu'on les lise. Ils décrivent l'enchaînement officiel complet, avec dates et
`statutConclusion` :

```
AN1  1ère lecture (1ère assemblée saisie)   2026-06-02  adopté
SN1  1ère lecture (2ème assemblée saisie)   2026-07-02  modifié
CMP  Commission Mixte Paritaire             2026-07-17  Accord
CC   Conseil constitutionnel                2026-07-24  (sans statut)
```

Liste fermée de 11 codes d'étape retenus (les 16 existants moins « Travaux »,
« Débat » et « Mise en application de la loi », qui ne décrivent pas le parcours
du texte). Le vocabulaire de conclusion est riche et circonstancié (« adoptée,
dans les conditions prévues à l'article 45, alinéa 3… », « considéré comme
rejeté… ») : seul ce qui est sans ambiguïté donne un statut, le reste — dont les
avis du Conseil constitutionnel, qui ne sont ni adoption ni rejet — laisse
l'étape **sans statut** (§2.5). Repli pour les dossiers sans actes (`TXT-…`,
`SEN-…`) : les mentions de navette des objets de vote, **distinguées par
chambre** (« Première lecture » à l'Assemblée et au Sénat sont deux étapes).

⚠️ **La copie de la législature courante prime.** 193 dossiers figurent dans les
deux archives téléchargées (un texte reporté après la dissolution garde son
`dossierRef` L16), mais celle de la législature précédente est un instantané
**figé** : mesuré, 36 d'entre eux y sont sans leur promulgation, que l'archive
courante documente. La première copie vue gagne, et la liste commence par la
courante.

### Où en est le texte (`etat_du_texte`, même module)

La frise, seule, ne raconte que le **passé** : un lecteur devant une loi
promulguée voyait la même chaîne de pastilles grises qu'un texte encore en
navette. `etat_du_texte` lit dans les **mêmes actes** l'état d'aujourd'hui —
liste fermée, premier signal positif rencontré :

| État | Signal dans l'archive | Mesuré |
|---|---|---|
| `promulgue` | `PROM-PUB` (+ `codeLoi`, `infoJO`) | 96 |
| `en_navette` | la dernière étape retenue, telle quelle | 126 |
| `resolution` | `procedureParlementaire` 8 ou 22 + étape conclue | 21 |
| `conseil_constitutionnel` | `CC-SAISIE-*` sans `CC-CONCLUSION` | 7 |
| `retire` | `…RTRINI` **dans la dernière étape** | 4 |
| *(aucun)* | dossier sans actes (`TXT-…`, `SEN-…`) | 74 |

Soit **254/328 dossiers** qui répondent à « et maintenant ? ».

⚠️ **Aucun champ ne décrit une étape à venir**, et un test le vérifie. Le
calendrier parlementaire est une décision politique (inscription à l'ordre du
jour, convocation d'une CMP), pas une donnée lisible dans l'archive : annoncer
« prochaine étape : le Sénat » serait une prédiction (§2.5). Un texte en
circulation reçoit son **dernier point documenté**, suivi de ce que la source ne
dit pas (« Aucune étape postérieure n'est publiée »).

Deux choix qui ne vont pas de soi :

- **`resolution` mérite son état.** Une résolution est conclue dès sa lecture
  unique — ni transmise à l'autre chambre, ni promulguée. La ranger dans
  `en_navette` ferait passer 21 textes **terminés** pour des textes en attente.
  Le code de procédure est le seul indice retenu : on ne devine pas la nature
  d'un texte à partir du libellé de son étape.
- **Un `RTRINI` ne compte que dans la dernière étape.** Un retrait suivi
  d'autres actes ne conclut rien.

Le `PROM-PUB` donne en prime le lien vers le texte **en vigueur**
(`EtatTexte.url_legifrance`) : l'URL est celle que l'Assemblée publie dans
`infoJO`, jamais une URL construite ici ; elle n'est pas vérifiée à l'ingestion
(Légifrance répond 403 à tout script, challenge Cloudflare — ce n'est pas une
preuve de lien mort), et la référence écrite (n° + date + JO) reste affichée à
côté. ⚠️ Ce lien **ne figure pas** dans `Dossier.sources` : il vit dans la carte
« La loi », appairé au texte voté (cf. ci-dessous). L'y laisser afficherait deux
fois la même URL sous deux libellés — d'où `sources_sans_le_lien_de_la_loi`, qui
retire l'URL **exacte** de l'état et non « tout ce qui ressemble à du
Légifrance » (une source légitime peut y pointer).

### La loi finale (`app/ingestion/textes_adoptes.py`)

Tout ce que l'app décrivait d'un texte venait de son **dépôt** : l'exposé des
motifs, le dispositif, et « qu'est-ce que ça change ? ». Sur une loi promulguée,
cette version n'existe plus — la navette et les amendements l'ont modifiée. La
fiche de la **loi n° 2025-379**, en vigueur, affichait donc :

> « Selon l'auteur du texte, cette *proposition* de loi *permettrait* de
> renforcer la coordination entre les forces de sécurité… »

Le pitch de l'auteur, au conditionnel, sur une proposition. **Mesuré : 83 des
96 lois promulguées** étaient dans cet état.

L'archive désigne elle-même le bon texte : `PROM-PUB.texteLoiRef` pointe vers le
document adopté (la « petite loi »), dont l'URL se dérive de l'`uid` comme celle
du texte déposé :

```
PIONANR5L17BTA0075  → assemblee-nationale.fr/dyn/17/textes/l17t0075_texte-adopte-seance
PRJLSNR5S459BTA0040 → senat.fr/leg/tas24-040
```

| | Mesuré |
|---|---|
| `texteLoiRef` présent → **lien** posé | **76 / 96** |
| corps sous le cap `_MAX_DISPOSITIF` → **source de la Q4** | **45 / 76** |
| Q4 réécrite à l'indicatif | **44** (1 rejetée par les garde-fous) |
| sans `texteLoiRef` | 20 → rien (§2.5) |

`TexteAdopte` dissocie **le lien et le corps** à dessein : le lien vaut dès que
l'archive désigne le texte, le corps seulement s'il peut être lu *entièrement*
par le modèle (au-delà — budget, PLFSS — on n'attache rien, jamais un tronçon).

⚠️ **Côté Sénat, l'année de l'URL est celle de la session** (oct.→sept.), déduite
de la date de publication du document via `session_pour`. Elle n'est jamais
approchée : la numérotation redémarre à chaque session, si bien qu'un décalage
d'un an attrape un texte **sans rapport** (vérifié : `tas24-159` est une
résolution européenne sur la subsidiarité, là où `tas25-159` devait être une loi
sur les maladies cardio-neuro-vasculaires). Un 404 ne donne rien, il ne déclenche
aucun repli.

⚠️ **Les 20 lois sans `texteLoiRef` ne sont pas devinées.** Leur dossier porte
pourtant 2 à 4 textes adoptés (un par lecture, dans chaque chambre) — en élire un
serait choisir à la place de la source, et le plus récent est parfois la version
*modifiée par le Sénat*, qui n'est justement pas la loi.

`decouper_loi` n'est pas `decouper_dispositif` : une petite loi n'a pas d'exposé
des motifs, et son en-tête est administratif (« TEXTE ADOPTÉ n° 75 », « (Texte
définitif) », « L'Assemblée nationale a adopté… », « Voir les numéros : … »). Le
découpage part donc du **premier article**, repéré **sans** `IGNORECASE` : les
titres d'article sont capitalisés, alors qu'une référence en prose ne l'est pas
(« à l'article 45 de la Constitution »… qui figure justement dans l'en-tête).

**La Q4 gagne un barreau au-dessus des deux existants** (`app/ai/questions.py`) :

| Priorité | Source | Registre | Attribution |
|---|---|---|---|
| 1 | texte **voté** (la loi) | **indicatif** | aucune |
| 2 | dispositif du texte déposé | conditionnel | aucune |
| 3 | exposé des motifs | conditionnel | « Selon l'auteur du texte » |

C'est le prolongement de la règle déjà en place (« le fait officiel prime sur la
parole du déposant ») : **la loi votée prime sur le texte déposé**. Une réponse
déjà en base est regénérée dès qu'une source plus haute apparaît — même mécanisme
que celui qui faisait déjà remonter l'exposé vers le dispositif. Le seul mot qui
change dans le prompt est le registre : le conditionnel dit « ce n'est qu'une
proposition », ce qui serait faux d'un texte en vigueur.

### Qui porte le texte (`app/ingestion/initiative.py`)

L'app disait *ce qui a été voté* et *comment chaque groupe a voté*, jamais **d'où
vient le texte** : un projet de loi du Gouvernement et une proposition déposée
par une députée de l'opposition s'affichaient à l'identique. La même archive le
dit pourtant, sur le **document de dépôt** : `auteurs.auteur` porte soit un
`acteurRef` (+ `qualite`), soit un `organeRef`.

Trois origines, et rien d'autre :

| Origine | Règle | Mesuré (dossiers officiels) |
|---|---|---|
| `gouvernement` | le texte est un *projet* de loi (art. 39) | 49 |
| `parlementaire` | **un seul** auteur de `qualite="auteur"` | 124, dont 110 nommés |
| `senat` | auteur = organe `PO838901` **et** dépôt `INITNAV` | 69 |

**242 / 255**, et **zéro contradiction** avec la nature écrite dans le titre
officiel (contrôle croisé en base : aucun `parlementaire`/`senat` sur un « projet
de loi », aucun `gouvernement` ailleurs).

Quatre refus qui font la fiabilité du champ :

- **On ne nomme pas le ministre** déposant d'un projet de loi. Sa qualité
  ministérielle n'est documentée dans aucune de nos sources, et 7 cas sur 48
  seulement seraient nommables : une attribution qui ne marche qu'une fois sur
  sept vaut moins que « Gouvernement », exact partout.
- **Plusieurs auteurs → aucun nom.** L'origine reste vraie, mais désigner le
  premier de la liste serait choisir à la place de la source (§2.5) — même règle
  que `normalize.auteur_amendement`. Mesuré : 140 dépôts sur 143 n'ont qu'un
  auteur, la prudence ne coûte presque rien.
- **Un `qualite="rapporteur"` n'est jamais un auteur**, alors qu'il figure dans
  la même liste.
- **L'initiative se lit sur le dépôt initial**, jamais sur un document de
  navette : un texte renvoyé par le Sénat après une première lecture à
  l'Assemblée y est signé du Sénat, s'y rabattre ferait passer un texte né à
  l'Assemblée pour un texte sénatorial.

L'`acteurRef` est résolu en nom + groupe + **photo officielle** + `deputeId` par
le même référentiel que le vote nominatif (la photo est celle de la table
`depute`, déjà vérifiée à l'ingestion — on n'en dérive **aucune** ici ; absente,
l'app affiche les initiales). Même frontière : `deputeId` n'est posé que si le
parlementaire est au référentiel servi par l'API — un ancien député garde son
origine mais perd son nom et son lien (jamais de `PA…` affiché, jamais de 404).
⚠️ Le groupe est celui du député **aujourd'hui** : l'archive AMO ne publie que
les mandats actifs, celui qu'il avait au dépôt n'y est plus.

Préservée entre runs comme l'exposé des motifs (un run dont le téléchargement de
l'archive a échoué ne l'efface pas), et rattrapable seule par
`python -m app.ingestion.initiatives`.

**Législature courante ET précédente.** `construire_reconciliation` /
`construire_index_textes` / `construire_index_numeros` prennent désormais un
**tuple de législatures**, pas une seule : l'archive *dossiers législatifs* est
téléchargée pour la législature courante et, en best-effort, pour la
précédente (`SyncJob.run`, §1bis). Un dossier **reporté après une dissolution**
garde son `dossierRef` d'origine (cas réel constaté : « Projet de loi de
simplification de la vie économique », `dossierRef` en `L16`, encore voté en
`L17`) — restreindre à la seule législature courante empêchait de le
retrouver par titre, le fragmentant en `TXT-…` et lui faisant perdre à la fois
son exposé des motifs et l'enrichissement de ses amendements (la clé de
jointure de l'archive amendements est le `dossierRef`). Le garde-fou
d'ambiguïté (un titre → un seul dossier, jamais deviné) protège déjà contre une
collision de titre entre deux législatures ; élargir la fenêtre ne l'affaiblit
pas. Un échec de téléchargement de l'archive de la législature précédente
n'est pas fatal (best-effort, §2.5) : le run continue sur la seule courante.
**Exposé des motifs** (`app/ingestion/textes_an.py`) : l'archive ne porte pas le
corps des textes (métadonnées seules), mais le **PDF du texte déposé** est
public et son URL se **dérive de l'`uid`** du document (`…L17B0369` →
`…/dyn/17/textes/l17b0369_proposition-loi.pdf` — les **zéros de tête sur
4 chiffres sont indispensables**, sans eux le site répond 404). Les
**propositions de résolution** ont leur propre famille d'uid (`PNREAN…`, ni
`PION…` ni `PRJL…`) et leur propre suffixe d'URL (`…_proposition-resolution.pdf`) —
absents jusqu'ici de `url_page_texte`/`construire_index_textes`, ce qui privait
**tous** les dossiers de résolution de leur exposé malgré un `dossierRef`
officiel (bug corrigé ; ~31 dossiers concernés). On en extrait l'exposé des
motifs (via `pypdf`) en essayant les textes déposés du **dépôt initial** au plus
récent (l'exposé n'est que dans le dépôt initial ; les versions de navette ne
l'ont pas). **Repli Sénat** (`app/ingestion/textes_senat.py`) : quand le texte
AN n'est qu'une **transmission du Sénat** (dispositif seul, en-tête « PROPOSITION
DE LOI ADOPTÉE PAR LE SÉNAT, TRANSMISE PAR… »), l'exposé vit sur senat.fr ; le
PDF de transmission cite les numéros Sénat (« Sénat : 452 … (2024-2025) »), d'où
on dérive l'URL `senat.fr/leg/{ppl|pjl}{AA}-{numéro sur 3 chiffres}.pdf` (les
deux préfixes essayés) et on extrait l'exposé avec le même découpage. **Le
numéro doit être zéro-paddé sur 3 chiffres** (« pjl25-024.pdf », pas
« pjl25-24.pdf » → 404) — même piège que les zéros de tête côté AN, repéré en
creusant les dossiers sans exposé (bug corrigé : sans le padding, la récupération
échouait pour 100 % des références Sénat à numéro court, silencieusement —
best-effort, §2.5, donc invisible sans creuser). Récupère ~38 dossiers d'origine
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

**Robustesse d'un run long (`SyncJob.run`, plusieurs heures sur la législature
complète).** Un **commit par dossier** (pas un commit unique en fin de run) :
une interruption (crash, redémarrage, Ctrl-C) ne perd que le dossier en cours
de traitement — tout ce qui est déjà committé (résumés, questions LLM
validées…) survit, au lieu de tout reperdre. La CLI affiche une **ligne de
progression** par dossier (`[i/total] titre`) via `on_progress` (callback
optionnel de `SyncJob`, découplé de la CLI). Deux caches évitent du travail
redondant à chaque run : l'**exposé des motifs** n'est retéléchargé/reparsé que
s'il n'est pas déjà en base pour ce dossier (un texte déposé ne change pas,
`_expose_en_base`) ; la **reclassification de thème** LLM n'est retentée que si
le thème en base n'est pas déjà résolu (`_theme_en_base`) — sans ce cache, un
dossier déjà classé était quand même repassé au LLM à chaque run (la fusion
finissait par préserver le bon thème, mais après un appel gaspillé).

> Le modèle de tables a évolué (dossiers allégés + table `scrutin` au format
> vote-détaillé). Après mise à jour du code, **relancer l'ingestion** pour
> recréer/remplir les tables (les payloads précédents ne sont plus au bon format ;
> au besoin `DROP TABLE dossier; DROP TABLE scrutin;` avant).

- Documentation interactive : http://localhost:8000/docs
- Santé : http://localhost:8000/health

## Endpoints (cœur produit, §3 du MVP)

| Méthode | Route              | Écran            | Description                                   |
|---------|--------------------|------------------|-----------------------------------------------|
| GET     | `/accueil`         | Accueil (1)      | Écran complet en une réponse : à la une, aujourd'hui/hier, **votes les plus disputés**, rangées par thème |
| GET     | `/recap`           | Accueil (1)      | Activité du dernier mois actif (votes, adoptés/rejetés, textes) |
| GET     | `/dossiers`        | Fil paginé       | Derniers dossiers, du plus récent au plus ancien |
| GET     | `/dossiers/{id}`   | Fiche dossier (2)| Résumé sourcé + votes sur le texte + amendements |
| GET     | `/scrutins/{id}`   | Fiche vote (3)   | Détail d'un vote (texte ou amendement) : groupes + nominatif |
| GET     | `/recherche?q=&theme=` | Recherche (4) | Multi-termes (tous exigés) classée par pertinence ; `theme` seul parcourt le thème |
| GET     | `/themes`          | Recherche (4)    | Thèmes réellement présents + nombre de dossiers — les filtres |
| GET     | `/deputes?q=&groupe=&chambre=` | Annuaire | Parlementaires (ordre alphabétique), filtrables par chambre, groupe et recherche libre |
| GET     | `/deputes/{id}`    | Fiche parlementaire | Identité + portrait de vote (12 mois) + 1re page d'historique |
| GET     | `/deputes/{id}/votes` | Fiche parlementaire | Historique paginé (« charger les votes plus anciens ») |
| GET     | `/groupes?chambre=` | Annuaire        | Groupes politiques (nom, abréviation, couleur, chambre) — filtres |
| GET     | `/health`          | —                | Statut du service                             |

**Les votes les plus disputés (rangée d'accueil)** — `app/domain/division.py`,
fonction pure partagée par les deux repositories. « Disputé » qualifie
**l'arithmétique du scrutin**, jamais la mesure votée (§4.3) : l'ordre vient de
trois composantes lues sur les décomptes officiels — l'**écart** de voix (0,6),
la part d'**abstention** (0,2), la **fracture entre groupes** (0,2, soit le
nombre de positions majoritaires distinctes) —, le tout pondéré par l'**ampleur**
(à division égale, un vote à 371 votants pèse plus qu'un à 60 : sans ce facteur
le classement remonte des amendements votés dans un hémicycle vide).

Trois exclusions, toutes §2.5 : vote **à main levée** (rien à mesurer), vote de
**moins de 50 votants** (« serré » n'y veut rien dire), et vote de **conduite de
séance** — suspension, prolongation au-delà de minuit, seconde délibération
(`est_vote_de_conduite_de_seance`, liste fermée relevée sur les objets réels) :
souvent très serrés, mais ils ne décident de rien. Un même dossier n'occupe pas
plus de **2** places (`limiter_par_dossier`), sinon un texte clivant monopolise
la rangée avec ses lectures successives.

⚠️ La **dispersion interne** (groupes dont plus d'un cinquième des voix s'écarte
de leur majorité) est calculée et **affichée**, mais **pas classante** : elle est
incalculable au Sénat (délégation de vote par groupe), et la pondérer reviendrait
à classer les deux chambres sur des critères différents — l'une pénalisée par une
composante manquante, l'autre avantagée par sa renormalisation. Le classement ne
retient donc que ce qui est observable des deux côtés.

L'indice vit dans la colonne indexée `scrutin.indice_division` (le tri porte sur
toute la table), posée à l'ingestion et rattrapable par
`python -m app.ingestion.divisions`. Les **chiffres affichés**, eux, sont toujours
recalculés depuis le scrutin servi : la colonne ne sert qu'à ordonner.

**Recherche (§3.3)** — `app/domain/recherche.py`, trois fonctions **pures**
partagées par les deux repositories (les tests tournent sur `memory`, ils doivent
donc prouver le comportement servi en production) :

- `index_recherche(dossier)` est la **source unique** de `search_index`, appelée
  à l'ingestion comme par `reformater`. Au-delà des titres, de l'accroche et du
  thème, elle indexe les réponses **Q1 « pourquoi »** et **Q4 « ce que ça
  change »** et les **publics concernés** — c'est là que vit le vocabulaire du
  lecteur (« logement », « hôpital »), absent des titres officiels (« habitat »,
  « loi de finances »). Mesuré sur 17 requêtes réalistes : **7 sans aucun
  résultat avant, 2 après**. L'**exposé des motifs** est délibérément exclu :
  long et argumentatif, il ramenait 41 % du corpus sur « fin de vie ».
- `termes(requete)` découpe et plie ; les termes de moins de 2 caractères sont
  écartés. **Tous** les termes sont exigés (ET) — « loi mayotte » trouve les
  textes qui portent les deux mots, même éloignés, ce qu'un `LIKE` du bloc
  entier ne faisait pas.
- `score(champs, termes, requete)` classe : phrase exacte dans un titre (4) >
  tous les termes dans les titres (3) > accroche/thème (2) > ailleurs dans
  l'index (1). À score égal, la date décroissante — le tri d'origine. Côté
  Postgres le `LIKE` par terme sert de **préfiltre** (l'index B-tree reste
  exploité), le classement se fait ensuite sur au plus 200 candidats.

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
  domain/recherche.py  Index, découpage en termes et pertinence (pur, partagé par les 2 repos)
  db/                models.py (dossier, scrutin, groupe, depute, vote_depute, sync_run) · session.py (moteur async)
                     migrations.py  DDL additives idempotentes (pas d'Alembic : `create_all` ne modifie pas l'existant)
  repositories/      Protocole + in-memory (seed) + postgres (ingéré) — choix via config
  data/seed.py       Dossiers + députés FICTIFS de démonstration (backend « memory »)
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
    senat.py         Scrutins publics du Sénat (senat.fr) : parse_page_scrutin + parse_scrutin_senat (purs) + CLI autonome
    senateurs.py     Référentiel des sénateurs + votes nominatifs (purs) — jamais de « contre son groupe »
    navette.py       Trajectoire au Parlement : actes législatifs officiels (2 chambres), repli sur les objets de vote
                     + etat_du_texte : où en est le texte AUJOURD'HUI (jamais l'étape suivante) + source Légifrance
    debats.py        Comptes rendus (SyceronBrut) : explications de vote par groupe + liaison au vote
    amendements.py   Contenu des amendements (dispositif + exposé sommaire + article visé) : archive AN → index (dossierRef, numéro)
    textes_an.py     Exposé des motifs ET dispositif : uid → URL du PDF officiel → extraction (pypdf)
    textes_adoptes.py La LOI FINALE (« petite loi ») : texteLoiRef → URL AN/Sénat → articles votés, source de la Q4
    textes_senat.py  Repli exposé/dispositif : texte de transmission Sénat → PDF senat.fr → extraction
    organes.py       Résolution des groupes (AMO) + couleurs + annuaire des députés
    deputes.py       Référentiel des députés + votes nominatifs (pur) + CLI autonome
    normalize.py     Thème (heuristique), positions, décomptes, titre d'affichage (titre_court)
    sync.py          Job download → parse → regroupement par dossier → upsert (idempotent)
    run.py           CLI : python -m app.ingestion.run
    reformater.py    CLI : recalcule titre court + accroche des dossiers en base (sans réseau ni LLM)
    revalider.py     CLI : repasse les garde-fous sur les réponses en base, efface celles qui échouent
    divisions.py     CLI : recalcule l'indice de division des scrutins en base (rangée « votes disputés »)
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
  Chaque votant (`Votant`) porte son `nom` et, **uniquement s'il figure au
  référentiel `depute`**, son `depute_id` — c'est lui qui rend le nom cliquable
  vers la fiche du député, et un lien ne doit jamais mener à un 404. Mesuré sur
  la base de dev : 645 votants distincts, dont **577 siègent encore** (les 68
  autres, mandats terminés en cours de législature, gardent leur nom sans lien).
  Un acteur **absent de l'annuaire AMO** est en revanche **retiré de la liste** :
  sa référence machine (« PA795808 ») n'est pas un nom, et l'afficher comme tel
  trompait le lecteur (17 638 occurrences avant correction). Le décompte affiché
  reste celui, officiel, du groupe — l'écart est donc visible, pas masqué.
- **Députés** (§5.2) : référentiel (`depute`) construit depuis l'archive AMO —
  nom, groupe (mandat GP en cours, couleur partagée avec les ventilations),
  circonscription (« Pas-de-Calais, 5ᵉ circ. »), début de mandat — et **votes
  nominatifs** (`vote_depute`, une ligne par député × scrutin, écrite par lots).
  Mesuré sur la base de dev : **577 députés**, **1 270 476 votes** sur 8 434
  scrutins. La fiche député en dérive un **portrait sur 12 mois glissants**
  (votes exprimés et leur ventilation, cohésion = part des votes suivant la
  majorité de son groupe) et un
  **historique paginé**. « Contre son groupe » est un **fait déduit** du même
  scrutin (position ≠ `positionMajoritaire` du groupe), calculé pour les seules
  positions exprimées et **absent** quand le groupe n'a pas de position
  majoritaire exploitable ; un ratio au dénominateur nul reste `null`
  (« information non disponible », jamais 0 %, §2.5). La **photo officielle**
  est le seul champ dont l'URL est *dérivée* (`.../tribun/{leg}/photos/carre/
  {acteurRef sans PA}.jpg` — le référentiel AMO ne la porte pas) : elle n'est
  attachée qu'après vérification (HEAD 200 + `content-type: image/…`,
  `attacher_portraits`), sinon `null` et l'app affiche les initiales. Mesuré :
  **576/577** photos confirmées. **Aucun taux de
  participation n'est produit** : l'open data ne recense que les votants
  physiques d'un scrutin public (268 en moyenne sur 577, médiane de 44 % même
  sur les seuls votes sur l'ensemble), si bien que tout ratio de présence se
  lirait comme un score d'absentéisme que la source ne soutient pas (§7.4). Pas d'URL de portrait :

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

**Dispositif du texte — la source factuelle de « ce que ça change » (en place)**
- Le **même PDF** porte, après l'exposé, le **dispositif** : les articles du
  texte. `decouper_dispositif` commence exactement là où `decouper_expose`
  s'arrête (marqueur `_RE_FIN`), donc **aucun téléchargement supplémentaire**.
  Stocké dans `Dossier.dispositif` (texte + source).
- **Jamais affiché brut** : c'est du droit codifié (« Le troisième alinéa de
  l'article L. 815-13 du code de la sécurité sociale est complété par… »),
  illisible pour un citoyen. Il sert de **source vérifiable** à la Q4 et le
  lecteur l'atteint en 1 tap par le lien (§7.5).
- **Cap `_MAX_DISPOSITIF` = 10 000 caractères, sans troncature** : au-delà, on
  n'attache rien. Le modèle doit lire la source ENTIÈREMENT, sinon il présente un
  bout de loi comme le texte entier (§2.5). Calibré sur 25 textes réels : 17 sous
  7 000 caractères, puis 9 461 / 14 351 / 26 301 / 37 528, et les textes
  budgétaires à 217 000-266 000. Épreuve : à 1 455 et 6 636 caractères
  mistral-small tient la consigne ; à 15 711 il produit un rapport structuré de
  3 000 caractères, rejeté par les garde-fous (l'appel est perdu pour rien).
- Effet de bord assumé : un texte hors cap n'aura jamais de dispositif, donc son
  PDF est retéléchargé à chaque run (pas de marqueur d'absence inventé en base).

**Publics concernés — liste fermée (en place)**
- `app/ai/publics.py` : même doctrine que le thème (rangement, pas de prose).
  19 publics (Salariés, Locataires, Agriculteurs, Patients, Soignants,
  Consommateurs, Enfants, Communes…), sortie **validée exact-match**, cap 3,
  hors-liste ignoré, rien de valide → `public_concerne` vide → section « Qui est
  concerné ? » masquée (§2.5). ⚠️ Miroir obligatoire de `publicEmoji`
  (`src/screens/DossierDetailScreen.tsx`).
- Le prompt a été calibré sur des textes réels : trop permissif il ajoutait des
  publics par ricochet (« Étudiants » sur un texte de sécurité routière), trop
  strict il répondait « aucun » 12 fois sur 18. La version en place vise les
  publics **directement** visés et réserve « aucun » aux textes institutionnels,
  procéduraux ou symboliques.

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
  débats** (`debats.py`, archive « SyceronBrut »). Trois viviers de prises de
  position, par ordre de préférence (`_VIVIERS`) : la section « Explications de
  vote » (variantes « Explication de vote », « … communes » comprises), où
  chaque groupe explique lui-même sa position ; à défaut la **discussion
  générale** ; à défaut seulement les débats **sans section dédiée** — motion de
  rejet préalable (`MOTION_RP_1_1`) et paroles placées directement sous le titre
  de discussion (motion de censure, déclaration au titre de l'article 50-1).
  Les morceaux **consécutifs** d'un même orateur sont recollés (une parole
  hachée par les interruptions ne doit pas être réduite à son premier fragment)
  et la **présidence de séance est écartée** par sa fonction : elle est
  elle-même députée, donc porteuse d'un `acteurRef`, et ses annonces d'ordre du
  jour seraient sinon attribuées à son groupe (§7.4).

  Le débat est relié au **vote conclusif** du dossier (`_vote_conclusif` :
  ensemble > article unique > texte cité directement > vote procédural > motion ;
  **jamais** un vote d'article numéroté — le débat sur l'article 27 du budget
  n'est pas une position sur le texte). La liaison se fait d'abord par le
  **numéro de texte** cité au CR (« (n° 525) »), joint aux numéros de tous
  les documents du dossier (`construire_index_numeros` — robuste aux
  renumérotations de la navette, et au **vote solennel** tenu quelques jours
  après le débat, fenêtre 14 j). ⚠️ La série des numéros **redémarre à chaque
  législature** : le garde-fou « un numéro → un seul dossier » s'applique donc à
  `(législature, numéro)`, et seuls les numéros de la législature **courante**
  sont exposés (les CR ingérés sont les siens). Sans cette clé, la collision
  entre le n° 959 de la 16e et celui de la 17e faisait jeter les deux dossiers —
  2 540 numéros sur 3 026 perdus, couverture 54/237 dossiers officiels.
  À défaut de numéro : **date de séance + recoupement du titre** (coefficient de
  recouvrement — labels courts du CR). Un candidat
  unique le jour J **ne suffit jamais** sans recoupement : plusieurs textes
  sont votés le même jour et l'archive ne capture pas toutes les séances
  (leçon d'un mauvais rattachement constaté en réel) ; cas ambigus écartés,
  §2.5. En revanche un même texte **rouvert plusieurs fois le même jour**
  (reprise de séance) est **fusionné** en un seul débat avant l'index
  (`fusionner_meme_texte`) : sans cela il se présentait comme deux candidats
  quasi identiques et la liaison était refusée pour ambiguïté — 31 faux positifs
  mesurés, zéro vraie collision. Chaque
  explication est **paraphrasée en une phrase par le LLM et validée**
  (`generer_desaccord` → `valider_argument`), **attribuée à son groupe** (§7.4,
  même gabarit pour tous) ; le **sens pour/contre vient du scrutin**, jamais du
  LLM. Aucune synthèse éditoriale (« qui a raison ») : on juxtapose les positions
  que les groupes formulent eux-mêmes. Source = le compte rendu officiel (§7.5).

  La validation d'un argument ajoute l'**ancrage lexical** aux contrôles communs
  (cf. plus bas) : mettre dans la bouche d'un groupe une opinion qu'il n'a pas
  exprimée est précisément ce que §7.4 interdit, et aucun contrôle de forme ne
  l'attrape. Pour que ce garde-fou — et les suivants — s'applique aussi au
  passé, l'**extrait de compte rendu** qui a produit chaque argument est
  conservé dans `dossier.desaccord_sources` (**colonne, hors `payload`** : le
  payload est le contrat d'API et serait servi tel quel). La Q2 se revalide donc
  hors ligne comme la Q1/Q4 depuis l'exposé ; un argument **sans source
  stockée est invérifiable**, donc effacé par `revalider` — 1 476 arguments
  (219 dossiers) l'ont été à l'introduction de l'ancrage, le run suivant les
  régénère.

  ⚠️ Seuls les groupes qui ont **pris la parole** ont un argument : mesuré sur
  la base de dev, la carte affichait en moyenne **6,4 groupes de moins** que le
  vote d'ancrage n'en documentait, et 26 dossiers montraient un sens unique
  alors que le vote était divisé. L'app le dit désormais explicitement
  (`QuestionsCard`) au lieu de laisser lire la liste comme le panorama de
  l'hémicycle, et le titre de la question ne parle de « désaccord » que s'il y a
  plusieurs sens de vote.
  L'**objet du vote d'ancrage** est conservé (`desaccord_objet`) et affiché
  au-dessus des positions : « pour » sur une motion de rejet préalable veut dire
  « pour le rejet du texte », l'inverse de ce que le seul mot laisserait croire
  (§7.4). Vote non reconnu par `libelleScrutin` côté app → ligne masquée (§2.5).
  **Pourquoi (Q1)** : généré depuis l'**exposé des motifs** (+ titre).
  **Changement (Q4)** : **deux sources, dans cet ordre** — le **dispositif
  officiel** du texte quand il existe (c'est un **fait** : réponse *sans*
  attribution, qui porte son `changement_source` vers le texte déposé, affiché
  en lien sous la réponse §7.5), sinon seulement l'**exposé**, et la réponse est
  alors obligatoirement préfixée « Selon l'auteur du texte » (point de vue du
  déposant, §4.3, au conditionnel). Une Q4 déjà en base tirée de l'exposé est
  **regénérée** dès qu'un dispositif devient disponible : le fait prime sur la
  parole du déposant.
  Les deux passent les **contrôles déterministes** (`valider_reponse`) : tout
  chiffre de la réponse doit exister dans la source, nature du texte non
  inversée (proposition↔projet), lexique évaluatif interdit, aucun caractère
  hors français (fuite CJK vue en épreuve), longueur bornée. **Exception
  `lexique_de_la_source_admis`** (dispositif de texte ou d'amendement, sources
  officielles) : un mot de la liste noire est admis **s'il figure tel quel dans
  la source** — on interdit au modèle d'**ajouter** un jugement, pas de reprendre
  les mots de la loi (cas réel : « l'exposition des jeunes utilisateurs aux
  contenus dangereux », écrit dans l'article unique d'une résolution, faisait
  rejeter une réponse pourtant fidèle). Rejet → réponse absente (§2.5), jamais
  publiée. Les réponses validées sont **persistées et réutilisées** entre runs
  (pas de rappel du modèle sur une source stable) — d'où
  `python -m app.ingestion.revalider`, à lancer quand un garde-fou est ajouté.

  Deux contrôles complètent la règle « le modèle reformule, il n'ajoute rien » :
  - **glose entre parenthèses** absente de la source → rejet. Un sigle ne se
    développe pas tout seul : sur l'amendement n° 7 du projet de loi agricole,
    le modèle écrivait « l'Anses (Agence nationale de sécurité du médicament et
    des produits de santé) » — développement absent de l'exposé, et qui est
    celui de l'**ANSM**, une autre agence. Comparaison mot à mot, accents et
    ponctuation neutralisés : « (à l'article 8) » passe si la source l'écrit.
  - **déposant requalifié** → rejet. `deposant()` (`normalize.py`) lit dans
    l'objet officiel qui a déposé — mention explicite (« du Gouvernement »,
    « présenté par le Gouvernement », « de M. X », « de la commission des
    lois ») et, **pour un vote sur le texte seulement**, la nature du texte
    (art. 39 : un *projet* émane du Gouvernement, une *proposition* d'un
    parlementaire). Sur un vote d'**amendement**, la nature du texte est
    ignorée : un député amende couramment un projet de loi. Deux indices
    contradictoires → `None`, aucun contrôle (§2.5). Le contrôle est
    **asymétrique** et ne s'applique qu'aux réponses **attribuées** (avec
    préfixe) : « le député » est rejeté quand la source dit « du
    Gouvernement », mais l'inverse est admis (l'exposé d'un amendement
    parlementaire mentionne légitimement le Gouvernement), et la Q1 non
    attribuée garde son amorce « Les députés ont examiné ce texte… ».
    Mesuré sur la base de dev : **175 réponses fautives** trouvées.
  - **ancrage lexical** (`ancrage_minimal`, **opt-in**) → rejet. Une part
    minimale des mots de contenu de la réponse doit se retrouver dans la source
    (comparaison sur racines tronquées, pour que « remboursement » retrouve
    « rembourser »). C'est le seul contrôle qui attrape une phrase **plausible
    et fabriquée** — sans chiffre inventé, sans mot évaluatif, sans parenthèse.
    Activé pour les seules **paraphrases d'explication de vote** (Q2, via
    `valider_argument`) : la Q1/Q4 travaillent sur des exposés longs dont le
    vocabulaire s'éloigne légitimement de la réponse, leur appliquer le même
    seuil sans campagne de mesure les invaliderait en masse. Seuil de départ
    **permissif** (`SEUIL_ANCRAGE_ARGUMENT`) : les sources étant désormais
    conservées, le resserrer ne coûte plus aucun appel au modèle.
    Mesuré sur la base de dev avant garde-fou : « le texte ne répond pas aux
    attentes des Français en matière de sécurité et d'immigration » servi tel
    quel sur trois dossiers sans rapport (dont un texte sur les honoraires
    d'expert-comptable), attribué à un groupe qui avait voté **pour**.
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
