"""Service de prédiction : toute interaction avec le modèle passe par la base de données.

Séquence pour chaque prédiction :

1. l'input validé est inséré dans ``prediction_requests`` (statut ``pending``) ;
2. les features sont **relues depuis la ligne en base** et envoyées au modèle ;
3. l'output est inséré dans ``prediction_results`` et la requête passe en ``done`` ;
4. en cas d'échec du modèle, la requête est conservée avec le statut ``error`` et le message.
"""

import logging
import time

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.db_models import Employee, PredictionRequest, PredictionResult
from app.ml.data_prep import FEATURES
from app.ml.model import AttritionModel

logger = logging.getLogger(__name__)


class PredictionError(RuntimeError):
    def __init__(self, message: str, request_ids: list[int]):
        super().__init__(message)
        self.request_ids = request_ids


def request_features(req: PredictionRequest) -> dict:
    return {f: getattr(req, f) for f in FEATURES}


def predict_and_store(
    db: Session,
    model: AttritionModel,
    inputs: list[dict],
    source: str,
    client_id: str,
    id_employees: list[int | None] | None = None,
) -> list[PredictionRequest]:
    """Enregistre les inputs, prédit à partir des lignes stockées, enregistre les outputs."""
    id_employees = id_employees or [None] * len(inputs)
    requests = [
        PredictionRequest(source=source, status="pending", client_id=client_id, id_employee=emp, **features)
        for features, emp in zip(inputs, id_employees, strict=True)
    ]
    db.add_all(requests)
    db.commit()  # l'input est tracé même si l'inférence échoue ensuite

    stored = [request_features(r) for r in requests]
    start = time.perf_counter()
    try:
        outcomes = model.predict(stored)
    except Exception as exc:
        logger.exception("Échec de l'inférence pour les requêtes %s", [r.id for r in requests])
        for r in requests:
            r.status = "error"
            r.error_message = f"{type(exc).__name__}: {exc}"[:2000]
        db.commit()
        raise PredictionError(
            "Le modèle n'a pas pu produire de prédiction", [r.id for r in requests]
        ) from exc
    latency_ms = (time.perf_counter() - start) * 1000 / len(requests)

    for req, out in zip(requests, outcomes, strict=True):
        req.status = "done"
        req.result = PredictionResult(
            prediction=out.prediction,
            label=out.label,
            probabilite_attrition=out.probabilite_attrition,
            decision_threshold=model.threshold,
            model_version=model.version,
            latency_ms=round(latency_ms, 3),
        )
    db.commit()
    return requests


def employee_features(employee: Employee) -> dict:
    """Extrait les 9 features du modèle depuis les tables du référentiel."""
    ev, so = employee.evaluation, employee.survey
    if ev is None or so is None:
        raise LookupError(f"Données incomplètes pour l'employé {employee.id_employee}")
    return {
        "revenu_mensuel": employee.revenu_mensuel,
        "nombre_experiences_precedentes": employee.nombre_experiences_precedentes,
        "age": employee.age,
        "note_evaluation_actuelle": ev.note_evaluation_actuelle,
        "note_evaluation_precedente": ev.note_evaluation_precedente,
        "satisfaction_employee_equilibre_pro_perso": ev.satisfaction_employee_equilibre_pro_perso,
        "distance_domicile_travail": so.distance_domicile_travail,
        "genre": employee.genre,
        "departement": employee.departement,
    }


def get_employee(db: Session, id_employee: int) -> Employee | None:
    stmt = (
        select(Employee)
        .options(selectinload(Employee.evaluation), selectinload(Employee.survey))
        .where(Employee.id_employee == id_employee)
    )
    return db.scalars(stmt).first()


def list_employees(db: Session, ids: list[int] | None = None) -> list[Employee]:
    stmt = select(Employee).options(selectinload(Employee.evaluation), selectinload(Employee.survey))
    if ids:
        stmt = stmt.where(Employee.id_employee.in_(ids))
    return list(db.scalars(stmt.order_by(Employee.id_employee)))


def get_request(db: Session, request_id: int) -> PredictionRequest | None:
    stmt = (
        select(PredictionRequest)
        .options(selectinload(PredictionRequest.result))
        .where(PredictionRequest.id == request_id)
    )
    return db.scalars(stmt).first()


def list_requests(
    db: Session, limit: int, offset: int, id_employee: int | None = None, source: str | None = None
) -> tuple[int, list[PredictionRequest]]:
    base = select(PredictionRequest)
    if id_employee is not None:
        base = base.where(PredictionRequest.id_employee == id_employee)
    if source is not None:
        base = base.where(PredictionRequest.source == source)
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = db.scalars(
        base.options(selectinload(PredictionRequest.result))
        .order_by(PredictionRequest.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return total, list(rows)


def to_record(req: PredictionRequest) -> dict:
    res = req.result
    return {
        "request_id": req.id,
        "created_at": req.created_at,
        "source": req.source,
        "status": req.status,
        "error_message": req.error_message,
        "client_id": req.client_id,
        "id_employee": req.id_employee,
        "inputs": request_features(req),
        "prediction": res.prediction if res else None,
        "label": res.label if res else None,
        "probabilite_attrition": res.probabilite_attrition if res else None,
        "model_version": res.model_version if res else None,
        "latency_ms": res.latency_ms if res else None,
    }


def to_output(req: PredictionRequest) -> dict:
    res = req.result
    return {
        "request_id": req.id,
        "prediction": res.prediction,
        "label": res.label,
        "probabilite_attrition": res.probabilite_attrition,
        "model_version": res.model_version,
        "created_at": res.created_at,
    }
