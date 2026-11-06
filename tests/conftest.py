"""Fixtures partagées.

La base de test est PostgreSQL si ``TEST_DATABASE_URL`` est défini (cas de la CI), sinon un
fichier SQLite temporaire. Le référentiel est chargé une fois par session ; les tables de
traçabilité sont vidées avant chaque test pour garantir des résultats reproductibles.
"""

import os
from pathlib import Path

import pytest

TEST_API_KEY = "test-key-0123456789abcdef"
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("API_KEYS", TEST_API_KEY)

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import delete  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.config import ROOT_DIR, Settings  # noqa: E402
from app.database import Base, make_engine  # noqa: E402
from app.db_models import PredictionRequest, PredictionResult  # noqa: E402
from app.main import create_app  # noqa: E402
from app.ml.data_prep import load_dataset  # noqa: E402
from app.ml.model import AttritionModel  # noqa: E402
from db.load_dataset import load  # noqa: E402

DATA_DIR = ROOT_DIR / "data" / "raw"
MODEL_PATH = ROOT_DIR / "models" / "attrition_model.joblib"
METRICS_PATH = ROOT_DIR / "models" / "metrics.json"

VALID_EMPLOYEE = {
    "revenu_mensuel": 3500,
    "nombre_experiences_precedentes": 3,
    "age": 35,
    "note_evaluation_actuelle": 3,
    "note_evaluation_precedente": 3,
    "satisfaction_employee_equilibre_pro_perso": 2,
    "distance_domicile_travail": 15,
    "genre": "M",
    "departement": "Consulting",
}


@pytest.fixture(scope="session")
def database_url(tmp_path_factory) -> str:
    url = os.environ.get("TEST_DATABASE_URL")
    if url:
        return url
    return f"sqlite:///{tmp_path_factory.mktemp('db') / 'test.db'}"


@pytest.fixture(scope="session")
def is_postgres(database_url) -> bool:
    return database_url.startswith("postgresql")


@pytest.fixture(scope="session")
def engine(database_url):
    eng = make_engine(database_url)
    Base.metadata.drop_all(eng)
    Base.metadata.create_all(eng)
    with Session(eng) as s:
        load(s, DATA_DIR)
    yield eng
    Base.metadata.drop_all(eng)
    eng.dispose()


@pytest.fixture
def db(engine):
    with Session(engine, expire_on_commit=False) as session:
        session.execute(delete(PredictionResult))
        session.execute(delete(PredictionRequest))
        session.commit()
        yield session


@pytest.fixture(scope="session")
def model() -> AttritionModel:
    return AttritionModel.load(MODEL_PATH, METRICS_PATH)


@pytest.fixture(scope="session")
def dataset():
    return load_dataset(DATA_DIR)


@pytest.fixture
def settings(database_url) -> Settings:
    return Settings(
        app_env="test",
        database_url=database_url,
        api_keys=TEST_API_KEY,
        model_path=MODEL_PATH,
        metrics_path=METRICS_PATH,
        max_batch_size=10,
    )


@pytest.fixture
def client(settings, db):
    """Client HTTP sur une instance fraîche de l'API (lifespan exécuté)."""
    with TestClient(create_app(settings)) as c:
        c.headers.update({"X-API-Key": TEST_API_KEY})
        yield c


@pytest.fixture
def anon_client(settings, db):
    with TestClient(create_app(settings)) as c:
        yield c


@pytest.fixture
def data_dir() -> Path:
    return DATA_DIR
