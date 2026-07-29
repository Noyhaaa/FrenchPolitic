# Décrypté

**Le traducteur neutre et mobile des décisions du Parlement.**

Une application mobile qui répond en 30 secondes à une seule question, sans biais :
*« Sur quoi les parlementaires ont-ils voté, et qu'est-ce que le texte dit ? »* —
chaque affirmation reliée à une source officielle, aucune opinion produite.

> Spécification produit : [`MVP_Assemblee_Nationale_v2.md`](MVP_Assemblee_Nationale_v2.md) — fait foi sur le périmètre et la neutralité.
> Guide pour contribuer (conventions, architecture détaillée) : [`CLAUDE.md`](CLAUDE.md).
> Détail de l'ingestion et de l'API : [`backend/README.md`](backend/README.md).

---

## 1. Sur quoi on se base

Tout ce qu'affiche l'app vient de sources publiques officielles. Rien n'est saisi
à la main, rien n'est acheté, rien n'est déduit d'un agrégateur tiers.

| Source | Ce qu'on en tire |
|---|---|
| **Open data Assemblée nationale** — scrutins publics (17e législature) | Le vote lui-même : objet, date, résultat, ventilation par groupe, **nominatif** |
| **Archive AMO** (acteurs & organes) | L'annuaire des députés, leur groupe, leur circonscription, leur photo |
| **Archive « Dossiers législatifs »** | Le rattachement d'un vote à son **dossier**, le lien officiel, la **trajectoire** du texte dans les deux chambres, **où il en est aujourd'hui** (n° de la loi promulguée, JO, Légifrance), et **qui le porte** |
| **PDF des textes déposés** (AN, repli senat.fr) | L'**exposé des motifs** (parole de l'auteur) et le **dispositif** (les articles) |
| **Archive « amendements »** (AN) | Le contenu réel d'un amendement : article visé, dispositif, exposé sommaire |
| **Comptes rendus des débats** (« SyceronBrut ») | Les **explications de vote** des groupes en séance |
| **senat.fr** — pages de scrutin, JSON nominatif, annuaire | Les votes du Sénat, les sénateurs, leur groupe et leur commission |

**Ces données ne sont pas opposables.** Seuls les textes signés publiés au Journal
officiel font foi. C'est pourquoi chaque écran ramène à sa source en un tap (§7.5).

## 2. Les règles qui contraignent tout le reste

Ce ne sont pas des préférences de style : elles priment sur l'esthétique et sur la
complétude, et elles expliquent la plupart des choix techniques du dépôt.

1. **On ne comble jamais un trou** (§2.5). Donnée absente → le bloc **disparaît**,
   ou affiche « information non disponible ». Jamais une supposition, jamais une
   moyenne présentée comme un fait.
