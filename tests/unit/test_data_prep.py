"""Préparation des données : jointure, nettoyage, cas d'erreur."""

import pandas as pd
import pytest

from app.ml import data_prep as dp


def test_load_raw_shapes(data_dir):
    frames = dp.load_raw(data_dir)
    assert {k: len(v) for k, v in frames.items()} == {"sirh": 1470, "eval": 1470, "sondage": 1470}


def test_load_raw_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        dp.load_raw(tmp_path)


def test_dataset_one_row_per_employee(dataset):
    assert len(dataset) == 1470
    assert dataset["id_employee"].is_unique
    assert dataset[dp.FEATURES + [dp.TARGET]].notna().all().all()


def test_target_encoding(dataset):
    assert set(dataset[dp.TARGET]) == {0, 1}
    assert dataset[dp.TARGET].sum() == 237  # 237 départs sur 1470


def test_column_typos_fixed(dataset):
    for good in [
        "nombre_heures_travaillees",
        "augmentation_salaire_precedente_pct",
        "annees_sous_responsable_actuel",
    ]:
        assert good in dataset.columns
    for bad in [
        "nombre_heures_travailless",
        "augementation_salaire_precedente",
        "annes_sous_responsable_actuel",
    ]:
        assert bad not in dataset.columns


def test_percentage_and_booleans_parsed(dataset):
    assert dataset["augmentation_salaire_precedente_pct"].between(0, 100).all()
    assert dataset["heure_supplementaires"].dtype == bool
    assert dataset["ayant_enfants"].dtype == bool


def test_join_keys_consistent(data_dir):
    cleaned = dp.clean_all(dp.load_raw(data_dir))
    row = cleaned["eval"].iloc[0]
    assert row["eval_number"] == f"E_{row['id_employee']}"
    s = cleaned["sondage"].iloc[0]
    assert int(s["code_sondage"]) == s["id_employee"]


def test_mismatched_ids_raise(data_dir):
    frames = dp.load_raw(data_dir)
    frames["sondage"] = frames["sondage"].iloc[:-1]
    with pytest.raises(ValueError, match="ne correspondent pas"):
        dp.clean_all(frames)


def test_duplicate_ids_raise(data_dir):
    frames = dp.load_raw(data_dir)
    frames["sirh"] = pd.concat([frames["sirh"], frames["sirh"].iloc[:1]])
    with pytest.raises(ValueError, match="unique"):
        dp.clean_all(frames)


def test_bad_eval_number_raises(data_dir):
    frames = dp.load_raw(data_dir)
    frames["eval"].loc[0, "eval_number"] = "X_1"
    with pytest.raises(ValueError, match="format"):
        dp.clean_eval(frames["eval"])


def test_unexpected_boolean_value_raises(data_dir):
    frames = dp.load_raw(data_dir)
    frames["sondage"].loc[0, dp.TARGET] = "Peut-être"
    with pytest.raises(ValueError, match="Peut-être"):
        dp.clean_sondage(frames["sondage"])
