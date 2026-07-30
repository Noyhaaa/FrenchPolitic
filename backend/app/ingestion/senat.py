"""Ingestion des scrutins publics du Sénat (pendant de `assemblee`).

Le Sénat ne publie pas d'archive de scrutins comparable à celle de l'Assemblée.
Il expose en revanche, par scrutin, deux ressources jointes :

- `scrutin-public/{session}/scr{session}-{n}.html` — l'objet du vote, la date de
  séance, le sort, le résultat global, l'analyse par groupe et le lien vers le
  dossier législatif ;
- `scrutin-public/{session}/scr{session}-{n}.json` — le **vote nominatif**, une
  ligne par matricule.

⚠️ `{session}` est l'année de **début de session** (octobre → septembre), pas
l'année civile : le scrutin n° 340 de la session « 2025 » a eu lieu le 21 juillet
2026. C'est le piège de ces URLs, au même titre que les zéros de tête côté AN.

Le rattachement au dossier suit la même cascade que côté Assemblée
(`parse_scrutin`), pour qu'un texte examiné dans les deux chambres se retrouve
dans **un seul** dossier :

1. la jointure officielle `senatChemin` de l'archive AN (voie directe) ;
2. le lien vers le dossier AN cité par la page dossier du Sénat (voie inverse,
   résolue par l'appelant, qui seul a le droit de faire du réseau) ;
3. la réconciliation par **titre** — les objets de vote du Sénat citent leur
   texte exactement comme ceux de l'AN, la machinerie existante s'applique ;
4. à défaut, un dossier d'origine sénatoriale, à identifiant stable `SEN-{slug}`
   (le slug du Sénat est stable, contrairement aux titres) ;
5. à défaut de tout, le scrutin est son propre dossier (événement autonome).

Les objets de vote du Sénat sont structurellement identiques à ceux de l'AN, au
préfixe « sur » près (« sur l'ensemble du projet de loi… »). On le retire à
l'entrée : tout l'aval (classement amendement/texte, vote décisif, rattachement
par titre) fonctionne alors sans adaptation.
"""
from __future__ import annotations

import asyncio
import html
import re
from dataclasses import dataclass, field

import httpx

from app.domain.enums import Chambre, PositionVote
from app.ingestion.assemblee import ScrutinParse
from app.ingestion.dossiers_legislatifs import (
    JointureSenat,
    Reconciliation,
    slug_dossier_senat,
)
from app.ingestion.normalize import (
    guess_theme,
    texte_de_rattachement,
    truncate,
    type_motion,
)
from app.ingestion.senateurs import (
    InfoSenateur,
    couleur_groupe,
    id_groupe_senat,
    id_senateur,
)
from app.schemas import (
    PositionGroupe,
    ResultatGlobal,
    Scrutin,
    SourceOfficielle,
    Votant,
)

BASE = "https://www.senat.fr"
URL_INDEX_SESSION = BASE + "/scrutin-public/scr{session}.html"
URL_SCRUTIN = BASE + "/scrutin-public/{session}/scr{session}-{numero}.html"
URL_SCRUTIN_JSON = BASE + "/scrutin-public/{session}/scr{session}-{numero}.json"
URL_DOSSIER = BASE + "/dossier-legislatif/{slug}.html"
URL_SENATEURS = BASE + "/api-senat/senateurs.json"
# Texte déposé au Sénat (exposé des motifs + dispositif) : le slug du dossier
# EST la référence du texte (« pjl25-689 » → « /leg/pjl25-689.pdf »).
URL_TEXTE_PDF = BASE + "/leg/{slug}.pdf"

# La session parlementaire s'ouvre en octobre : d'octobre à décembre, la session
# porte l'année civile ; de janvier à septembre, celle de l'année précédente.
_PREMIER_MOIS_SESSION = 10

_MOIS = {
    "janvier": 1, "février": 2, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5,
    "juin": 6, "juillet": 7, "août": 8, "aout": 8, "septembre": 9,
    "octobre": 10, "novembre": 11, "décembre": 12, "decembre": 12,
}

