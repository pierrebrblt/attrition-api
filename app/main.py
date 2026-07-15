from fastapi import FastAPI
from app.schemas import EmployeeInput, PredictionOutput
from app.model import predict_attrition

app = FastAPI(
    title="Attrition API",
    description="API de prédiction du risque de départ d'un employé - TechNova Partners",
    version="1.0"
)

@app.get("/")
def root():
    return {"message": "API Attrition opérationnelle"}

@app.post("/predict", response_model=PredictionOutput)
def predict(employee: EmployeeInput):
    result = predict_attrition(employee.model_dump())
    return result