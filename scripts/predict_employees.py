"""Prédiction en lot sur les employés du référentiel, en passant par la base.

Les features sont lues dans ``employees`` / ``evaluations`` / ``surveys``, chaque input est
enregistré dans ``prediction_requests`` et chaque output dans ``prediction_results``.

Usage : ``python -m scripts.predict_employees [--ids 1 2 3] [--limit 100]``
"""

import argparse
import logging

from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import Base, make_engine
from app.ml.model import AttritionModel
from app.services import employee_features, list_employees, predict_and_store

logger = logging.getLogger("predict_employees")


def run(
    session: Session, model: AttritionModel, ids: list[int] | None = None, limit: int | None = None
) -> dict:
    employees = list_employees(session, ids)[:limit]
    if not employees:
        return {"processed": 0, "predicted_attrition": 0, "accuracy_vs_actual": None}
    reqs = predict_and_store(
        session,
        model,
        [employee_features(e) for e in employees],
        source="batch",
        client_id="script:predict_employees",
        id_employees=[e.id_employee for e in employees],
    )
    actual = [e.survey.a_quitte_l_entreprise for e in employees]
    predicted = [r.result.prediction == 1 for r in reqs]
    correct = sum(a == p for a, p in zip(actual, predicted, strict=True))
    return {
        "processed": len(reqs),
        "predicted_attrition": sum(predicted),
        "accuracy_vs_actual": round(correct / len(reqs), 4),
    }


def main(argv: list[str] | None = None) -> dict:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ids", type=int, nargs="*", default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--database-url", default=None)
    args = parser.parse_args(argv)

    settings = get_settings()
    model = AttritionModel.load(settings.model_path, settings.metrics_path, settings.decision_threshold)
    engine = make_engine(args.database_url or settings.database_url)
    Base.metadata.create_all(engine)
    try:
        with Session(engine, expire_on_commit=False) as session:
            summary = run(session, model, args.ids, args.limit)
    finally:
        engine.dispose()
    logger.info("Résultat : %s", summary)
    return summary


if __name__ == "__main__":
    main()
