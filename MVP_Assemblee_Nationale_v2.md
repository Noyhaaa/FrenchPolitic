# MVP — Application mobile pour comprendre les votes de l'Assemblée nationale

*Version 2 — spécification resserrée, priorisée et « anti-hallucination »*

---

## 0. Résumé exécutif (à lire en premier)

**Le pari.** Aujourd'hui, comprendre ce que l'Assemblée a voté demande de croiser le
site de l'Assemblée, Légifrance et la presse. On propose une application mobile qui
répond en **30 secondes** à une seule question, sans biais : *« Sur quoi les députés
ont-ils voté, et qu'est-ce que le texte dit ? »*

**La différence avec l'existant.** NosDéputés.fr, Datan.fr et CIVIX exposent déjà ces
données. Notre valeur n'est pas la donnée, c'est **la couche d'explication
pédagogique**, mobile, avec un résumé neutre **systématiquement relié aux sources
officielles**. Le produit à construire n'est pas « un site de plus », c'est le
traducteur grand public de ces données.

**Le cœur du MVP (V1), et rien d'autre :**
1. Un **fil des derniers scrutins publics**.
2. Une **fiche scrutin** : titre clair + résumé neutre sourcé + résultat par groupe
   politique + liens vers les sources officielles.
3. Une **recherche simple** par mots-clés.

**Ce qu'on coupe volontairement de la V1** (pour tester vite le cœur de valeur) :
assistant IA conversationnel, fiche député complète, tableau « avant/après »
automatique, détail des amendements. Tout cela arrive en V1.1 / V2 — voir §2.

**Le risque n°1 n'est pas technique, il est éditorial :** un résumé IA biaisé ou
inventé détruit la confiance et donc le produit. La moitié de l'effort de conception
porte là-dessus (§4).

---

## 1. Vision & problème

### 1.1 Le problème (job-to-be-done)

> « Quand j'entends parler d'un vote à l'Assemblée, je veux comprendre en une minute
> **de quoi il s'agit et ce que ça implique concrètement**, sans avoir à lire un texte
> juridique ni un article d'opinion. »

Le besoin n'est pas *plus de données* (elles existent, elles sont ouvertes), c'est
*moins d'effort de compréhension* et *une garantie de neutralité*.

### 1.2 Persona cible (on conçoit pour une seule personne d'abord)

**« Léa, citoyenne curieuse mais pas experte »** — 25-45 ans, suit l'actualité de loin,
n'a ni le temps ni le vocabulaire pour lire un projet de loi. Veut se forger un avis
par elle-même à partir de faits, pas se faire dire quoi penser.

**Anti-persona (on ne conçoit PAS pour eux en V1) :** journaliste politique, assistant
parlementaire, chercheur en sciences politiques. Ils ont déjà NosDéputés/Datan et
veulent de la donnée brute exhaustive — un autre produit.

### 1.3 Positionnement vs. l'existant

| Acteur | Ce qu'il fait | Ce qu'il ne fait pas (notre ouverture) |
|---|---|---|
| Site Assemblée nationale | Source officielle exhaustive | Illisible pour un non-initié |
| NosDéputés.fr | Suivi de l'activité des députés | Pas d'explication vulgarisée, orienté « data » |
| Datan.fr | Statistiques de vote, cohésion des groupes | Analytique, pas pédagogique/mobile |
| CIVIX | Restructuration neutre des données en CSV/API | Brique de données, pas une app grand public |

**Notre créneau :** le « **dernier kilomètre** » — transformer la donnée officielle en
compréhension, sur mobile, en 30 secondes, avec sources cliquables.

### 1.4 Proposition de valeur

> **Le traducteur neutre et mobile des décisions de l'Assemblée.**
> Chaque affirmation renvoie à une source officielle. Aucune opinion produite.

---

## 2. Périmètre du MVP (la section la plus importante)

### 2.1 Principe de découpage

