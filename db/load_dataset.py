"""Insertion du dataset complet TechNova dans les tables du référentiel.

Usage :
    python -m db.load_dataset [--data-dir data/raw] [--replace]

Idempotent : sans ``--replace``, les employés déjà présents sont ignorés.
"""

import argparse
import logging
from pathlib import Path

import pandas as pd
from sqlalchemy import delete, insert, select
from sqlalchemy.orm import Session

from app.config import ROOT_DIR, get_settings
from app.database import Base, make_engine
from app.db_models import Employee, Evaluation, Survey
from app.ml.data_prep import clean_all, load_raw

logger = logging.getLogger("load_dataset")

EMPLOYEE_COLS = [c.name for c in Employee.__table__.columns]
EVAL_COLS = [c.name for c in Evaluation.__table__.columns]
SURVEY_COLS = [c.name for c in Survey.__table__.columns]


def _records(df: pd.DataFrame, cols: list[str], skip: set[int]) -> list[dict]:
    df = df[~df["id_employee"].isin(skip)][cols]
    # conversion des types numpy -> types Python natifs pour le driver
    return [
        {k: (v.item() if hasattr(v, "item") else v) for k, v in row.items()} for row in df.to_dict("records")
    ]


def load(session: Session, data_dir: str | Path, replace: bool = False) -> dict[str, int]:
    cleaned = clean_all(load_raw(data_dir))
    if replace:
        for model in (Survey, Evaluation, Employee):
            session.execute(delete(model))
    existing = set(session.scalars(select(Employee.id_employee)))
    counts = {
        "employees": _records(cleaned["sirh"], EMPLOYEE_COLS, existing),
        "evaluations": _records(cleaned["eval"], EVAL_COLS, existing),
        "surveys": _records(cleaned["sondage"], SURVEY_COLS, existing),
    }
    for model, key in ((Employee, "employees"), (Evaluation, "evaluations"), (Survey, "surveys")):
        if counts[key]:
            session.execute(insert(model), counts[key])
    session.commit()
    return {k: len(v) for k, v in counts.items()}


def main(argv: list[str] | None = None) -> dict[str, int]:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Charge le dataset dans la base")
    parser.add_argument("--data-dir", type=Path, default=ROOT_DIR / "data" / "raw")
    parser.add_argument("--database-url", default=None)
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args(argv)

    engine = make_engine(args.database_url or get_settings().database_url)
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as session:
            inserted = load(session, args.data_dir, replace=args.replace)
    finally:
        engine.dispose()
    logger.info("Lignes insérées : %s", inserted)
    return inserted


if __name__ == "__main__":
    main()
