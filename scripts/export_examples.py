"""Exporte les inputs/outputs du modèle enregistrés en base vers un CSV d'exemple.

Usage : ``python -m scripts.export_examples [--out data/examples/predictions_examples.csv] [--limit 50]``
"""

import argparse
import csv
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import ROOT_DIR, get_settings
from app.database import make_engine
from app.ml.data_prep import FEATURES
from app.services import list_requests, to_record

COLUMNS = [
    "request_id",
    "created_at",
    "source",
    "status",
    "id_employee",
    *FEATURES,
    "prediction",
    "label",
    "probabilite_attrition",
    "model_version",
    "latency_ms",
]


def export(session: Session, out: Path, limit: int) -> int:
    _, rows = list_requests(session, limit=limit, offset=0)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS)
        writer.writeheader()
        for req in reversed(rows):
            rec = to_record(req)
            writer.writerow({**{k: rec[k] for k in COLUMNS if k in rec}, **rec["inputs"]})
    return len(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out", type=Path, default=ROOT_DIR / "data" / "examples" / "predictions_examples.csv"
    )
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--database-url", default=None)
    args = parser.parse_args(argv)
    engine = make_engine(args.database_url or get_settings().database_url)
    try:
        with Session(engine) as session:
            n = export(session, args.out, args.limit)
    finally:
        engine.dispose()
    print(f"{n} lignes exportées vers {args.out}")
    return n


if __name__ == "__main__":
    main()
