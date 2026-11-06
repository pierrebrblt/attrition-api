"""Interrogation de la base (référentiel + traçabilité) depuis Python.

Usage :
    python -m scripts.query_db stats
    python -m scripts.query_db employee 42
    python -m scripts.query_db history --limit 10
    python -m scripts.query_db errors
"""

import argparse
import json

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import make_engine
from app.db_models import Employee, PredictionRequest, PredictionResult, Survey
from app.services import employee_features, get_employee, list_requests, to_record


def stats(session: Session) -> dict:
    by_dept = session.execute(
        select(
            Employee.departement,
            func.count(),
            func.avg(case((Survey.a_quitte_l_entreprise, 1.0), else_=0.0)),
        )
        .join(Survey, Survey.id_employee == Employee.id_employee)
        .group_by(Employee.departement)
        .order_by(Employee.departement)
    ).all()
    return {
        "employees": session.scalar(select(func.count()).select_from(Employee)),
        "prediction_requests": session.scalar(select(func.count()).select_from(PredictionRequest)),
        "prediction_results": session.scalar(select(func.count()).select_from(PredictionResult)),
        "errors": session.scalar(
            select(func.count()).select_from(PredictionRequest).where(PredictionRequest.status == "error")
        ),
        "attrition_by_department": {d: {"effectif": n, "taux": round(float(t), 4)} for d, n, t in by_dept},
    }


def employee(session: Session, id_employee: int) -> dict | None:
    emp = get_employee(session, id_employee)
    if emp is None:
        return None
    _, history = list_requests(session, limit=20, offset=0, id_employee=id_employee)
    return {
        "id_employee": id_employee,
        "poste": emp.poste,
        "features": employee_features(emp),
        "a_quitte_l_entreprise": emp.survey.a_quitte_l_entreprise,
        "predictions": [to_record(r) for r in history],
    }


def history(session: Session, limit: int) -> list[dict]:
    return [to_record(r) for r in list_requests(session, limit=limit, offset=0)[1]]


def errors(session: Session) -> list[dict]:
    rows = session.scalars(select(PredictionRequest).where(PredictionRequest.status == "error"))
    return [{"request_id": r.id, "created_at": r.created_at, "error": r.error_message} for r in rows]


def main(argv: list[str] | None = None):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--database-url", default=None)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("stats")
    p_emp = sub.add_parser("employee")
    p_emp.add_argument("id_employee", type=int)
    p_hist = sub.add_parser("history")
    p_hist.add_argument("--limit", type=int, default=10)
    sub.add_parser("errors")
    args = parser.parse_args(argv)

    engine = make_engine(args.database_url or get_settings().database_url)
    try:
        with Session(engine) as session:
            if args.cmd == "stats":
                result = stats(session)
            elif args.cmd == "employee":
                result = employee(session, args.id_employee)
            elif args.cmd == "history":
                result = history(session, args.limit)
            else:
                result = errors(session)
    finally:
        engine.dispose()
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    return result


if __name__ == "__main__":
    main()