# --- Repères de la page d'un scrutin -------------------------------------
_RE_TITRE = re.compile(r'<h1 class="page-title">(.*?)</h1>', re.S)
_RE_NUMERO_TITRE = re.compile(r"scrutin\s*n[°o]\s*(\d+)", re.I)
_RE_DATE_SEANCE = re.compile(r"s[ée]ance\s+du\s+(\d{1,2})\s+([\wéû]+)\s+(\d{4})", re.I)
_RE_OBJET = re.compile(r'<p class="page-lead">(.*?)</p>', re.S)
_RE_SORT = re.compile(r'<span class="badge[^"]*">(.*?)</span>', re.S)
_RE_LIEN_DOSSIER = re.compile(r'href="(/dossier-legislatif/[^"]+)"')
# Décomptes globaux : « <strong class="display-4 …">214</strong> pour ».
_RE_DECOMPTE = re.compile(
    r'<strong class="display-4[^"]*">\s*(\d+)\s*</strong>\s*([^<]+)', re.S
)
_RE_ABSTENTION = re.compile(
    r"Abstention\s*:\s*<span[^>]*>\s*(\d+)\s*</span>", re.S | re.I
)
_RE_NON_VOTANTS = re.compile(
    r"pas\s+pris\s+part\s+au\s+vote\s*:\s*<span[^>]*>\s*(\d+)\s*</span>", re.S | re.I
)
# Analyse par groupe : un bloc par groupe, identifié par son code (« UMP »).
_RE_BLOC_GROUPE = re.compile(r'<div id="accordion-scrutin-([\w-]+)"')
# Début du conteneur replié qui porte les listes nominatives d'un groupe.
_DEBUT_LISTE_NOMS = '<div id="accordion-collapse'
_RE_ENTETE_GROUPE = re.compile(
    r'<h3 class="accordion-title[^"]*">(.*?)</h3>', re.S
)
# Le préfixe « sur » de l'objet du vote, propre au Sénat.
_RE_PREFIXE_SUR = re.compile(r"^sur\s+", re.I)
# « présenté par M. Bernard Delcros » — l'AN écrit « de M. Léaument » (le nom
# seul), le Sénat « présenté par M. Bernard Delcros » (prénom ET nom) : deux
# formulations, même fait. On capte donc un ou deux mots capitalisés, et on
# s'arrête au premier mot en minuscule (« et plusieurs de ses collègues »).
_MOT_NOM = r"[A-ZÀ-Þ][\w'’/-]*"
_RE_AUTEUR_SENAT = re.compile(
    rf"pr[ée]sent[ée]s?\s+par\s+(M\.|Mme|MM\.|Mmes)\s+({_MOT_NOM}(?:\s+{_MOT_NOM})?)"
)
# « à l'article 8 du projet de loi… » / « à l'article unique de la proposition… »
_RE_ARTICLE_VISE = re.compile(
    r"[àa]\s+l['’]article\s+(unique|premier|\d+(?:\s*(?:bis|ter|quater))?)", re.I
)


def session_pour(annee: int, mois: int) -> int:
    """Année de session parlementaire pour une date donnée.

    La session ordinaire court d'octobre à septembre : un scrutin de juillet 2026
    appartient à la session « 2025 ». C'est cette année-là que portent les URLs.
    """
    return annee if mois >= _PREMIER_MOIS_SESSION else annee - 1


def _texte(fragment: str) -> str:
    """Contenu textuel d'un fragment HTML, espaces normalisés."""
    sans_balises = re.sub(r"<[^>]+>", " ", fragment)
    return " ".join(html.unescape(sans_balises).replace("\xa0", " ").split())


def _entier(valeur: object) -> int:
    try:
        return int(str(valeur).strip())
    except (TypeError, ValueError):
        return 0


@dataclass(frozen=True)
class GroupeScrutinSenat:
    """Décomptes officiels d'un groupe sur un scrutin (analyse par groupe)."""

    code: str
    nom: str
    pour: int = 0
    contre: int = 0
    abstention: int = 0
    non_votants: int = 0


