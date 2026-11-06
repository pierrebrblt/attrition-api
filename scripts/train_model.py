"""Entraînement reproductible du modèle d'attrition.

Reprend le pipeline du projet 4 (StandardScaler + OneHotEncoder + régression logistique
pondérée) et produit :

* ``models/attrition_model.joblib`` : pipeline sérialisé ;
* ``models/metrics.json`` : version, hyperparamètres, métriques sur le jeu de test, empreinte
  des données, versions des librairies.

Usage : ``python -m scripts.train_model [--data-dir data/raw] [--out-dir models] [--version 1.0.0]``
"""

import argparse
import hashlib
import json
import platform
from datetime import UTC, datetime
from pathlib import Path

import joblib
import numpy as np
import sklearn
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from app.config import ROOT_DIR
from app.ml.data_prep import CATEGORICAL_FEATURES, FEATURES, NUMERIC_FEATURES, RAW_FILES, TARGET, load_dataset

RANDOM_STATE = 42
TEST_SIZE = 0.2


def build_pipeline() -> Pipeline:
    preprocessor = ColumnTransformer(
        transformers=[
            ("num", StandardScaler(), NUMERIC_FEATURES),
            ("cat", OneHotEncoder(handle_unknown="error"), CATEGORICAL_FEATURES),
        ]
    )
    clf = LogisticRegression(class_weight="balanced", max_iter=1000, random_state=RANDOM_STATE)
    return Pipeline([("preprocessor", preprocessor), ("clf", clf)])


def data_fingerprint(data_dir: Path) -> str:
    h = hashlib.sha256()
    for name in sorted(RAW_FILES.values()):
        h.update((data_dir / name).read_bytes())
    return h.hexdigest()[:16]


def evaluate(y_true, proba, threshold: float = 0.5) -> dict:
    pred = (proba >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, pred).ravel()
    return {
        "roc_auc": round(float(roc_auc_score(y_true, proba)), 4),
        "accuracy": round(float(accuracy_score(y_true, pred)), 4),
        "precision_attrition": round(float(precision_score(y_true, pred)), 4),
        "recall_attrition": round(float(recall_score(y_true, pred)), 4),
        "f1_attrition": round(float(f1_score(y_true, pred)), 4),
        "confusion_matrix": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
    }


def train(data_dir: Path, out_dir: Path, version: str) -> dict:
    df = load_dataset(data_dir)
    X, y = df[FEATURES], df[TARGET]
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=TEST_SIZE, stratify=y, random_state=RANDOM_STATE
    )
    pipeline = build_pipeline()
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)
    cv_auc = cross_val_score(pipeline, X_train, y_train, cv=cv, scoring="roc_auc")
    pipeline.fit(X_train, y_train)
    proba = pipeline.predict_proba(X_test)[:, 1]

    metrics = {
        "model_version": version,
        "algorithm": "LogisticRegression(class_weight='balanced') + StandardScaler + OneHotEncoder",
        "trained_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "features": FEATURES,
        "target": TARGET,
        "random_state": RANDOM_STATE,
        "test_size": TEST_SIZE,
        "n_train": int(len(X_train)),
        "n_test": int(len(X_test)),
        "attrition_rate": round(float(y.mean()), 4),
        "data_fingerprint": data_fingerprint(data_dir),
        "cv_roc_auc_mean": round(float(np.mean(cv_auc)), 4),
        "cv_roc_auc_std": round(float(np.std(cv_auc)), 4),
        "test_metrics": evaluate(y_test.to_numpy(), proba),
        "sklearn_version": sklearn.__version__,
        "python_version": platform.python_version(),
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, out_dir / "attrition_model.joblib")
    (out_dir / "metrics.json").write_text(
        json.dumps(metrics, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return metrics


def main(argv: list[str] | None = None) -> dict:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=ROOT_DIR / "data" / "raw")
    parser.add_argument("--out-dir", type=Path, default=ROOT_DIR / "models")
    parser.add_argument("--version", default="1.0.0")
    args = parser.parse_args(argv)
    metrics = train(args.data_dir, args.out_dir, args.version)
    print(json.dumps(metrics["test_metrics"], indent=2))
    return metrics


if __name__ == "__main__":
    main()