2. **Aucun jugement produit** (§4.3). Pas d'adjectif évaluatif dans les données ni
   dans les libellés. Ce qui est non neutre (exposé des motifs, exposé sommaire
   d'un amendement) est affiché en **bloc cité et attribué**, jamais fondu dans le
   texte neutre.
3. **Symétrie entre groupes** (§7.4). Même gabarit, même longueur pour tous.
4. **Un chiffre qui ne veut rien dire ne s'affiche pas.** Deux refus assumés :
   pas de **taux de participation** (l'open data ne recense que les votants d'un
   scrutin public — un ratio se lirait comme un score d'absentéisme que la source
   ne soutient pas), et **jamais de « contre son groupe » au Sénat** (les bulletins
   d'un scrutin public ordinaire y sont déposés par un délégué pour tout le groupe :
   le chiffre existerait, il serait un artefact de procédure).
5. **Réversibilité** (§7.5). La source brute est à un tap.
6. **Jamais la couleur seule** pour porter un statut (RGAA) : icône + libellé.
7. **Langue simple** (§8). Le jargon de procédure est expliqué par le glossaire,
   source unique pour ses deux surfaces (les écrans dédiés et l'aide en ligne).

## 3. Comment ça marche

```
Sources officielles          Ingestion (Python)              PostgreSQL        API              App
──────────────────           ──────────────────              ──────────        ───              ───
scrutins AN + Sénat   ─┐     parse → contrôle                dossier       ┐
dossiers législatifs   ├──▶  regroupement PAR DOSSIER    ──▶ scrutin       ├─▶ FastAPI  ──▶  Expo / RN
PDF des textes         │     enrichissement (exposé,         depute        │   (lecture)      + cache
amendements, débats    │      dispositif, amendements)       vote_depute   │                   offline
annuaires AMO/Sénat   ─┘     résumé + questions              groupe        ┘
```

**L'unité centrale est le dossier** (un texte de loi), pas le scrutin. Un dossier
agrège **tous** ses votes successifs — ceux de l'Assemblée **et** ceux du Sénat —,
ses amendements, son résumé et sa trajectoire. Un texte en navette ne se dédouble
donc pas dans le fil.

Le travail difficile de l'ingestion est le **rattachement** : un vote dit « sur
l'ensemble de la proposition de loi visant à… », rarement à quel dossier il
appartient. La chaîne essaie, dans cet ordre : le `dossierRef` officiel → le titre
cité comparé aux titres de l'archive (exact, puis par signature tolérante aux
apostrophes et coquilles) → un dossier reconstitué à identifiant stable → sinon un
**événement autonome** (motion de censure, déclaration). Un titre qui désigne deux
dossiers possibles n'est **jamais** tranché au hasard : la table s'abstient.

Le **résumé neutre est écrit par un gabarit déterministe**, pas par un LLM :
5 phrases ancrées sur les faits du scrutin, chacune portant sa source.

### Ce que le LLM fait — et ne fait pas

Un LLM (Ollama, en local réseau) n'intervient que sur des tâches **vérifiables
après coup**, et chacune de ses sorties passe des contrôles déterministes avant
d'entrer en base : chiffres présents dans la source, nature du texte non inversée,
lexique évaluatif, sigle non développé de son propre chef, déposant non
requalifié, et — pour les paraphrases de débat — **ancrage lexical** dans la phrase
réellement prononcée. Rejet → « information non disponible ».

| Il fait | Il ne fait jamais |
|---|---|
| Classer un thème dans une **liste fermée** | Écrire le résumé neutre |
| Nommer les **publics concernés** (liste fermée de 19) | Dire qui a raison |
| Reformuler « pourquoi ce texte ? » (Q1) et « qu'est-ce que ça change ? » (Q4) depuis une source unique | Ajouter un fait, un chiffre ou une glose absents de la source |
| Paraphraser l'explication de vote d'un groupe (Q2) | Décider du sens d'un vote — il vient du scrutin |

« Quel est le résultat ? » (Q3) n'est pas généré du tout : il est composé
arithmétiquement depuis le vote décisif.

## 4. Ce que l'app montre

- **Accueil** façon Netflix : un texte à la une, les rangées Aujourd'hui / Hier
  (masquées si vides), la rangée **« Les votes les plus disputés »** — classée par
  arithmétique pure sur les décomptes officiels (écart de voix, abstention,
  fracture entre groupes), jamais par un jugement sur la mesure —, le récap du
  dernier mois actif, puis une rangée par thème. Un dossier qui reçoit un nouveau
  vote porte un badge **« mis à jour »**, descriptif et jamais évaluatif.
- **Fiche dossier** : **qui porte le texte** (le Gouvernement, le parlementaire
  auteur — cliquable vers sa fiche —, ou le Sénat), la frise **« Trajectoire au
  Parlement »** (les deux chambres, chaque étape de jargon ouvrant sa
  définition) close par **« Où en est le texte ? »** — « C'est la loi » avec son
  numéro et son lien Légifrance, ou la dernière étape enregistrée, **jamais
  l'étape suivante**, qui serait une prédiction —, le résumé, **le vote en
  4 questions**, puis trois sections — les
  votes sur le texte avec le **vote décisif** mis en avant, les **amendements**,
  les **sous-amendements**. L'exposé des motifs y est cité et attribué.
- **Fiche vote** : le résultat en tête, puis le **vote par groupe** avec la ligne
  de fracture et les **noms des votants** dépliables (chaque nom ouvre la fiche du
  parlementaire s'il siège encore). Sur un vote d'amendement, sa carte « en 4
  questions » et son contenu réel remplacent la ventilation par groupe.
- **Explorer** : quatre portes d'entrée et les catégories — un écran de
  découverte, qui **ouvre** l'écran de résultats au lieu de l'afficher sur place.
- **Dossiers** : les résultats en chronologie dense. La recherche est
  multi-termes et porte aussi sur les **réponses citoyennes** et les **publics
  concernés** — c'est là qu'est le vocabulaire du lecteur (« logement »,
  « hôpital »), pas dans les titres officiels.
- **Glossaire** : un mot du jour, l'index par lettre, et sur chaque fiche les
  **dossiers où le mot apparaît** — une définition ne doit pas être un cul-de-sac.
- **Annuaire et fiche parlementaire** (les deux chambres) : identité, **portrait
  de vote** sur 12 mois glissants, et historique paginé filtrable.

Le tout avec cache hors-ligne, pull-to-refresh, et les états chargement / erreur /
hors-ligne sur chaque écran.

## 5. État actuel

**Fait.** L'app V1 est branchée sur l'API. L'ingestion réelle tourne de bout en
bout sur les deux chambres, avec le rattachement par dossier, l'enrichissement des
amendements, les questions citoyennes et la trajectoire.

Mesuré sur la base de développement au **29 juillet 2026** (dernier run complet) :

| | |
|---|---|
| Dossiers | **328** — dont 255 rattachés à leur dossier officiel, 44 reconstitués, 26 événements autonomes, 3 d'origine sénatoriale |
| Scrutins | **8 433** Assemblée + **340** Sénat |
| Parlementaires | **925** (577 députés + 348 sénateurs), **1,39 M** de votes nominatifs |
| Trajectoire au Parlement | 262 / 328 dossiers |
| Où en est le texte (état actuel) | **254 / 328** — 96 promulgués · 126 en navette · 21 résolutions · 7 au Conseil constitutionnel · 4 retirés |
| Initiative (qui porte le texte) | **242 / 255 dossiers officiels** — 49 Gouvernement · 124 parlementaires (110 nommés) · 69 Sénat |
| Accroche (le but du texte en une phrase) | 241 / 328 |
| Exposé des motifs | 242 / 328 · dispositif : 176 |
| Q2 « principal désaccord » (depuis les débats) | 211 / 328 |
| Amendements AN enrichis de leur contenu | **6 042 / 7 221 (83,7 %)** |
| Sénateurs avec commission permanente | 346 / 348 |

Ces trous sont **documentés, pas masqués** : chaque bloc sans source disparaît de
l'écran plutôt que d'afficher une approximation.

**Limites connues, avec leur cause.** 44 dossiers restent reconstitués : 32 dont le
titre est réellement absent de l'archive (dont des coquilles de la source), 12 que
l'archive contient mais qu'un garde-fou d'ambiguïté écarte — le même titre existe
dans deux législatures, donc on s'abstient. Le début de mandat d'un sénateur est
absent parce que l'annuaire du Sénat **ne le publie pas** (vérifié à la source), et
la commission d'un député parce que l'archive AMO demande un travail de résolution
non fait. Ce ne sont pas des oublis : ils sont inscrits dans le code, à l'endroit
où quelqu'un se poserait la question.

**En cours / à venir.** Les comptes rendus du Sénat (pour que la Q2 existe aussi
sur un dossier purement sénatorial), l'enrichissement des amendements du Sénat,
Légifrance pour le texte consolidé, et la planification du job de synchro. Les
filtres de recherche et le partage sont en V1.1 ; l'assistant IA en questions
pré-cadrées est en V2.

## 6. Démarrer

**Backend** (PostgreSQL requis) :

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Python 3.12
pip install -r requirements.txt
createdb frenchpolitics
cp .env.example .env                                # puis renseigner DATABASE_URL
python -m app.db.migrations                         # colonnes ajoutées au modèle
python -m app.ingestion.run --limit 300             # ingère les 300 scrutins récents
uvicorn app.main:app --reload                       # http://localhost:8000/docs
```

Sans ingestion, l'API sert des **données seed fictives** (`REPOSITORY_BACKEND=memory`) :
suffisant pour lancer l'app, mais ce ne sont pas des votes réels.

⚠️ Piège le plus fréquent : lancer une commande backend **sans activer le venv**.

Commandes utiles (détaillées dans [`backend/README.md`](backend/README.md)) :

```bash
python -m app.ingestion.senat --limit 40   # sénateurs + scrutins du Sénat seuls (~10 s)
python -m app.ingestion.deputes            # annuaire + votes nominatifs seuls
python -m app.ingestion.revalider          # repasse les garde-fous sur les réponses en base
python -m app.ingestion.divisions          # recalcule l'indice des « votes disputés »
python -m app.ingestion.initiatives        # renseigne « qui porte le texte » en base
python -m app.ingestion.etats              # renseigne « où en est le texte » + source Légifrance
pytest                                     # suite de tests
```

**Application mobile** (dans un autre terminal, à la racine) :

```bash
npm install
npm run ios         # ou : npm run android / npm start
npx tsc --noEmit    # vérification de types — à lancer avant de conclure
```

En dev, l'app découvre l'API via l'hôte Metro ; surchargeable avec
`EXPO_PUBLIC_API_URL`. Le backend doit tourner pour le premier chargement, ensuite
le cache prend le relais hors-ligne.

## 7. Hors périmètre (V1)

Notifications push, suivi de député, comparateur, assistant à champ libre,
prédiction d'impact. Le suivi de dossier (badge « mis à jour ») a en revanche été
**intégré en V1**, comme levée assumée d'un verrou de la spec.