@dataclass(frozen=True)
class PageScrutinSenat:
    """Ce que la page d'un scrutin du Sénat documente (résultat du parsing pur)."""

    session: int
    numero: int
    date: str  # ISO « AAAA-MM-JJ »
    objet: str  # sans le « sur » initial
    statut: str  # « adopte » | « rejete »
    slug_dossier: str | None
    resultat: ResultatGlobal
    groupes: list[GroupeScrutinSenat] = field(default_factory=list)

    @property
    def id(self) -> str:
        """Identifiant stable du scrutin, préfixé pour ne pas heurter les uid AN."""
        return f"SEN-{self.session}-{self.numero}"

    @property
    def url(self) -> str:
        return URL_SCRUTIN.format(session=self.session, numero=self.numero)


def _date_iso(fragment_titre: str) -> str | None:
    m = _RE_DATE_SEANCE.search(fragment_titre)
    if not m:
        return None
    mois = _MOIS.get(m.group(2).lower())
    if mois is None:
        return None
    return f"{int(m.group(3)):04d}-{mois:02d}-{int(m.group(1)):02d}"


def _decomptes_globaux(page: str) -> ResultatGlobal:
    """Résultat global depuis le bloc « Résultat du scrutin ».

    Seuls « pour » et « contre » sont mis en avant par la page ; l'abstention et
    les non-votants vivent dans la ligne en dessous. Un décompte absent vaut 0 —
    la page les affiche systématiquement, y compris à zéro.
    """
    compte = {
        libelle.strip().lower(): _entier(valeur)
        for valeur, libelle in _RE_DECOMPTE.findall(page)
    }
    abstention = _RE_ABSTENTION.search(page)
    non_votants = _RE_NON_VOTANTS.search(page)
    return ResultatGlobal(
        pour=compte.get("pour", 0),
        contre=compte.get("contre", 0),
        abstention=_entier(abstention.group(1)) if abstention else 0,
        non_votants=_entier(non_votants.group(1)) if non_votants else 0,
    )


def _groupes(page: str) -> list[GroupeScrutinSenat]:
    """Analyse par groupe : décomptes **officiels**, pas la longueur des listes.

    Chaque bloc de groupe porte d'abord son en-tête (nom, effectif, décomptes)
    puis, replié, la liste nominative. On s'arrête au conteneur replié : les
    mêmes mots (« Pour : ») réapparaissent plus bas pour introduire les noms.
    """
    groupes: list[GroupeScrutinSenat] = []
    marqueurs = list(_RE_BLOC_GROUPE.finditer(page))
    for i, marqueur in enumerate(marqueurs):
        fin = marqueurs[i + 1].start() if i + 1 < len(marqueurs) else len(page)
        bloc = page[marqueur.start() : fin]
        # `_DEBUT_LISTE_NOMS` et non « accordion-collapse » seul : ce fragment
        # apparaît AUSSI dans les attributs du bouton, en amont de l'en-tête.
        coupure = bloc.find(_DEBUT_LISTE_NOMS)
        entete = bloc[:coupure] if coupure > 0 else bloc

        titre = _RE_ENTETE_GROUPE.search(entete)
        if not titre:
            continue
        texte_titre = _texte(titre.group(1))
        # « Groupe Les Républicains : 131 sénateurs » → nom avant le décompte.
        nom = re.split(r"\s*:\s*\d", texte_titre)[0].strip() or texte_titre

        texte_entete = _texte(entete)

        def compte(motif: str) -> int:
            trouve = re.search(motif + r"\s*:\s*(\d+)", texte_entete, re.I)
            return _entier(trouve.group(1)) if trouve else 0

        groupes.append(
            GroupeScrutinSenat(
                code=marqueur.group(1),
                nom=nom,
                pour=compte(r"\bPour"),
                contre=compte(r"\bContre"),
                abstention=compte(r"\bAbstentions?"),
                non_votants=compte(r"pas pris part au vote"),
            )
        )
    return groupes


