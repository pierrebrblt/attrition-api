"""Tests fonctionnels des endpoints, y compris la traçabilité en base."""

import pytest
from sqlalchemy import func, select

from app.db_models import PredictionRequest, PredictionResult
from app.security import fingerprint
from tests.conftest import TEST_API_KEY, VALID_EMPLOYEE


def count(db, model):
    db.expire_all()
    return db.scalar(select(func.count()).select_from(model))


# ------------------------------------------------------------------------------------ statut
def test_root(anon_client):
    r = anon_client.get("/")
    assert r.status_code == 200
    assert r.json()["message"] == "API Attrition opérationnelle"


def test_health(anon_client):
    body = anon_client.get("/health").json()
    assert body["status"] == "ok"
    assert body["model_loaded"] is True
    assert body["database"] == "ok"
    assert body["environment"] == "test"


def test_openapi_documents_endpoints(anon_client):
    spec = anon_client.get("/openapi.json").json()
    for path in ["/predict", "/predict/batch", "/predict/employee/{id_employee}", "/predictions", "/health"]:
        assert path in spec["paths"]
    assert "APIKeyHeader" in spec["components"]["securitySchemes"]
    assert spec["components"]["schemas"]["EmployeeInput"]["examples"]


def test_swagger_ui(anon_client):
    assert anon_client.get("/docs").status_code == 200


def test_model_info(client):
    body = client.get("/model/info").json()
    assert body["model_version"] == "1.0.0"
    assert len(body["features"]) == 9


# ------------------------------------------------------------------------------ authentification
@pytest.mark.parametrize(
    "method, path, body",
    [
        ("post", "/predict", VALID_EMPLOYEE),
        ("post", "/predict/batch", {"employees": [VALID_EMPLOYEE]}),
        ("post", "/predict/employee/1", None),
        ("get", "/predictions", None),
        ("get", "/predictions/1", None),
        ("get", "/model/info", None),
    ],
)
def test_protected_routes_require_key(anon_client, method, path, body):
    r = getattr(anon_client, method)(path, json=body) if body else getattr(anon_client, method)(path)
    assert r.status_code == 401
    r = getattr(anon_client, method)(
        path, headers={"X-API-Key": "mauvaise"}, **({"json": body} if body else {})
    )
    assert r.status_code == 403


def test_rejected_calls_are_not_stored(anon_client, db):
    anon_client.post("/predict", json=VALID_EMPLOYEE)
    assert count(db, PredictionRequest) == 0


# ---------------------------------------------------------------------------------- /predict
def test_predict_ok_and_traced(client, db):
    r = client.post("/predict", json=VALID_EMPLOYEE)
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {
        "request_id",
        "prediction",
        "label",
        "probabilite_attrition",
        "model_version",
        "created_at",
    }
    assert body["label"] == ("Oui" if body["prediction"] == 1 else "Non")
    assert 0 <= body["probabilite_attrition"] <= 1

    db.expire_all()
    req = db.get(PredictionRequest, body["request_id"])
    assert req.status == "done" and req.source == "api"
    assert req.client_id == fingerprint(TEST_API_KEY)
    assert req.age == VALID_EMPLOYEE["age"] and req.departement == "Consulting"
    assert req.result.probabilite_attrition == body["probabilite_attrition"]
    assert req.result.model_version == "1.0.0"
    assert req.result.latency_ms >= 0


def test_predict_is_reproducible(client):
    p1 = client.post("/predict", json=VALID_EMPLOYEE).json()
    p2 = client.post("/predict", json=VALID_EMPLOYEE).json()
    assert p1["probabilite_attrition"] == p2["probabilite_attrition"]
    assert p1["request_id"] != p2["request_id"]


def test_predict_matches_model(client, model):
    api = client.post("/predict", json=VALID_EMPLOYEE).json()
    assert api["probabilite_attrition"] == model.predict([VALID_EMPLOYEE])[0].probabilite_attrition


@pytest.mark.parametrize(
    "patch",
    [
        {"age": "pas_un_nombre"},
        {"departement": "R&D"},
        {"genre": "X"},
        {"note_evaluation_actuelle": 9},
        {"revenu_mensuel": -1},
        {"inconnu": 1},
    ],
)
def test_predict_validation_errors(client, db, patch):
    r = client.post("/predict", json={**VALID_EMPLOYEE, **patch})
    assert r.status_code == 422
    assert "detail" in r.json()
    assert count(db, PredictionRequest) == 0


def test_predict_missing_field(client):
    data = {k: v for k, v in VALID_EMPLOYEE.items() if k != "age"}
    r = client.post("/predict", json=data)
    assert r.status_code == 422
    assert r.json()["detail"][0]["loc"] == ["body", "age"]


def test_predict_empty_and_malformed_body(client):
    assert client.post("/predict", json={}).status_code == 422
    assert (
        client.post(
            "/predict", content="pas du json", headers={"Content-Type": "application/json"}
        ).status_code
        == 422
    )


