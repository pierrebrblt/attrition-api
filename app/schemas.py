"""Schémas Pydantic : validation des entrées et documentation OpenAPI des sorties.

Les bornes et catégories reflètent le domaine observé dans le dataset d'entraînement : le
pipeline (OneHotEncoder avec ``handle_unknown='error'``) planterait sur une catégorie inconnue,
c'est donc l'API qui la refuse proprement (HTTP 422) en amont.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Genre = Literal["F", "M"]
Departement = Literal["Commercial", "Consulting", "Ressources Humaines"]

EXAMPLE_EMPLOYEE = {
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


class EmployeeInput(BaseModel):
    """Caractéristiques d'un employé utilisées par le modèle."""

    model_config = ConfigDict(extra="forbid", json_schema_extra={"examples": [EXAMPLE_EMPLOYEE]})

    revenu_mensuel: float = Field(gt=0, le=100_000, description="Salaire mensuel brut (€)")
    nombre_experiences_precedentes: int = Field(ge=0, le=50, description="Nombre d'employeurs")
    age: int = Field(ge=16, le=80, description="Âge en années")
    note_evaluation_actuelle: int = Field(ge=1, le=4, description="Note d'évaluation (1 à 4)")
    note_evaluation_precedente: int = Field(ge=1, le=4, description="Note précédente (1 à 4)")
    satisfaction_employee_equilibre_pro_perso: int = Field(
        ge=1, le=4, description="Satisfaction équilibre vie pro/perso (1 à 4)"
    )
    distance_domicile_travail: float = Field(ge=0, le=500, description="Distance en km")
    genre: Genre = Field(description="'F' ou 'M'")
    departement: Departement = Field(description="Département de rattachement")


class BatchInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    employees: list[EmployeeInput] = Field(min_length=1, description="Liste d'employés")


class PredictionOutput(BaseModel):
    request_id: int = Field(description="Identifiant de la requête tracée en base")
    prediction: Literal[0, 1] = Field(description="1 = risque de départ")
    label: Literal["Oui", "Non"]
    probabilite_attrition: float = Field(ge=0, le=1)
    model_version: str
    created_at: datetime


class EmployeePredictionOutput(PredictionOutput):
    id_employee: int
    a_quitte_l_entreprise: bool = Field(description="Valeur réelle connue dans le référentiel")


class BatchOutput(BaseModel):
    count: int
    predictions: list[PredictionOutput]


class PredictionRecord(BaseModel):
    """Historique : input + output stockés en base."""

    model_config = ConfigDict(from_attributes=True)

    request_id: int
    created_at: datetime
    source: str
    status: str
    error_message: str | None
    client_id: str
    id_employee: int | None
    inputs: EmployeeInput
    prediction: int | None
    label: str | None
    probabilite_attrition: float | None
    model_version: str | None
    latency_ms: float | None


class PredictionList(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[PredictionRecord]


class HealthOutput(BaseModel):
    status: Literal["ok", "degraded"]
    environment: str
    api_version: str
    model_loaded: bool
    model_version: str | None
    database: Literal["ok", "error"]


class ModelInfo(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    model_version: str
    decision_threshold: float
    features: list[str]
    algorithm: str | None = None
    trained_at: str | None = None
    sklearn_version: str | None = None
    test_metrics: dict | None = None


class ErrorOutput(BaseModel):
    detail: str