def parse_page_scrutin(page: str, session: int) -> PageScrutinSenat | None:
    """Convertit la page d'un scrutin du Sénat en `PageScrutinSenat`.

    Fonction **pure** (HTML → objet), testable sans réseau. None si la page ne
    porte pas les repères attendus : mieux vaut sauter un scrutin que d'en
    fabriquer un à moitié (§2.5).
    """
    # La page sépare systématiquement un libellé de son deux-points par une
    # espace insécable (« Pour&nbsp;: »). On la normalise d'emblée, sinon aucun
    # motif « libellé\s*: » ne peut correspondre.
    page = page.replace("&nbsp;", " ").replace("\xa0", " ")

    titre = _RE_TITRE.search(page)
    objet_brut = _RE_OBJET.search(page)
    if not titre or not objet_brut:
        return None
    texte_titre = _texte(titre.group(1))
    numero = _RE_NUMERO_TITRE.search(texte_titre)
    date = _date_iso(texte_titre)
    objet = _RE_PREFIXE_SUR.sub("", _texte(objet_brut.group(1))).strip()
    if not numero or not date or not objet:
        return None

    sort = _RE_SORT.search(page)
    # Le badge de la page porte le sort (« Adopté » / « Rejeté »). Sans lui, on
    # ne devine pas : un scrutin sans sort lisible est écarté (§2.5).
    if not sort:
        return None
    libelle_sort = _texte(sort.group(1))
    if not libelle_sort:
        return None

    lien = _RE_LIEN_DOSSIER.search(page)
    return PageScrutinSenat(
        session=session,
        numero=int(numero.group(1)),
        date=date,
        objet=objet,
        statut="adopte" if "adopt" in libelle_sort.lower() else "rejete",
        slug_dossier=slug_dossier_senat(lien.group(1)) if lien else None,
        resultat=_decomptes_globaux(page),
        groupes=_groupes(page),
    )


def numeros_de_session(index: str, session: int) -> list[int]:
    """Numéros de scrutin listés par l'index annuel, du plus récent au plus ancien."""
    motif = re.compile(rf"scr{session}-(\d+)\.html")
    numeros = {int(n) for n in motif.findall(index)}
    return sorted(numeros, reverse=True)


def auteur_amendement_senat(objet: str) -> str | None:
    """Auteur d'un amendement du Sénat (« présenté par M. X »), s'il est unique.

    L'Assemblée écrit « de M. X », le Sénat « présenté par M. X » : deux
    formulations pour le même fait. Plusieurs auteurs (amendements identiques) →
    None, comme côté AN : on ne choisit pas pour le lecteur (§2.5).
    """
    auteurs = {
        f"{civilite} {nom}" for civilite, nom in _RE_AUTEUR_SENAT.findall(objet)
    }
    return auteurs.pop() if len(auteurs) == 1 else None


def article_vise_senat(objet: str) -> str | None:
    """Article visé par un amendement, cité par l'objet officiel du vote.

    Côté Assemblée cette information vient de l'archive des amendements ; côté
    Sénat, l'objet du vote la porte lui-même (« … à l'article 8 du projet de
    loi… »). Extrait tel quel, jamais reconstitué.
    """
    m = _RE_ARTICLE_VISE.search(objet)
    if not m:
        return None
    reste = " ".join(m.group(1).split())
    return f"Article {reste}"


def source_scrutin_senat(session: int, numero: int) -> SourceOfficielle:
    return SourceOfficielle(
        type="scrutin",
        libelle="Scrutin",
        url=URL_SCRUTIN.format(session=session, numero=numero),
    )


def source_dossier_senat(slug: str) -> SourceOfficielle:
    return SourceOfficielle(
        type="texte",
        libelle="Dossier législatif au Sénat",
        url=URL_DOSSIER.format(slug=slug),
    )


def _position_majoritaire(groupe: GroupeScrutinSenat) -> PositionVote:
    """Position majoritaire d'un groupe, déduite de ses décomptes officiels.

    Le Sénat ne publie pas ce champ (l'AN si) : on le calcule. En cas d'égalité
    parfaite entre deux positions — ou d'aucun vote exprimé — le groupe n'a pas
    de position majoritaire exploitable : `non_votant`, le même repli que côté
    Assemblée pour un groupe sans position (§2.5).
    """
    exprimes = (
        (PositionVote.pour, groupe.pour),
        (PositionVote.contre, groupe.contre),
        (PositionVote.abstention, groupe.abstention),
    )
    maximum = max(n for _, n in exprimes)
    if maximum == 0:
        return PositionVote.non_votant
    en_tete = [p for p, n in exprimes if n == maximum]
    return en_tete[0] if len(en_tete) == 1 else PositionVote.non_votant


