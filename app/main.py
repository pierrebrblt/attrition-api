"""Point d'entrée FastAPI. Documentation interactive : /docs (Swagger) et /redoc."""

import logging
from collections.abc import Iterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Path, Query, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app import __version__
from app.config import Settings, get_settings
from app.database import Base, make_engine, make_session_factory
from app.ml.model import AttritionModel
from app.schemas import (
    BatchInput,
    BatchOutput,
    EmployeeInput,
    EmployeePredictionOutput,
    ErrorOutput,
    HealthOutput,
    ModelInfo,
    PredictionList,
    PredictionOutput,
    PredictionRecord,
)
from app.security import require_api_key
from app.services import (
    PredictionError,
    employee_features,
    get_employee,
    get_request,
    list_requests,
    predict_and_store,
    to_output,
    to_record,
)

logger = logging.getLogger("app")

TAGS = [
    {"name": "Statut", "description": "Disponibilité de l'API, du modèle et de la base."},
    {"name": "Prédiction", "description": "Prédiction du risque d'attrition (tracée en base)."},
    {"name": "Historique", "description": "Consultation des inputs/outputs enregistrés."},
]

AUTH_RESPONSES = {
    401: {"model": ErrorOutput, "description": "Clé d'API manquante"},
    403: {"model": ErrorOutput, "description": "Clé d'API invalide"},
}


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    logging.basicConfig(level=settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        engine = make_engine(settings.database_url)
        if settings.auto_create_tables:
            Base.metadata.create_all(engine)
        app.state.engine = engine
        app.state.session_factory = make_session_factory(engine)
        if getattr(app.state, "model", None) is None:
            try:
                app.state.model = AttritionModel.load(
                    settings.model_path, settings.metrics_path, settings.decision_threshold
                )
            except Exception:  # l'API démarre en mode dégradé, visible sur /health
                logger.exception("Impossible de charger le modèle")
                app.state.model = None
        if not settings.auth_enabled:
            logger.warning("Aucune clé d'API configurée : authentification DÉSACTIVÉE (%s)", settings.app_env)
        yield
        engine.dispose()

    app = FastAPI(
        title="Attrition API - Futurisys",
        description=(
            "Prédiction du risque de départ d'un employé (modèle TechNova Partners).\n\n"
            "**Authentification** : en-tête `X-API-Key` sur les routes de prédiction et d'historique.\n\n"
            "**Traçabilité** : chaque input et chaque output du modèle est enregistré dans PostgreSQL "
            "(`prediction_requests` / `prediction_results`)."
        ),
        version=__version__,
        openapi_tags=TAGS,
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.model = None

    # ----------------------------------------------------------------------------- dépendances
    def get_db(request: Request) -> Iterator[Session]:
        session = request.app.state.session_factory()
        try:
            yield session
        finally:
            session.close()

    def get_model(request: Request) -> AttritionModel:
        model = request.app.state.model
        if model is None:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Modèle non disponible")
        return model

    DB = Annotated[Session, Depends(get_db)]
    Model = Annotated[AttritionModel, Depends(get_model)]
    Client = Annotated[str, Depends(require_api_key)]

    # ------------------------------------------------------------------------ gestion d'erreurs
    @app.exception_handler(PredictionError)
    async def _prediction_error(_: Request, exc: PredictionError):
        return JSONResponse(status_code=500, content={"detail": str(exc), "request_ids": exc.request_ids})

    @app.exception_handler(SQLAlchemyError)
    async def _db_error(_: Request, exc: SQLAlchemyError):
        logger.exception("Erreur base de données", exc_info=exc)
        return JSONResponse(status_code=503, content={"detail": "Base de données indisponible"})

    # ---------------------------------------------------------------------------------- routes
    @app.get("/", tags=["Statut"])
    def root():
        return {
            "message": "API Attrition opérationnelle",
            "version": __version__,
            "docs": "/docs",
        }

    @app.get("/health", tags=["Statut"], response_model=HealthOutput)
    def health(request: Request):
        try:
            with request.app.state.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            db_status = "ok"
        except Exception:
            db_status = "error"
        model = request.app.state.model
        ok = model is not None and db_status == "ok"
        return {
            "status": "ok" if ok else "degraded",
            "environment": settings.app_env,
            "api_version": __version__,
            "model_loaded": model is not None,
            "model_version": model.version if model else None,
            "database": db_status,
        }

    @app.get("/model/info", tags=["Statut"], response_model=ModelInfo, responses=AUTH_RESPONSES)
    def model_info(model: Model, _: Client):
        return model.info()

    @app.post(
        "/predict",
        tags=["Prédiction"],
        response_model=PredictionOutput,
        responses={**AUTH_RESPONSES, 503: {"model": ErrorOutput}},
        summary="Prédire l'attrition d'un employé",
    )
    def predict(employee: EmployeeInput, db: DB, model: Model, client: Client):
        [req] = predict_and_store(db, model, [employee.model_dump()], "api", client)
        return to_output(req)

    @app.post(
        "/predict/batch",
        tags=["Prédiction"],
        response_model=BatchOutput,
        responses=AUTH_RESPONSES,
        summary="Prédire l'attrition d'une liste d'employés",
    )
    def predict_batch(payload: BatchInput, db: DB, model: Model, client: Client):
        if len(payload.employees) > settings.max_batch_size:
            raise HTTPException(
                status.HTTP_413_CONTENT_TOO_LARGE,
                f"Batch limité à {settings.max_batch_size} employés",
            )
        reqs = predict_and_store(db, model, [e.model_dump() for e in payload.employees], "batch", client)
        return {"count": len(reqs), "predictions": [to_output(r) for r in reqs]}

    @app.post(
        "/predict/employee/{id_employee}",
        tags=["Prédiction"],
        response_model=EmployeePredictionOutput,
        responses={**AUTH_RESPONSES, 404: {"model": ErrorOutput}},
        summary="Prédire l'attrition d'un employé du référentiel (features lues en base)",
    )
    def predict_employee(db: DB, model: Model, client: Client, id_employee: int = Path(ge=1)):
        emp = get_employee(db, id_employee)
        if emp is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"Employé {id_employee} introuvable")
        try:
            features = employee_features(emp)
        except LookupError as exc:
            raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
        actual = emp.survey.a_quitte_l_entreprise
        [req] = predict_and_store(db, model, [features], "employee", client, [id_employee])
        return {**to_output(req), "id_employee": id_employee, "a_quitte_l_entreprise": actual}

    @app.get(
        "/predictions",
        tags=["Historique"],
        response_model=PredictionList,
        responses=AUTH_RESPONSES,
        summary="Lister les prédictions enregistrées",
    )
    def predictions(
        db: DB,
        _: Client,
        limit: int = Query(50, ge=1, le=500),
        offset: int = Query(0, ge=0),
        id_employee: int | None = Query(None, ge=1),
        source: str | None = Query(None, pattern="^(api|employee|batch)$"),
    ):
        total, rows = list_requests(db, limit, offset, id_employee, source)
        return {"total": total, "limit": limit, "offset": offset, "items": [to_record(r) for r in rows]}

    @app.get(
        "/predictions/{request_id}",
        tags=["Historique"],
        response_model=PredictionRecord,
        responses={**AUTH_RESPONSES, 404: {"model": ErrorOutput}},
        summary="Détail d'une prédiction (input + output)",
    )
    def prediction_detail(db: DB, _: Client, request_id: int = Path(ge=1)):
        req = get_request(db, request_id)
        if req is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"Requête {request_id} introuvable")
        return to_record(req)

    return app


app = create_app()
