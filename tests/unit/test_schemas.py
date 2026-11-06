"""Validation Pydantic des entrées : cas nominaux, limites et erreurs."""

import pytest
from pydantic import ValidationError

from app.schemas import BatchInput, EmployeeInput
from tests.conftest import VALID_EMPLOYEE


def test_valid_employee():
    emp = EmployeeInput(**VALID_EMPLOYEE)
    assert emp.departement == "Consulting"
    assert emp.model_dump() == {**VALID_EMPLOYEE, "revenu_mensuel": 3500.0, "distance_domicile_travail": 15.0}


@pytest.mark.parametrize("field", list(VALID_EMPLOYEE))
def test_every_field_is_required(field):
    data = {k: v for k, v in VALID_EMPLOYEE.items() if k != field}
    with pytest.raises(ValidationError) as exc:
        EmployeeInput(**data)
    assert exc.value.errors()[0]["loc"] == (field,)


@pytest.mark.parametrize(
    "field, value",
    [
        ("age", 15),
        ("age", 81),
        ("age", 35.5),
        ("age", "trente"),
        ("revenu_mensuel", 0),
        ("revenu_mensuel", -100),
        ("nombre_experiences_precedentes", -1),
        ("note_evaluation_actuelle", 0),
        ("note_evaluation_actuelle", 5),
        ("note_evaluation_precedente", 5),
        ("satisfaction_employee_equilibre_pro_perso", 0),
        ("distance_domicile_travail", -1),
        ("genre", "X"),
        ("genre", "f"),
        ("departement", "R&D"),
        ("departement", ""),
        ("departement", None),
    ],
)
def test_invalid_values_rejected(field, value):
    with pytest.raises(ValidationError):
        EmployeeInput(**{**VALID_EMPLOYEE, field: value})


@pytest.mark.parametrize(
    "field, value",
    [
        ("age", 16),
        ("age", 80),
        ("note_evaluation_actuelle", 1),
        ("note_evaluation_actuelle", 4),
        ("distance_domicile_travail", 0),
        ("nombre_experiences_precedentes", 0),
    ],
)
def test_boundaries_accepted(field, value):
    assert getattr(EmployeeInput(**{**VALID_EMPLOYEE, field: value}), field) == value


def test_numeric_strings_are_coerced():
    emp = EmployeeInput(**{**VALID_EMPLOYEE, "age": "40"})
    assert emp.age == 40


def test_extra_field_forbidden():
    with pytest.raises(ValidationError, match="Extra inputs"):
        EmployeeInput(**VALID_EMPLOYEE, salaire_secret=1)


def test_batch_requires_at_least_one():
    with pytest.raises(ValidationError):
        BatchInput(employees=[])


def test_categories_match_model(model):
    """Les catégories autorisées par l'API sont exactement celles apprises par le modèle."""
    enc = model.pipeline.named_steps["preprocessor"].named_transformers_["cat"]
    genre_cats, dept_cats = (sorted(c) for c in enc.categories_)
    schema = EmployeeInput.model_json_schema()["properties"]
    assert sorted(schema["genre"]["enum"]) == genre_cats
    assert sorted(schema["departement"]["enum"]) == dept_cats