def _votants_par_groupe(
    votes: object,
    annuaire: dict[str, InfoSenateur],
    senateurs_connus: frozenset[str] | None,
) -> dict[str, dict[PositionVote, list[Votant]]]:
    """Répartit le vote nominatif par (code de groupe, position).

    Un matricule absent de l'annuaire est **omis** : sa référence machine n'est
    pas un nom, et l'afficher à sa place tromperait le lecteur (§2.5, même règle
    que côté Assemblée). Le décompte officiel du groupe reste affiché à côté, si
    bien qu'un éventuel écart est visible plutôt que masqué.
    """
    from app.ingestion.senateurs import POSITIONS

    if isinstance(votes, dict):
        votes = votes.get("votes")
    if not isinstance(votes, list):
        return {}

    connus = senateurs_connus or frozenset()
    par_groupe: dict[str, dict[PositionVote, list[Votant]]] = {}
    for brut in votes:
        if not isinstance(brut, dict):
            continue
        matricule = str(brut.get("matricule") or "").strip()
        position = POSITIONS.get(str(brut.get("vote") or "").strip().lower())
        info = annuaire.get(matricule)
        if info is None or position is None:
            continue
        identifiant = id_senateur(matricule)
        par_groupe.setdefault(info.groupe_code, {}).setdefault(position, []).append(
            Votant(
                nom=info.nom,
                depute_id=identifiant if identifiant in connus else None,
            )
        )
    return par_groupe