Un MVP n'est pas « une petite version du produit final », c'est **le plus petit
parcours qui délivre la valeur centrale et qu'on peut mettre entre les mains
d'utilisateurs pour apprendre**. On coupe tout ce qui :
- est risqué pour la neutralité sans surveillance humaine (assistant libre, prédiction
  d'impact) ;
- ajoute de l'effort sans tester une nouvelle hypothèse de valeur.

### 2.2 ✅ Dans le MVP (V1) — le « parcours en or »

1. **Fil des scrutins publics** (accueil).
2. **Fiche scrutin** avec résumé neutre sourcé + résultat par groupe + liens sources.
3. **Recherche par mots-clés** (titre du texte, thème).

C'est tout. Ce parcours suffit à valider les deux hypothèses centrales :
**(H1)** les gens comprennent réellement grâce au résumé ; **(H2)** ils font confiance
parce que tout est sourcé.

### 2.3 🔜 Juste après (V1.1 puis V2), une fois le cœur validé

- **V1.1** : fiche député (lecture seule : circonscription, groupe, votes récents),
  filtres de recherche (par groupe/thème), partage d'une fiche.
- **V2** : bloc « **Ce que dit le texte** » structuré (voir §4.5, remplace le
  « avant/après »), détail des amendements clés, assistant IA en **questions
  pré-cadrées** (pas de champ libre au début).

### 2.4 ❌ Hors périmètre (assumé, à documenter pour ne pas y revenir)

Notifications, suivre un député/thème, comparateur de partis, timeline législative,
« vote de mon député » géolocalisé, assistant conversationnel à champ libre, prédiction
d'impact d'une loi.

### 2.5 Règle d'or de neutralité qui contraint tout le périmètre

> **On n'affiche jamais une phrase qui ne peut pas être rattachée à une source
> officielle.** Si la donnée manque, on affiche « information non disponible », jamais
> une supposition.

---

## 3. Spécifications fonctionnelles du cœur

### 3.1 Écran 1 — Fil des scrutins

Liste des derniers scrutins publics, du plus récent au plus ancien.

Chaque carte affiche :
- **Titre reformulé en langage clair** (le titre officiel est souvent opaque).
- **Statut** : `Adopté` / `Rejeté` / `En cours de navette` (badge couleur + libellé
  texte pour l'accessibilité — jamais la couleur seule).
- **Date** du scrutin.
- **Thème** (1 pastille : Logement, Santé, Fiscalité…).
- **Micro-résultat** : « 312 pour · 220 contre ».
- **Temps de lecture estimé** (~30 s).

Contraintes UX : chargement instantané (données en cache), *pull-to-refresh*, état vide
et état hors-ligne gérés explicitement.

### 3.2 Écran 2 — Fiche scrutin (le cœur du produit)

Structure verticale, du plus synthétique au plus détaillé (l'utilisateur peut
s'arrêter quand il a compris) :

1. **Titre clair + statut + date.**
2. **Résumé neutre** (≈ 4-6 phrases, format imposé — voir §4). Chaque affirmation
   sensible porte un renvoi source `[1]`.
3. **De quoi parle ce texte ?** — contexte factuel court (« ce texte modifie le code
   de… », « il fait suite à… »), uniquement si la source le documente.
4. **Résultat global** : Pour / Contre / Abstention / Non-votants, en chiffres + barre.
5. **Vote par groupe politique** : pour chaque groupe, position majoritaire + décompte
   (une ligne lisible, pas un tableau dense). Indiquer le taux de cohésion si dispo.
6. **Qui est concerné ?** — puces factuelles seulement si présentes dans l'exposé des
   motifs (particuliers, entreprises, collectivités…). Sinon, masquer le bloc.
7. **Sources officielles** (obligatoire, toujours en bas) : lien vers le texte
   (Légifrance/dossier législatif), le scrutin (Assemblée), les débats, les amendements.

> Note importante : **beaucoup de votes se font à main levée et n'ont aucune trace
> nominative**. La fiche « vote par groupe » n'existe que pour les **scrutins publics**.
> Pour les autres, on affiche le résultat global sans ventilation, et on l'explique.

### 3.3 Écran 3 — Recherche simple

Un champ, une recherche plein texte sur le titre reformulé + titre officiel + thème.
Pas de filtres avancés en V1 (ils viennent en V1.1). Résultats = mêmes cartes que le
fil.

---

## 4. Le résumé IA : spécification et garde-fous *(section critique)*

C'est ici que le produit gagne ou meurt. Un résumé « joliment écrit » mais inexact ou
orienté est pire que pas de résumé.

### 4.1 Principe : génération **ancrée**, jamais « libre »

Le modèle ne « connaît » rien : il **reformule uniquement** un contexte qu'on lui
fournit (RAG). Pipeline :
1. Récupérer les documents officiels du scrutin (titre, exposé des motifs, texte,
   résultat, éventuellement débats).
2. Les découper et les fournir au modèle **comme seule source autorisée**.
3. Demander un résumé **avec citation obligatoire** de la source de chaque affirmation.
4. **Vérifier** que chaque phrase du résumé est étayée par un passage source (voir 4.4).

### 4.2 Format de sortie imposé (structuré, pas de prose libre)

On force le modèle à répondre en JSON structuré, ensuite mis en forme par l'app :

```json
{
  "titre_clair": "…",
  "resume": [
    { "phrase": "…", "source_id": "expose_motifs" },
    { "phrase": "…", "source_id": "texte_article_2" }
  ],
  "objet": "…",
  "public_concerne": ["…"],
  "confiance": "haute | moyenne | faible",
  "champs_non_documentes": ["public_concerne"]
}
```

Un format contraint réduit drastiquement la place laissée à l'interprétation et rend le
contrôle automatisable.

### 4.3 Règles anti-biais (dans le prompt système + en revue)

- **Décrire, ne pas juger.** Interdiction des adjectifs évaluatifs (« ambitieux »,
  « insuffisant », « controversé ») et des verbes d'intention prêtés aux acteurs.
- **Attribuer, ne pas trancher.** « Le groupe X a voté contre » ✅ ; « le groupe X
  s'oppose au progrès social » ❌.
- **Pas de prédiction d'impact.** On décrit ce que le texte prévoit, pas ce qu'il
  « va provoquer ».
- **Symétrie.** Si on cite un argument « pour » tiré des débats, on cite un argument
  « contre » de même longueur, ou aucun des deux.
- **En cas de doute ou de source manquante → champ vide + mention explicite**, jamais de
  comblement.

### 4.4 Garde-fous automatiques (avant affichage)

- **Vérification d'ancrage** : chaque `phrase` doit correspondre à un passage source
  (score de similarité minimal). Sinon, phrase rejetée.
- **Détecteur de lexique orienté** : liste noire d'adjectifs/tournures évaluatives qui
  bloque la publication.
- **Cohérence des chiffres** : les décomptes du résumé doivent être identiques aux
  données de scrutin (contrôle strict, pas de tolérance).
- **Score de confiance** : si « faible », le résumé passe en file de **revue humaine**
  et n'est pas publié automatiquement.

### 4.5 « Ce que dit le texte » plutôt que « avant / après »

Le tableau « avant/après » du MVP initial est un **piège** : il demande d'interpréter
l'état du droit avant et l'effet après, ce qui est risqué à automatiser et facilement
biaisé. On le remplace (en V2) par un bloc factuel **« Ce que prévoit le texte »** :
liste des dispositions telles qu'écrites, chacune sourcée à un article. Descriptif, pas
comparatif ni prédictif.

### 4.6 Revue humaine — indispensable au démarrage

Au lancement, **aucun résumé n'est publié sans validation humaine** (au moins pour les
scrutins solennels et les textes sensibles). C'est lent, mais c'est le seul moyen de
gagner la confiance initiale. On automatise progressivement à mesure que les garde-fous
prouvent leur fiabilité (mesure : taux de résumés validés sans correction).

---

## 5. Données : la réalité du terrain

### 5.1 Sources et ce qu'elles contiennent vraiment

| Source | Contenu utile | Format / accès |
|---|---|---|
| **Open data Assemblée nationale** | Scrutins & votes nominatifs (scrutins publics), amendements, comptes rendus des débats, acteurs (députés), dossiers législatifs | XML/JSON, Licence ouverte, téléchargement de jeux complets |
| **API Légifrance (via PISTE)** | Texte consolidé des lois, JO, dossiers | REST, OAuth2 (Client Credentials), gratuit après inscription |
| **(optionnel) CIVIX / NosDéputés / Datan** | Données déjà restructurées, stats de cohésion | CSV / API — utile comme raccourci ou pour recouper |

### 5.2 Contraintes clés à intégrer dès le départ

- **Scrutins publics uniquement pour le nominatif.** Les votes à main levée n'ont pas de
  ventilation par député/groupe. Le produit se construit autour des scrutins publics.
- **Données non opposables.** L'API Légifrance le rappelle : seuls les PDF signés du JO
  font foi. À afficher dans les mentions légales.
- **Fiabilité non garantie** côté API : prévoir des contrôles de cohérence et un
  mécanisme de signalement d'anomalie.
- **Fréquence de mise à jour** : les jeux open data ne sont pas temps réel. Définir une
  synchronisation périodique (ex. plusieurs fois par jour) et afficher la date de
  dernière synchro.
- **Législature courante (17e)** : cadrer le MVP sur la législature en cours ; les
  archives (15e, etc.) sont hors périmètre initial.

### 5.3 Modèle de données (entités principales)

```
Scrutin      (id, date, titre_officiel, titre_clair, statut, dossier_id, type)
Dossier      (id, titre, theme, url_legifrance)
Vote         (scrutin_id, depute_id, position)          # pour, contre, abstention, non-votant
Depute       (id, nom, circonscription, groupe_id)
Groupe       (id, nom, couleur)
PositionGrp  (scrutin_id, groupe_id, position_majoritaire, pour, contre, abst, cohesion)
Amendement   (id, dossier_id, auteur_id, objet, sort)   # V2
Resume       (scrutin_id, json_structuré, confiance, statut_revue, date_generation)
Source       (scrutin_id, type, url)                    # texte, scrutin, débats, amendements
```

---

## 6. Architecture technique

On conserve la stack proposée (elle est cohérente), avec quelques ajouts.

```
[Sources officielles]        [Ingestion / ETL]         [Stockage]
 AN Open Data  ─┐                                        PostgreSQL
 Légifrance API ├──►  Jobs planifiés (sync périodique) ──►  + pgvector (embeddings pour le RAG)
                │     nettoyage, normalisation, dédup      + cache résumés
                └──►  file d'attente de génération résumé ─┘
                                    │
                                    ▼
                        [Génération IA + garde-fous]
                     RAG (contexte officiel) → LLM → validation
                     ancrage / lexique / chiffres → file de revue humaine
                                    │
                                    ▼
                            [API REST — FastAPI]
                     /scrutins  /scrutins/{id}  /recherche
                                    │
                                    ▼
                            [App mobile — Flutter]
                        Fil · Fiche · Recherche · cache offline
```

**Choix & justifications :**
- **Flutter** : un seul code iOS/Android, adapté à une petite équipe. ✅ conservé.
- **FastAPI + PostgreSQL** : ✅ conservés. Ajouter **pgvector** pour stocker les
  embeddings et éviter une base vectorielle séparée en MVP.
- **Génération des résumés en asynchrone** (file d'attente), pas à la volée : un résumé
  se calcule **une fois par scrutin**, se met en cache, et se sert instantanément à tous.
  C'est essentiel pour le coût et la latence.
- **IA** : le choix du fournisseur importe moins que **l'architecture RAG + garde-fous**.
  Rester capable de changer de modèle (abstraction derrière une interface).

**Coûts IA — à cadrer tôt :** comme chaque résumé est généré une seule fois et mis en
cache, le coût est proportionnel au **nombre de scrutins**, pas au nombre
d'utilisateurs. C'est un modèle économiquement sain. Estimer : (nb scrutins/mois) ×
(coût par génération + revue). Prévoir un budget de régénération quand un texte évolue.

---

## 7. Charte éditoriale & neutralité (principes opérationnels)

Les « principes » du MVP initial (neutralité, transparence…) sont justes mais abstraits.
On les rend **opérationnels** :

1. **Traçabilité totale** — toute affirmation affichée pointe vers une source officielle.
2. **Faits séparés du contexte** — les données de vote (factuelles) ne se mélangent
   jamais visuellement avec le résumé (reformulé).
3. **Aucune opinion produite** — le produit décrit, il ne recommande pas, il ne note
   pas, il ne classe pas les députés en « bons/mauvais ».
4. **Symétrie de traitement** entre groupes politiques (même gabarit, même longueur).
5. **Réversibilité** — l'utilisateur peut toujours atteindre la source brute en 1 tap et
   se faire son propre avis.
6. **Transparence sur l'IA** — mention claire « résumé généré automatiquement à partir
   des sources officielles, [relu par un humain] » + bouton « signaler une erreur ».

---

## 8. Exigences non-fonctionnelles

- **Accessibilité (RGAA)** : contraste suffisant, statut jamais porté par la seule
  couleur, compatibilité lecteur d'écran, tailles de police dynamiques. C'est une app
  civique : l'accessibilité est un impératif, pas un bonus.
- **Langue simple** : viser un niveau de lecture « grand public » (phrases courtes,
  éviter le jargon ; expliquer un terme technique au premier usage).
- **Performance** : fil et fiche servis depuis le cache < 1 s ; l'app reste utilisable
  **hors-ligne** sur les contenus déjà consultés.
- **RGPD** : aucune donnée personnelle utilisateur nécessaire en V1 (pas de compte).
  Les votes des députés sont publics — pas de sujet côté personnes concernées, mais
  citer la source et la licence. Analytics anonymisées uniquement.
- **Mentions légales** : préciser que les résumés sont indicatifs et que seules les
  sources officielles (JO signé) font foi.
- **Observabilité** : journaliser les régénérations, les rejets de garde-fous, les
  signalements d'erreur — ce sont les métriques de qualité éditoriale.

---

## 9. Mesure du succès (KPIs du MVP)

On ne mesure pas « des features livrées » mais « la valeur validée ».

**Compréhension (H1)**
- % d'utilisateurs qui répondent « oui, j'ai compris » (micro-sondage 1 tap en fin de
  fiche).
- Temps de lecture réel vs. cible 30 s.

**Confiance (H2)**
- Taux de clic vers au moins une source officielle.
- Nombre de signalements d'erreur / 100 résumés (à faire baisser).

**Qualité éditoriale (interne)**
- % de résumés validés **sans correction** en revue humaine (mesure la maturité des
  garde-fous → conditionne l'automatisation).
- % de scrutins avec au moins un garde-fou déclenché.

**Engagement**
- Rétention J1 / J7, nombre de fiches consultées par session.
- Coût IA moyen par scrutin publié.

Seuils de décision (« go/no-go » pour investir dans la V2) à fixer avant le lancement,
p. ex. : « ≥ 70 % de "j'ai compris" ET < 2 signalements pour 100 résumés ».

---

## 10. Roadmap réaliste (phasée)

Le planning « 3 semaines » du MVP initial n'est pas atteignable pour ce périmètre : il
mélangeait ingestion, base, API, génération IA **et** une app Flutter complète à 4
écrans. Voici un découpage honnête, orienté « livrer le cœur d'abord ». Les durées
supposent une petite équipe ; en solo, compter plutôt le haut de la fourchette.

**Phase 0 — Cadrage (quelques jours)**
Choisir le persona, figer le périmètre V1, écrire la charte éditoriale, obtenir les accès
(inscription PISTE pour Légifrance).

**Phase 1 — Fondations données (~1-2 sem.)**
Ingestion des scrutins publics + dossiers, schéma PostgreSQL, job de synchronisation,
contrôles de cohérence, une API `/scrutins` minimale. *Livrable testable :* on peut
lister et consulter des scrutins bruts.

**Phase 2 — Cœur lisible (~2-3 sem.)**
Pipeline RAG + génération de résumé structuré + garde-fous + file de revue humaine.
Reformulation des titres. *Livrable :* fiches scrutin avec résumé neutre sourcé, servies
par l'API.

**Phase 3 — Application (~2-3 sem.)**
Flutter : Fil, Fiche scrutin, Recherche simple, cache offline, états vides/hors-ligne,
accessibilité de base, bouton « signaler une erreur ».

**Phase 4 — Boucle de test (~1-2 sem.)**
Mise en main de 10-20 utilisateurs cibles, micro-sondages, mesure des KPIs, corrections.
*Décision go/no-go V1.1.*

> En clair : le **cœur du MVP** est réaliste en ~6-10 semaines pour une petite équipe, à
> condition de tenir le périmètre. Chaque phase produit quelque chose de testable — on
> n'attend pas la fin pour apprendre.

---

## 11. Risques & mitigations

| Risque | Impact | Mitigation |
|---|---|---|
| Résumé IA biaisé ou inventé | Perte de confiance = mort du produit | Garde-fous §4 + revue humaine + sourcing obligatoire |
| Votes à main levée sans nominatif | Fiches incomplètes, incompréhension | Cadrer sur scrutins publics, expliquer l'absence de ventilation |
| Données open data non temps réel / anomalies | Info périmée ou fausse | Synchro périodique + date de synchro affichée + signalement d'anomalie |
| Périmètre qui gonfle (assistant, député, avant/après) | On ne livre jamais | Périmètre V1 verrouillé (§2), reste en backlog daté |
| Perception « app militante » | Rejet, polémiques | Charte de neutralité opérationnelle + symétrie stricte + transparence IA |
| Coûts IA | Modèle non viable | Génération 1×/scrutin mise en cache (coût ∝ scrutins, pas utilisateurs) |
| Espace déjà occupé (NosDéputés, Datan, CIVIX) | Faible différenciation | Se concentrer sur le « dernier kilomètre » pédagogique + mobile |

---

## 12. Décisions à trancher (questions ouvertes)

1. **Nom & identité** de l'app (le MVP initial n'en a pas).
2. **Niveau de revue humaine** au lancement : tous les résumés, ou seulement les
   scrutins solennels / textes sensibles ?
3. **Fournisseur IA** et politique de repli (multi-modèles ?).
4. **Périmètre temporel** : uniquement la 17e législature, ou intégrer un historique ?
5. **Réutiliser CIVIX/NosDéputés** comme raccourci de données, ou tout ingérer soi-même
   depuis l'open data brut (plus de contrôle, plus d'effort) ?
6. **Seuils go/no-go** chiffrés pour déclencher la V1.1.

---

## Vision long terme (inchangée, et solide)

Le « **Duolingo de la démocratie** » : une app qui explique lois, débats et votes de
façon claire, neutre et accessible, en renvoyant toujours vers les sources officielles.
Le MVP ci-dessus est la première marche : **prouver qu'on peut faire comprendre un vote
en 30 secondes sans trahir les faits.** Tout le reste (notifications, suivi, pédagogie
gamifiée) s'y greffe seulement une fois cette promesse tenue.
