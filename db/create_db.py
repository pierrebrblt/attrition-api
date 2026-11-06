"""Création de la base PostgreSQL et des tables.

Usage :
    python -m db.create_db                    # crée la base (si absente) puis les tables
    python -m db.create_db --drop             # supprime puis recrée les tables (dev uniquement)
    python -m db.create_db --dump-sql db/schema.sql   # régénère le DDL SQL équivalent

L'URL est lue dans ``DATABASE_URL`` (voir .env.example) ou passée via ``--database-url``.
Le schéma est défini une seule fois dans ``app/db_models.py`` ; ``db/schema.sql`` en est la
traduction SQL générée, utilisable directement avec ``psql -f db/schema.sql``.
"""

import argparse
import logging
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine import URL, make_url
from sqlalchemy.schema import CreateIndex, CreateTable

from app import db_models  # noqa: F401  (enregistre les tables dans Base.metadata)
from app.config import get_settings
from app.database import Base, make_engine

logger = logging.getLogger("create_db")


def ensure_database(url: URL) -> bool:
    """Crée la base PostgreSQL si elle n'existe pas. Renvoie True si elle a été créée."""
    if url.get_backend_name() != "postgresql":
        return False
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": url.database}
            ).scalar()
            if not exists:
                conn.execute(text(f'CREATE DATABASE "{url.database}"'))
                logger.info("Base %s créée", url.database)
                return True
    finally:
        admin.dispose()
    return False


def create_tables(database_url: str, drop: bool = False) -> list[str]:
    engine = make_engine(database_url)
    try:
        if drop:
            Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)
    finally:
        engine.dispose()
    return sorted(Base.metadata.tables)


def dump_sql() -> str:
    """DDL PostgreSQL généré depuis les modèles ORM."""
    dialect = postgresql.dialect()
    parts = [
        "-- Schéma de la base attrition (généré par `python -m db.create_db --dump-sql`).",
        "-- Ne pas éditer à la main : modifier app/db_models.py puis régénérer.",
        "",
    ]
    for table in Base.metadata.sorted_tables:
        ddl = str(CreateTable(table, if_not_exists=True).compile(dialect=dialect)).strip()
        parts.append(ddl + ";\n")
        for index in sorted(table.indexes, key=lambda i: i.name):
            parts.append(str(CreateIndex(index, if_not_exists=True).compile(dialect=dialect)) + ";")
        parts.append("")
    return "\n".join(parts).rstrip() + "\n"


def main(argv: list[str] | None = None) -> list[str]:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Création de la base et des tables")
    parser.add_argument("--database-url", default=None)
    parser.add_argument("--drop", action="store_true", help="Supprime les tables avant création")
    parser.add_argument("--dump-sql", type=Path, default=None, help="Écrit le DDL et s'arrête")
    args = parser.parse_args(argv)

    if args.dump_sql:
        args.dump_sql.write_text(dump_sql(), encoding="utf-8")
        logger.info("DDL écrit dans %s", args.dump_sql)
        return []

    database_url = args.database_url or get_settings().database_url
    ensure_database(make_url(database_url))
    tables = create_tables(database_url, drop=args.drop)
    logger.info("Tables disponibles : %s", ", ".join(tables))
    return tables


if __name__ == "__main__":
    main()