def parse_scrutin_senat(
    page: PageScrutinSenat,
    votes: object = None,
    annuaire: dict[str, InfoSenateur] | None = None,
    *,
    dossier_ref: str | None = None,
    reconciliation: Reconciliation | None = None,
    senateurs_connus: frozenset[str] | None = None,
) -> ScrutinParse:
    """Convertit un scrutin du Sénat en `ScrutinParse` (fonction pure).

    `dossier_ref` est le `dossierRef` AN déjà résolu par l'appelant (niveaux 1 et
    2 de la cascade, qui demandent réseau) ; cette fonction assure les niveaux
    suivants — réconciliation par titre, dossier d'origine sénatoriale, puis
    singleton. `annuaire` (matricule → sénateur) active le vote nominatif ;
    `senateurs_connus` décide quels noms sont cliquables (jamais un lien vers un
    404, même règle que côté Assemblée).
    """
    annuaire = annuaire or {}
    nominatif = _votants_par_groupe(votes, annuaire, senateurs_connus)

    positions: list[PositionGroupe] = []
    for groupe in page.groupes:
        noms = nominatif.get(groupe.code, {})
        positions.append(
            PositionGroupe(
                groupe_id=id_groupe_senat(groupe.code),
                groupe_nom=groupe.nom,
                couleur=couleur_groupe(groupe.code),
                position_majoritaire=_position_majoritaire(groupe),
                pour=groupe.pour,
                contre=groupe.contre,
                abstention=groupe.abstention,
                # Jamais de cohésion au Sénat : la délégation de vote par groupe
                # la viderait de sens (cf. `senateurs`, §7.4).
                cohesion=None,
                votants_pour=noms.get(PositionVote.pour) or None,
                votants_contre=noms.get(PositionVote.contre) or None,
                votants_abstention=noms.get(PositionVote.abstention) or None,
            )
        )

    # --- Rattachement au dossier (suite de la cascade) --------------------
    rattachement = texte_de_rattachement(page.objet)
    if dossier_ref:
        dossier_id = dossier_ref
        dossier_titre = rattachement or page.objet
    else:
        ref_par_titre = (
            reconciliation.ref_pour_titre(rattachement) if reconciliation else None
        )
        if ref_par_titre:
            dossier_ref = ref_par_titre
            dossier_id = ref_par_titre
            dossier_titre = rattachement or page.objet
        elif page.slug_dossier:
            # Dossier d'origine sénatoriale : le slug du Sénat est un identifiant
            # stable (contrairement au titre, qui varie d'un vote à l'autre) —
            # pas besoin de hacher, contrairement aux dossiers « TXT-… ».
            dossier_id = f"SEN-{page.slug_dossier}"
            dossier_titre = rattachement or page.objet
        else:
            # Ni texte cité ni dossier : événement autonome (motion, débat).
            dossier_id = page.id
            dossier_titre = page.objet

    sources = [source_scrutin_senat(page.session, page.numero)]

    scrutin = Scrutin(
        id=page.id,
        dossier_id=dossier_id,
        date=page.date,
        objet=truncate(page.objet, 120),
        statut=page.statut,
        # ⚠️ Classé sur l'objet ENTIER, avant la troncature ci-dessus. Un objet
        # du Sénat s'ouvre sur le numéro et l'auteur de la motion (« la motion
        # n° 278, présentée par Mme… ») et ne dit qu'ensuite ce qu'elle est
        # (« tendant à opposer la question préalable ») — vers le 135e
        # caractère. Classer après troncature ne verrait donc jamais rien, et
        # ces votes resteraient sans nom ni mention à l'écran.
        type_motion=type_motion(page.objet),
        chambre=Chambre.senat,
        # Le Sénat ne publie en ligne que ses scrutins publics (§5.2).
        scrutin_public=True,
        resultat=page.resultat,
        positions_groupes=positions,
        cible=article_vise_senat(page.objet),
        sources=sources,
    )

    return ScrutinParse(
        scrutin=scrutin,
        dossier_id=dossier_id,
        dossier_titre=truncate(dossier_titre, 160),
        dossier_ref=dossier_ref,
        # Page officielle du dossier au Sénat : elle ne sert de source de niveau
        # dossier que si l'Assemblée n'en a pas (cf. `build_dossier`).
        source_dossier=(
            source_dossier_senat(page.slug_dossier) if page.slug_dossier else None
        ),
        theme=guess_theme(dossier_titre, page.objet),
        # Le Sénat ne numérote pas ses travaux par législature : la session tient
        # ce rôle dans ses URLs, on la transporte telle quelle.
        legislature=str(page.session),
        numero=str(page.numero),
    )


# ---------------------------------------------------------------------------
# Client réseau
# ---------------------------------------------------------------------------


