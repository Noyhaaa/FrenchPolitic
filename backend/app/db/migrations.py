"""Migrations additives du schéma (le dépôt n'a pas d'Alembic).

`init_models` se contente d'un `create_all` : il crée les tables manquantes mais
ne touche **jamais** à celles qui existent déjà. Une colonne ajoutée au modèle
n'apparaît donc pas sur une base déjà peuplée, et l'API tombe à la première
requête.

Ce module applique les quelques DDL **additives et idempotentes** qui manquent.
Chaque énoncé est écrit pour pouvoir être rejoué sans effet : `ADD COLUMN IF NOT
EXISTS`, élargissement de type (jamais de rétrécissement). Aucune donnée n'est
supprimée ni réécrite — les lignes existantes reçoivent la valeur par défaut,
qui est toujours choisie pour décrire fidèlement ce qu'elles sont déjà.

    python -m app.db.migrations            # applique ce qui manque
    python -m app.db.migrations --dry-run  # affiche sans exécuter

Une migration destructive n'a rien à faire ici : elle mériterait un vrai outil.
"""
from __future__ import annotations

import argparse
import asyncio

from sqlalchemy import text

from app.db.session import make_engine

# (libellé, SQL). L'ordre est celui de l'application.
#
# `chambre` : introduite avec l'ingestion du Sénat. Toutes les lignes existantes
# viennent de l'Assemblée — la valeur par défaut les décrit exactement, il n'y a
# donc rien à recalculer.
MIGRATIONS: tuple[tuple[str, str], ...] = (
    (
        "scrutin.chambre",
        "ALTER TABLE scrutin ADD COLUMN IF NOT EXISTS chambre "
        "VARCHAR(16) NOT NULL DEFAULT 'assemblee'",
    ),
    (
        "index scrutin.chambre",
        "CREATE INDEX IF NOT EXISTS ix_scrutin_chambre ON scrutin (chambre)",
    ),
    (
        "depute.chambre",
        "ALTER TABLE depute ADD COLUMN IF NOT EXISTS chambre "
        "VARCHAR(16) NOT NULL DEFAULT 'assemblee'",
    ),
    (
        "index depute.chambre",
        "CREATE INDEX IF NOT EXISTS ix_depute_chambre ON depute (chambre)",
    ),
    (
        "groupe.chambre",
        "ALTER TABLE groupe ADD COLUMN IF NOT EXISTS chambre "
        "VARCHAR(16) NOT NULL DEFAULT 'assemblee'",
    ),
    (
        "index groupe.chambre",
        "CREATE INDEX IF NOT EXISTS ix_groupe_chambre ON groupe (chambre)",
    ),
    # Les groupes du Sénat portent un identifiant préfixé (« SEN-… ») : la
    # colonne était dimensionnée pour les seuls organeRef de l'Assemblée.
    ("groupe.id élargi", "ALTER TABLE groupe ALTER COLUMN id TYPE VARCHAR(32)"),
    # `indice_division` ordonne la rangée « Les votes les plus disputés ».
    # Volontairement NULLABLE sans valeur par défaut : NULL veut dire « pas
    # encore calculé » (ou « non classable »), et un 0 par défaut aurait menti
    # en présentant tous les votes existants comme unanimes. La colonne se
    # remplit avec `python -m app.ingestion.divisions`.
    (
        "scrutin.indice_division",
        "ALTER TABLE scrutin ADD COLUMN IF NOT EXISTS indice_division "
        "DOUBLE PRECISION",
    ),
    (
        "index scrutin.indice_division",
        "CREATE INDEX IF NOT EXISTS ix_scrutin_indice_division "
        "ON scrutin (indice_division)",
    ),
    # `desaccord_sources` conserve les extraits de compte rendu qui ont produit la
    # Q2, pour pouvoir revalider ces paraphrases hors ligne (comme l'exposé le
    # permet déjà pour la Q1/Q4). NULLABLE sans défaut : NULL veut dire « source
    # non conservée » — ce qui décrit exactement les lignes écrites avant, dont
    # les arguments sont donc invérifiables et seront effacés par
    # `python -m app.ingestion.revalider`.
    (
        "dossier.desaccord_sources",
        "ALTER TABLE dossier ADD COLUMN IF NOT EXISTS desaccord_sources JSONB",
    ),
    # `commission` : publiée par l'annuaire du Sénat, absente côté Assemblée.
    # NULLABLE sans défaut — NULL veut dire « non documentée », ce qui décrit
    # exactement les lignes existantes (et durablement les députés).
    (
        "depute.commission",
        "ALTER TABLE depute ADD COLUMN IF NOT EXISTS commission TEXT",
    ),
)


async def appliquer(dry_run: bool = False) -> int:
    """Applique les migrations manquantes ; renvoie le nombre d'énoncés joués."""
    engine = make_engine()
    joues = 0
    try:
        async with engine.begin() as connexion:
            for libelle, sql in MIGRATIONS:
                if dry_run:
                    print(f"  [dry-run] {libelle}\n      {sql}")
                    continue
                await connexion.execute(text(sql))
                print(f"  ✓ {libelle}")
                joues += 1
    finally:
        await engine.dispose()
    return joues


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Migrations additives du schéma (idempotentes)"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Afficher sans exécuter"
    )
    args = parser.parse_args()
    print("Migrations du schéma…")
    joues = asyncio.run(appliquer(args.dry_run))
    if args.dry_run:
        print(f"{len(MIGRATIONS)} énoncé(s) à jouer (aucun exécuté).")
    else:
        print(f"Terminé : {joues} énoncé(s) appliqué(s) (rejouables sans effet).")


if __name__ == "__main__":
    main()
