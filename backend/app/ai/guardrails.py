"""Garde-fous automatiques avant affichage d'un résumé (§4.4 du MVP).

« Le risque n°1 n'est pas technique, il est éditorial. » Ces contrôles sont de la
logique pure, testable sans LLM. Un résumé qui échoue à un garde-fou bloquant
n'est jamais publié automatiquement : il part en revue humaine (§4.6).

Contrôles :
- ancrage       : chaque phrase renvoie à une source fournie (source_id connu) ;
- lexique       : aucun adjectif/tournure évaluative (liste noire, §4.3) ;
- chiffres      : les décomptes cités correspondent au résultat officiel ;
- confiance     : « faible » ⇒ revue humaine obligatoire.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from app.domain.enums import NiveauConfiance
from app.schemas import ResultatGlobal, ResumeScrutin

# Liste noire de lexique orienté (§4.3). Non exhaustive — à enrichir en revue.
LEXIQUE_ORIENTE: frozenset[str] = frozenset(
    {
        "ambitieux",
        "ambitieuse",
        "insuffisant",
        "insuffisante",
        "controverse",  # « controversé » (comparaison sans accents, voir _normalize)
        "scandaleux",
        "courageux",
        "laxiste",
        "liberticide",
        "historique",  # au sens laudatif
        "inedit",
        "necessaire",
        "indispensable",
        "dangereux",
        "injuste",
        "juste",
        "progressiste",
        "regressif",
        "timide",
        "audacieux",
        "brutal",
        "massif",
    }
)


@dataclass
class Violation:
    regle: str          # "ancrage" | "lexique" | "chiffres"
    message: str
    bloquant: bool = True


@dataclass
class GuardrailReport:
    violations: list[Violation] = field(default_factory=list)

    @property
    def bloquant(self) -> bool:
        return any(v.bloquant for v in self.violations)

    @property
    def ok(self) -> bool:
        return not self.violations


def _normalize(text: str) -> str:
    """Minuscule + suppression des accents, pour comparer le lexique."""
    nfkd = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-zàâäéèêëïîôöùûüç]+", text.lower())


def check_ancrage(resume: ResumeScrutin, sources_autorisees: set[str]) -> list[Violation]:
    """Chaque phrase doit citer une source fournie (§4.1 point 3, §4.4)."""
    violations: list[Violation] = []
    for i, phrase in enumerate(resume.resume):
        if not phrase.source_id:
            violations.append(
                Violation("ancrage", f"Phrase {i + 1} sans source.")
            )
        elif phrase.source_id not in sources_autorisees:
            violations.append(
                Violation(
                    "ancrage",
                    f"Phrase {i + 1} cite une source inconnue : "
                    f"'{phrase.source_id}'.",
                )
            )
    return violations


def check_lexique(resume: ResumeScrutin) -> list[Violation]:
    """Aucun adjectif/tournure évaluative (§4.3)."""
    violations: list[Violation] = []
    champs = [p.phrase for p in resume.resume]
    champs += [
        c
        for c in (resume.contexte, resume.objectif, resume.historique)
        if c
    ]
    for texte in champs:
        for mot in _tokens(_normalize(texte)):
            if mot in LEXIQUE_ORIENTE:
                violations.append(
                    Violation(
                        "lexique",
                        f"Terme potentiellement orienté détecté : « {mot} ».",
                    )
                )
    return violations


# Mots signalant qu'un nombre voisin est un décompte de vote (et non une date,
# un montant, un article de loi…). Comparés sans accents (voir _normalize).
CONTEXTE_VOTE: frozenset[str] = frozenset(
    {
        "voix",
        "vote",
        "votes",
        "votant",
        "votants",
        "pour",
        "contre",
        "abstention",
        "abstentions",
        "depute",
        "deputes",
        "suffrage",
        "suffrages",
        "favorables",
        "defavorables",
    }
)

# Fenêtre (en mots) autour d'un nombre où l'on cherche un mot de contexte de vote.
_FENETRE_CONTEXTE = 3


def check_chiffres(resume: ResumeScrutin, resultat: ResultatGlobal) -> list[Violation]:
    """Tout décompte de vote cité dans le résumé doit correspondre au résultat
    officiel.

    Contrôle strict, sans tolérance (§4.4). On ne considère que les nombres
    proches d'un mot de contexte de vote (« 231 contre », « 999 voix ») : un
    nombre isolé comme une année (« 2027 ») n'est pas un décompte et n'est pas
    contrôlé ici.
    """
    officiels = {
        resultat.pour,
        resultat.contre,
        resultat.abstention,
        resultat.non_votants,
        resultat.pour + resultat.contre + resultat.abstention + resultat.non_votants,
    }
    violations: list[Violation] = []
    for phrase in resume.resume:
        # Tokens normalisés en conservant l'ordre (mots + nombres).
        tokens = re.findall(r"\d+|[a-zàâäéèêëïîôöùûüç]+", _normalize(phrase.phrase))
        for i, tok in enumerate(tokens):
            if not tok.isdigit():
                continue
            debut = max(0, i - _FENETRE_CONTEXTE)
            fin = min(len(tokens), i + _FENETRE_CONTEXTE + 1)
            voisins = tokens[debut:i] + tokens[i + 1 : fin]
            if not any(v in CONTEXTE_VOTE for v in voisins):
                continue
            n = int(tok)
            if n not in officiels:
                violations.append(
                    Violation(
                        "chiffres",
                        f"Le décompte {n} du résumé ne correspond à aucun chiffre "
                        "officiel du scrutin.",
                    )
                )
    return violations


def run_guardrails(
    resume: ResumeScrutin,
    resultat: ResultatGlobal,
    sources_autorisees: set[str],
) -> GuardrailReport:
    """Exécute tous les garde-fous et agrège les violations."""
    report = GuardrailReport()
    report.violations += check_ancrage(resume, sources_autorisees)
    report.violations += check_lexique(resume)
    report.violations += check_chiffres(resume, resultat)
    return report


def doit_passer_en_revue(
    report: GuardrailReport, confiance: NiveauConfiance
) -> bool:
    """Un résumé part en revue humaine si un garde-fou bloque OU confiance faible.

    §4.4 : « si "faible", le résumé passe en file de revue humaine et n'est pas
    publié automatiquement. »
    """
    return report.bloquant or confiance == NiveauConfiance.faible