class SenatOpenDataClient:
    """Accès aux ressources publiques de senat.fr (best-effort, §2.5).

    Le Sénat n'offre pas d'archive groupée : on télécharge un scrutin à la fois.
    Les requêtes sont donc plafonnées en parallélisme, par courtoisie envers le
    serveur, et chaque échec est simplement sauté — jamais comblé.
    """

    _TENTATIVES = 3
    _ATTENTES_S = (2.0, 6.0)
    CONCURRENCE = 6

    def __init__(self, session: int, timeout: float = 30.0) -> None:
        self.session = session
        self._timeout = timeout

    async def _get(self, client: httpx.AsyncClient, url: str) -> str | None:
        for tentative in range(self._TENTATIVES):
            try:
                reponse = await client.get(url)
                if reponse.status_code == 404:
                    return None
                reponse.raise_for_status()
                return reponse.text
            except httpx.HTTPError:
                if tentative < len(self._ATTENTES_S):
                    await asyncio.sleep(self._ATTENTES_S[tentative])
        return None

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            timeout=self._timeout,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0"},
        )

    async def numeros(self) -> list[int]:
        """Numéros de scrutin de la session, du plus récent au plus ancien."""
        async with self._client() as client:
            index = await self._get(
                client, URL_INDEX_SESSION.format(session=self.session)
            )
        return numeros_de_session(index, self.session) if index else []

    async def telecharger_scrutins(
        self, numeros: list[int]
    ) -> list[tuple[PageScrutinSenat, object]]:
        """Télécharge et parse les scrutins demandés : `(page, votes nominatifs)`.

        Un scrutin dont la page manque ou n'est pas exploitable est sauté ; son
        JSON nominatif absent laisse simplement le vote sans détail (§2.5).
        """
        semaphore = asyncio.Semaphore(self.CONCURRENCE)
        resultats: list[tuple[int, PageScrutinSenat, object]] = []

        async def charger(client: httpx.AsyncClient, numero: int) -> None:
            async with semaphore:
                brut = await self._get(
                    client, URL_SCRUTIN.format(session=self.session, numero=numero)
                )
                if brut is None:
                    return
                page = parse_page_scrutin(brut, self.session)
                if page is None:
                    return
                corps = await self._get(
                    client,
                    URL_SCRUTIN_JSON.format(session=self.session, numero=numero),
                )
            votes: object = None
            if corps:
                try:
                    import json

                    votes = json.loads(corps)
                except ValueError:
                    votes = None
            resultats.append((numero, page, votes))

        async with self._client() as client:
            await asyncio.gather(*(charger(client, n) for n in numeros))
        resultats.sort(key=lambda r: r[0])
        return [(page, votes) for _, page, votes in resultats]

    async def senateurs(self) -> list[dict]:
        """Annuaire brut des sénateurs (liste vide si injoignable)."""
        async with self._client() as client:
            corps = await self._get(client, URL_SENATEURS)
        if not corps:
            return []
        try:
            import json

            donnees = json.loads(corps)
        except ValueError:
            return []
        return donnees if isinstance(donnees, list) else []

    async def ref_an_du_dossier(self, slug: str, jointure: JointureSenat) -> str | None:
        """Niveau 2 de la cascade : le `dossierRef` AN cité par la page du dossier.

        Quand l'archive de l'Assemblée n'a pas (encore) renseigné `senatChemin`,
        c'est le Sénat qui cite l'Assemblée. On ne retient le lien que s'il se
        résout en un dossier connu, sans ambiguïté (§2.5)."""
        async with self._client() as client:
            page = await self._get(client, URL_DOSSIER.format(slug=slug))
        if not page:
            return None
        for url in re.findall(r'href="([^"]*assemblee-nationale[^"]*)"', page):
            ref = jointure.ref_pour_url_an(url)
            if ref:
                return ref
        return None

    async def telecharger_texte_pdf(self, slug: str) -> bytes | None:
        """PDF du texte déposé au Sénat (exposé des motifs + dispositif)."""
        try:
            async with self._client() as client:
                reponse = await client.get(URL_TEXTE_PDF.format(slug=slug))
            if reponse.status_code != 200:
                return None
            if "pdf" not in reponse.headers.get("content-type", "").lower():
                return None
            return reponse.content
        except httpx.HTTPError:
            return None


# ---------------------------------------------------------------------------
# CLI autonome : sénateurs + scrutins du Sénat UNIQUEMENT.
# ---------------------------------------------------------------------------


