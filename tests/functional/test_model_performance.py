"""Tests fonctionnels du modèle : performances, reproductibilité, cohérence métier."""

import json

import joblib
import numpy as np
import pytest
from sklearn.model_selection import train_test_split

from app.ml.data_prep import FEATURES, TARGET
from scripts import train_model
from tests.conftest import METRICS_PATH, VALID_EMPLOYEE

# Seuils minimaux acceptés pour mettre une version en production (cf. docs/model.md).
MIN_ROC_AUC = 0.60
MIN_RECALL_ATTRITION = 0.50


@pytest.fixture(scope="module")
def test_split(dataset):
    _, X_test, _, y_test = train_test_split(
        dataset[FEATURES],
        dataset[TARGET],
        test_size=train_model.TEST_SIZE,
        stratify=dataset[TARGET],
        random_state=train_model.RANDOM_STATE,
    )
    return X_test, y_test


def test_metrics_on_test_set_meet_thresholds(model, test_split):
    X_test, y_test = test_split
    metrics = train_model.evaluate(y_test.to_numpy(), model.pipeline.predict_proba(X_test)[:, 1])
    assert metrics["roc_auc"] >= MIN_ROC_AUC
    assert metrics["recall_attrition"] >= MIN_RECALL_ATTRITION


def test_committed_metrics_match_model(model, test_split):
    """metrics.json décrit bien l'artefact versionné."""
    X_test, y_test = test_split
    recomputed = train_model.evaluate(y_test.to_numpy(), model.pipeline.predict_proba(X_test)[:, 1])
    assert recomputed == json.loads(METRICS_PATH.read_text())["test_metrics"]


def test_beats_random_on_full_dataset(model, dataset):
    proba = model.pipeline.predict_proba(dataset[FEATURES])[:, 1]
    leavers = proba[dataset[TARGET] == 1].mean()
    stayers = proba[dataset[TARGET] == 0].mean()
    assert leavers > stayers


def test_training_is_reproducible(tmp_path, data_dir, model, dataset):
    metrics = train_model.main(["--data-dir", str(data_dir), "--out-dir", str(tmp_path), "--version", "test"])
    assert metrics["test_metrics"] == json.loads(METRICS_PATH.read_text())["test_metrics"]
    retrained = joblib.load(tmp_path / "attrition_model.joblib")
    np.testing.assert_allclose(
        retrained.predict_proba(dataset[FEATURES])[:, 1],
        model.pipeline.predict_proba(dataset[FEATURES])[:, 1],
    )
    assert (tmp_path / "metrics.json").exists()


@pytest.mark.parametrize(
    "feature, low, high",
    [
        ("revenu_mensuel", 2000, 15000),  # salaire plus élevé -> risque plus faible
        ("age", 22, 55),  # employé plus âgé -> risque plus faible
    ],
)
def test_business_sanity(model, feature, low, high):
    p_low = model.predict_proba([{**VALID_EMPLOYEE, feature: low}])[0]
    p_high = model.predict_proba([{**VALID_EMPLOYEE, feature: high}])[0]
    assert p_low > p_high


def test_extreme_but_valid_inputs_do_not_crash(model):
    extremes = [
        {**VALID_EMPLOYEE, "age": 16, "revenu_mensuel": 0.01, "distance_domicile_travail": 0},
        {
            **VALID_EMPLOYEE,
            "age": 80,
            "revenu_mensuel": 100_000,
            "distance_domicile_travail": 500,
            "nombre_experiences_precedentes": 50,
            "genre": "F",
            "departement": "Ressources Humaines",
        },
    ]
    for out in model.predict(extremes):
        assert 0 <= out.probabilite_attrition <= 1


def test_inference_latency(model):
    import time

    start = time.perf_counter()
    model.predict([VALID_EMPLOYEE] * 100)
    assert (time.perf_counter() - start) < 1.0
