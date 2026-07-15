import joblib
import pandas as pd
from pathlib import Path

MODEL_PATH = Path(__file__).parent.parent / "models" / "attrition_model.pkl"

pipeline = joblib.load(MODEL_PATH)

FEATURE_ORDER = [
    "revenu_mensuel",
    "nombre_experiences_precedentes",
    "age",
    "note_evaluation_actuelle",
    "note_evaluation_precedente",
    "satisfaction_employee_equilibre_pro_perso",
    "distance_domicile_travail",
    "genre",
    "departement"
]

def predict_attrition(data: dict) -> dict:
    df = pd.DataFrame([data])[FEATURE_ORDER]
    prediction = pipeline.predict(df)[0]
    proba = pipeline.predict_proba(df)[0][1]
    return {
        "prediction": int(prediction),
        "label": "Oui" if prediction == 1 else "Non",
        "probabilite_attrition": round(float(proba), 4)
    }