"""Préparation des données brutes TechNova (3 fichiers CSV).

Une seule implémentation est partagée par l'entraînement (``scripts/train_model.py``), le
chargement en base (``db/load_dataset.py``) et les tests, afin de garantir la cohérence entre
les données stockées et celles vues par le modèle.

Jointure : ``extrait_sirh.id_employee`` = ``extrait_eval.eval_number`` ('E_<id>') =
``extrait_sondage.code_sondage`` (id zéro-paddé).
"""

from pathlib import Path

import pandas as pd

NUMERIC_FEATURES = [
    "revenu_mensuel",
    "nombre_experiences_precedentes",
    "age",
    "note_evaluation_actuelle",
    "note_evaluation_precedente",
    "satisfaction_employee_equilibre_pro_perso",
    "distance_domicile_travail",
]
CATEGORICAL_FEATURES = ["genre", "departement"]
FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES
TARGET = "a_quitte_l_entreprise"

RAW_FILES = {
    "sirh": "extrait_sirh.csv",
    "eval": "extrait_eval.csv",
    "sondage": "extrait_sondage.csv",
}

# Corrections des coquilles présentes dans les noms de colonnes sources.
SIRH_RENAME = {"nombre_heures_travailless": "nombre_heures_travaillees"}
EVAL_RENAME = {"augementation_salaire_precedente": "augmentation_salaire_precedente_pct"}
SONDAGE_RENAME = {"annes_sous_responsable_actuel": "annees_sous_responsable_actuel"}

_OUI_NON = {"Oui": True, "Non": False}
_Y_N = {"Y": True, "N": False}


def _map_strict(series: pd.Series, mapping: dict, column: str) -> pd.Series:
    mapped = series.map(mapping)
    if mapped.isna().any():
        bad = sorted(series[mapped.isna()].astype(str).unique())
        raise ValueError(f"Valeurs inattendues dans '{column}': {bad}")
    return mapped.astype(bool)


def load_raw(data_dir: str | Path) -> dict[str, pd.DataFrame]:
    """Lit les 3 CSV bruts. Lève FileNotFoundError si un fichier manque."""
    data_dir = Path(data_dir)
    frames = {}
    for key, filename in RAW_FILES.items():
        path = data_dir / filename
        if not path.exists():
            raise FileNotFoundError(f"Fichier introuvable : {path}")
        frames[key] = pd.read_csv(path, dtype={"code_sondage": str, "eval_number": str})
    return frames


def clean_sirh(df: pd.DataFrame) -> pd.DataFrame:
    out = df.rename(columns=SIRH_RENAME).copy()
    if not out["id_employee"].is_unique:
        raise ValueError("id_employee doit être unique dans extrait_sirh.csv")
    return out


def clean_eval(df: pd.DataFrame) -> pd.DataFrame:
    out = df.rename(columns=EVAL_RENAME).copy()
    if not out["eval_number"].str.fullmatch(r"E_\d+").all():
        raise ValueError("eval_number doit respecter le format 'E_<id>'")
    out["id_employee"] = out["eval_number"].str.removeprefix("E_").astype(int)
    out["heure_supplementaires"] = _map_strict(
        out["heure_supplementaires"], _OUI_NON, "heure_supplementaires"
    )
    out["augmentation_salaire_precedente_pct"] = (
        out["augmentation_salaire_precedente_pct"]
        .astype(str)
        .str.replace("%", "", regex=False)
        .str.strip()
        .astype(int)
    )
    return out


def clean_sondage(df: pd.DataFrame) -> pd.DataFrame:
    out = df.rename(columns=SONDAGE_RENAME).copy()
    out["code_sondage"] = out["code_sondage"].astype(str)
    out["id_employee"] = out["code_sondage"].astype(int)
    out[TARGET] = _map_strict(out[TARGET], _OUI_NON, TARGET)
    out["ayant_enfants"] = _map_strict(out["ayant_enfants"], _Y_N, "ayant_enfants")
    return out


def clean_all(frames: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Nettoie les 3 tables et vérifie que les identifiants correspondent 1-1."""
    sirh = clean_sirh(frames["sirh"])
    ev = clean_eval(frames["eval"])
    so = clean_sondage(frames["sondage"])
    ids = set(sirh["id_employee"])
    if set(ev["id_employee"]) != ids or set(so["id_employee"]) != ids:
        raise ValueError("Les identifiants employés ne correspondent pas entre les 3 fichiers")
    return {"sirh": sirh, "eval": ev, "sondage": so}


def build_dataset(frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Renvoie la table fusionnée (1 ligne par employé) avec la cible encodée en 0/1."""
    cleaned = clean_all(frames)
    merged = (
        cleaned["sirh"]
        .merge(cleaned["eval"], on="id_employee", how="inner", validate="one_to_one")
        .merge(cleaned["sondage"], on="id_employee", how="inner", validate="one_to_one")
        .sort_values("id_employee")
        .reset_index(drop=True)
    )
    merged[TARGET] = merged[TARGET].astype(int)
    return merged


def load_dataset(data_dir: str | Path) -> pd.DataFrame:
    return build_dataset(load_raw(data_dir))
