from pydantic import BaseModel

class EmployeeInput(BaseModel):
    revenu_mensuel: float
    nombre_experiences_precedentes: int
    age: int
    note_evaluation_actuelle: float
    note_evaluation_precedente: float
    satisfaction_employee_equilibre_pro_perso: int
    distance_domicile_travail: float
    genre: str          # "F" ou "M"
    departement: str    # "Commercial", "Consulting", "R&D"

class PredictionOutput(BaseModel):
    prediction: int
    label: str  
    probabilite_attrition: float