async def _main(limit: int | None, session: int | None, legislature: int) -> None:
    """Ingère les seuls travaux du Sénat (ni LLM, ni archives de l'Assemblée).

    Pendant de `python -m app.ingestion.deputes` : quelques minutes au lieu d'un
    run complet. La jointure vers les dossiers de l'Assemblée reste faite —
    c'est elle qui évite de dupliquer un texte déjà présent dans le fil — mais
    l'enrichissement (résumés, questions, thèmes affinés) est laissé au run
    complet, qui reconstruira les dossiers touchés.
    """
    import argparse as _argparse  # noqa: F401  (documenté par `main`)
    from datetime import date, datetime, timezone

    from app.db.session import init_models, make_engine, make_session_factory
    from app.ingestion.assemblee import AssembleeOpenDataClient
    from app.ingestion.deputes import remplacer_votes_du_scrutin, upsert_deputes
    from app.ingestion.dossiers_legislatifs import (
        construire_jointure_senat,
        construire_reconciliation,
    )
    from app.ingestion.senateurs import (
        build_senateurs,
        construire_annuaire,
        groupes_senat,
        votes_du_scrutin_senat,
    )
    from app.ingestion.sync import _upsert_groupes, _upsert_scrutin

    if session is None:
        aujourdhui = date.today()
        session = session_pour(aujourdhui.year, aujourdhui.month)

    debut = datetime.now(timezone.utc)
    engine = make_engine()
    await init_models(engine)
    sf = make_session_factory(engine)
    client = SenatOpenDataClient(session=session)

    print(f"Sénat (session {session}, limit={limit})…")
    annuaire = construire_annuaire(await client.senateurs())
    if not annuaire:
        print("⚠ annuaire des sénateurs injoignable : arrêt (rien n'a été écrit).")
        await engine.dispose()
        return
    senateurs = build_senateurs(annuaire)
    async with sf() as s:
        nb_groupes = await _upsert_groupes(s, groupes_senat(annuaire), Chambre.senat)
        nb_senateurs = await upsert_deputes(s, senateurs)
        await s.commit()
    print(f"  {nb_senateurs} sénateurs, {nb_groupes} groupes.")

    # Jointure vers les dossiers de l'Assemblée : une seule archive (10 Mo).
    client_an = AssembleeOpenDataClient(legislature=legislature)
    documents, dossiers = await client_an.download_dossiers_complet()
    jointure = construire_jointure_senat(dossiers)
    reconciliation = construire_reconciliation(documents, (legislature,))
    print(f"  jointure Assemblée ↔ Sénat : {len(jointure)} dossiers appariés.")

    numeros = await client.numeros()
    if limit is not None:
        numeros = numeros[:limit]
    pages = await client.telecharger_scrutins(numeros)
    connus = frozenset(s.id for s in senateurs)

    refs_par_slug: dict[str, str | None] = {}
    nb_votes = 0
    nb_joints = 0
    async with sf() as s:
        for i, (page, votes) in enumerate(pages, start=1):
            slug = page.slug_dossier
            ref: str | None = None
            if slug:
                if slug not in refs_par_slug:
                    trouve = jointure.ref_pour_slug_senat(slug)
                    if trouve is None:
                        trouve = await client.ref_an_du_dossier(slug, jointure)
                    refs_par_slug[slug] = trouve
                ref = refs_par_slug[slug]
            parse = parse_scrutin_senat(
                page,
                votes,
                annuaire,
                dossier_ref=ref,
                reconciliation=reconciliation,
                senateurs_connus=connus,
            )
            if parse.dossier_ref:
                nb_joints += 1
            await _upsert_scrutin(s, parse.scrutin)
            if votes is not None:
                nb_votes += await remplacer_votes_du_scrutin(
                    s,
                    parse.scrutin.id,
                    parse.scrutin.date,
                    votes_du_scrutin_senat(votes, annuaire),
                )
            if i % 50 == 0:
                await s.commit()
                print(f"  [{i}/{len(pages)}] {nb_votes} votes nominatifs écrits")
        await s.commit()
    await engine.dispose()

    duree = (datetime.now(timezone.utc) - debut).total_seconds()
    print(
        f"Terminé en {duree:.0f} s : {len(pages)} scrutins du Sénat "
        f"({nb_joints} rattachés à un dossier de l'Assemblée), "
        f"{nb_votes} votes nominatifs, {nb_senateurs} sénateurs.\n"
        "  ⚠ Les dossiers ne sont pas reconstruits ici : relancer "
        "`python -m app.ingestion.run` pour les résumés et la trajectoire."
    )


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Ingestion des scrutins publics et des sénateurs (Sénat seul)"
    )
    parser.add_argument("--limit", type=int, default=None, help="Nb de scrutins récents")
    parser.add_argument(
        "--session",
        type=int,
        default=None,
        help="Année de DÉBUT de session (oct.→sept.) ; par défaut, la session en cours",
    )
    parser.add_argument(
        "--legislature",
        type=int,
        default=17,
        help="Législature de l'Assemblée, pour la jointure des dossiers",
    )
    args = parser.parse_args()
    asyncio.run(_main(args.limit, args.session, args.legislature))


if __name__ == "__main__":
    main()