def test_predict_model_failure_is_traced(client, db):
    class Broken:
        version, threshold = "broken", 0.5

        def predict(self, _):
            raise RuntimeError("boom")

    client.app.state.model = Broken()
    r = client.post("/predict", json=VALID_EMPLOYEE)
    assert r.status_code == 500
    [rid] = r.json()["request_ids"]
    db.expire_all()
    req = db.get(PredictionRequest, rid)
    assert req.status == "error" and "boom" in req.error_message
    assert count(db, PredictionResult) == 0


def test_predict_model_unavailable(client):
    client.app.state.model = None
    assert client.post("/predict", json=VALID_EMPLOYEE).status_code == 503
    assert client.get("/health").json()["status"] == "degraded"


def test_database_down_returns_503(client):
    from sqlalchemy.exc import OperationalError

    def broken_factory():
        raise OperationalError("SELECT 1", {}, Exception("down"))

    client.app.state.session_factory = broken_factory
    r = client.post("/predict", json=VALID_EMPLOYEE)
    assert r.status_code == 503


def test_health_reports_db_error(client):
    class BadEngine:
        def connect(self):
            raise RuntimeError("down")

        def dispose(self):
            pass

    real = client.app.state.engine
    client.app.state.engine = BadEngine()
    try:
        assert client.get("/health").json()["database"] == "error"
    finally:
        client.app.state.engine = real


# ---------------------------------------------------------------------------- /predict/batch
def test_batch(client, db):
    young = {**VALID_EMPLOYEE, "age": 22, "revenu_mensuel": 1500}
    r = client.post("/predict/batch", json={"employees": [VALID_EMPLOYEE, young]})
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 2
    assert len({p["request_id"] for p in body["predictions"]}) == 2
    assert count(db, PredictionResult) == 2


def test_batch_too_large(client, db):
    r = client.post("/predict/batch", json={"employees": [VALID_EMPLOYEE] * 11})
    assert r.status_code == 413
    assert count(db, PredictionRequest) == 0


def test_batch_one_invalid_rejects_all(client, db):
    r = client.post("/predict/batch", json={"employees": [VALID_EMPLOYEE, {**VALID_EMPLOYEE, "age": 3}]})
    assert r.status_code == 422
    assert r.json()["detail"][0]["loc"][:3] == ["body", "employees", 1]
    assert count(db, PredictionRequest) == 0


# ------------------------------------------------------------------------- /predict/employee
def test_predict_employee_reads_features_from_db(client, db, dataset, model):
    row = dataset.iloc[0]
    r = client.post(f"/predict/employee/{row.id_employee}")
    assert r.status_code == 200
    body = r.json()
    assert body["id_employee"] == row.id_employee
    assert body["a_quitte_l_entreprise"] == bool(row.a_quitte_l_entreprise)
    expected = model.predict([row[model.pipeline.feature_names_in_].to_dict()])[0]
    assert body["probabilite_attrition"] == expected.probabilite_attrition
    db.expire_all()
    req = db.get(PredictionRequest, body["request_id"])
    assert req.source == "employee" and req.id_employee == row.id_employee


def test_predict_employee_not_found(client):
    assert client.post("/predict/employee/999999").status_code == 404


def test_predict_employee_invalid_id(client):
    assert client.post("/predict/employee/0").status_code == 422
    assert client.post("/predict/employee/abc").status_code == 422


# ------------------------------------------------------------------------------- historique
def test_history_list_and_filters(client):
    client.post("/predict", json=VALID_EMPLOYEE)
    client.post("/predict/employee/1")
    client.post("/predict/employee/2")

    body = client.get("/predictions").json()
    assert body["total"] == 3
    assert [i["request_id"] for i in body["items"]] == sorted(
        (i["request_id"] for i in body["items"]), reverse=True
    )

    only_emp = client.get("/predictions", params={"source": "employee"}).json()
    assert only_emp["total"] == 2
    assert client.get("/predictions", params={"id_employee": 2}).json()["total"] == 1

    page = client.get("/predictions", params={"limit": 1, "offset": 1}).json()
    assert len(page["items"]) == 1 and page["total"] == 3


def test_history_bad_params(client):
    assert client.get("/predictions", params={"limit": 0}).status_code == 422
    assert client.get("/predictions", params={"source": "hack"}).status_code == 422


def test_history_detail(client):
    rid = client.post("/predict", json=VALID_EMPLOYEE).json()["request_id"]
    body = client.get(f"/predictions/{rid}").json()
    assert body["inputs"]["age"] == VALID_EMPLOYEE["age"]
    assert body["status"] == "done" and body["label"] in ("Oui", "Non")


def test_history_detail_not_found(client):
    assert client.get("/predictions/987654").status_code == 404


def test_auth_disabled_in_dev(settings, db):
    from fastapi.testclient import TestClient

    from app.main import create_app

    with TestClient(create_app(settings.model_copy(update={"api_keys": ""}))) as c:
        r = c.post("/predict", json=VALID_EMPLOYEE)
        assert r.status_code == 200
    db.expire_all()
    assert db.get(PredictionRequest, r.json()["request_id"]).client_id == "anonymous"


def test_startup_without_model_file(settings, db, tmp_path):
    from fastapi.testclient import TestClient

    from app.main import create_app

    with TestClient(create_app(settings.model_copy(update={"model_path": tmp_path / "x.joblib"}))) as c:
        assert c.get("/health").json()["model_loaded"] is False
