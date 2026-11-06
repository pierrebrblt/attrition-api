"""Tests unitaires du wrapper de modèle."""

import json

import joblib
import pytest

from app.ml.data_prep import FEATURES
from app.ml.model import AttritionModel, ModelNotLoadedError
from tests.conftest import METRICS_PATH, MODEL_PATH, VALID_EMPLOYEE


def test_load_reads_version_from_metrics(model):
    meta = json.loads(METRICS_PATH.read_text())
    assert model.version == meta["model_version"]
    assert model.threshold == 0.5


def test_load_missing_file(tmp_path):
    with pytest.raises(ModelNotLoadedError):
        AttritionModel.load(tmp_path / "absent.joblib")


def test_load_without_metrics(tmp_path):
    m = AttritionModel.load(MODEL_PATH, tmp_path / "absent.json")
    assert m.version == "unknown"


def test_rejects_non_classifier():
    with pytest.raises(TypeError):
        AttritionModel(object(), version="x")


def test_pipeline_expects_api_features(model):
    assert list(model.pipeline.feature_names_in_) == FEATURES


def test_predict_single(model):
    [out] = model.predict([VALID_EMPLOYEE])
    assert out.prediction in (0, 1)
    assert out.label == ("Oui" if out.prediction else "Non")
    assert 0.0 <= out.probabilite_attrition <= 1.0


def test_predict_is_deterministic(model):
    assert model.predict([VALID_EMPLOYEE] * 3) == model.predict([VALID_EMPLOYEE] * 3)
    assert len({o.probabilite_attrition for o in model.predict([VALID_EMPLOYEE] * 3)}) == 1


def test_feature_order_does_not_matter(model):
    reordered = dict(reversed(list(VALID_EMPLOYEE.items())))
    assert model.predict_proba([reordered]) == model.predict_proba([VALID_EMPLOYEE])


def test_extra_columns_ignored(model):
    assert model.predict_proba([{**VALID_EMPLOYEE, "autre": 1}]) == model.predict_proba([VALID_EMPLOYEE])


def test_missing_feature_raises(model):
    data = {k: v for k, v in VALID_EMPLOYEE.items() if k != "age"}
    with pytest.raises(ValueError, match="age"):
        model.predict([data])


def test_empty_input_raises(model):
    with pytest.raises(ValueError):
        model.predict([])


def test_unknown_category_raises(model):
    """Le pipeline refuse une catégorie inconnue : d'où la validation stricte côté API."""
    with pytest.raises(ValueError):
        model.predict([{**VALID_EMPLOYEE, "departement": "R&D"}])


@pytest.mark.parametrize("threshold, expected", [(0.0001, 1), (0.9999, 0)])
def test_threshold_drives_decision(threshold, expected):
    m = AttritionModel(joblib.load(MODEL_PATH), version="t", threshold=threshold)
    assert m.predict([VALID_EMPLOYEE])[0].prediction == expected


def test_info(model):
    info = model.info()
    assert info["features"] == FEATURES
    assert info["test_metrics"]["roc_auc"] > 0.5
