"""Chargement et inférence du modèle d'attrition (pipeline scikit-learn sérialisé avec joblib)."""

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import pandas as pd

from app.ml.data_prep import FEATURES

logger = logging.getLogger(__name__)


class ModelNotLoadedError(RuntimeError):
    pass


@dataclass(frozen=True)
class Outcome:
    prediction: int
    label: str
    probabilite_attrition: float


class AttritionModel:
    """Enveloppe autour du pipeline : ordre des features, seuil de décision, métadonnées."""

    def __init__(
        self,
        pipeline: Any,
        version: str,
        threshold: float = 0.5,
        metadata: dict | None = None,
    ) -> None:
        missing = [m for m in ("predict_proba",) if not hasattr(pipeline, m)]
        if missing:
            raise TypeError(f"L'objet chargé n'est pas un classifieur valide (manque {missing})")
        self.pipeline = pipeline
        self.version = version
        self.threshold = threshold
        self.metadata = metadata or {}

    @classmethod
    def load(
        cls, model_path: str | Path, metrics_path: str | Path | None = None, threshold: float = 0.5
    ) -> "AttritionModel":
        model_path = Path(model_path)
        if not model_path.exists():
            raise ModelNotLoadedError(f"Modèle introuvable : {model_path}")
        pipeline = joblib.load(model_path)
        metadata: dict = {}
        if metrics_path and Path(metrics_path).exists():
            metadata = json.loads(Path(metrics_path).read_text(encoding="utf-8"))
        version = metadata.get("model_version", "unknown")
        logger.info("Modèle chargé depuis %s (version %s)", model_path, version)
        return cls(pipeline, version=version, threshold=threshold, metadata=metadata)

    def _frame(self, records: list[dict]) -> pd.DataFrame:
        if not records:
            raise ValueError("Aucune donnée à prédire")
        df = pd.DataFrame(records)
        missing = [f for f in FEATURES if f not in df.columns]
        if missing:
            raise ValueError(f"Features manquantes : {missing}")
        return df[FEATURES]

    def predict_proba(self, records: list[dict]) -> list[float]:
        probas = self.pipeline.predict_proba(self._frame(records))[:, 1]
        return [float(p) for p in probas]

    def predict(self, records: list[dict]) -> list[Outcome]:
        outcomes = []
        for proba in self.predict_proba(records):
            pred = int(proba >= self.threshold)
            outcomes.append(
                Outcome(
                    prediction=pred,
                    label="Oui" if pred == 1 else "Non",
                    probabilite_attrition=round(proba, 4),
                )
            )
        return outcomes

    def info(self) -> dict:
        return {
            "model_version": self.version,
            "decision_threshold": self.threshold,
            "features": FEATURES,
            "algorithm": self.metadata.get("algorithm"),
            "trained_at": self.metadata.get("trained_at"),
            "sklearn_version": self.metadata.get("sklearn_version"),
            "test_metrics": self.metadata.get("test_metrics"),
        }
