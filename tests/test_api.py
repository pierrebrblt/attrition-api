import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

# --- Données de test ---
VALID_EMPLOYEE = {
    "revenu_mensuel": 3500,
    "nombre_experiences_precedentes": 3,
    "age": 35,
    "note_evaluation_actuelle": 3,
    "note_evaluation_precedente": 3,
    "satisfaction_employee_equilibre_pro_perso": 2,
    "distance_domicile_travail": 15,
    "genre": "M",
    "departement": "Consulting"
}

# --- Tests endpoint racine ---
def test_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "API Attrition opérationnelle"}

# --- Tests endpoint /predict ---
def test_predict_status_code():
    response = client.post("/predict", json=VALID_EMPLOYEE)
    assert response.status_code == 200

def test_predict_response_keys():
    response = client.post("/predict", json=VALID_EMPLOYEE)
    data = response.json()
    assert "prediction" in data
    assert "label" in data
    assert "probabilite_attrition" in data

def test_predict_response_types():
    response = client.post("/predict", json=VALID_EMPLOYEE)
    data = response.json()
    assert isinstance(data["prediction"], int)
    assert isinstance(data["label"], str)
    assert isinstance(data["probabilite_attrition"], float)

def test_predict_label_coherence():
    response = client.post("/predict", json=VALID_EMPLOYEE)
    data = response.json()
    if data["prediction"] == 1:
        assert data["label"] == "Oui"
    else:
        assert data["label"] == "Non"

def test_predict_probability_range():
    response = client.post("/predict", json=VALID_EMPLOYEE)
    data = response.json()
    assert 0.0 <= data["probabilite_attrition"] <= 1.0

def test_predict_missing_field():
    incomplete = VALID_EMPLOYEE.copy()
    del incomplete["age"]
    response = client.post("/predict", json=incomplete)
    assert response.status_code == 422  # Validation error

def test_predict_invalid_type():
    invalid = VALID_EMPLOYEE.copy()
    invalid["age"] = "pas_un_nombre"
    response = client.post("/predict", json=invalid)
    assert response.status_code == 422