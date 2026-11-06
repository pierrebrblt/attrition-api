"""Création de la base, chargement du dataset et scripts d'interaction."""

import csv

import pytest
from sqlalchemy import func, inspect, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.database import make_engine
from app.db_models import Employee, Evaluation, PredictionRequest, Survey
from app.services import employee_features, get_employee
from db import create_db, load_dataset
from scripts import export_examples, predict_employees, query_db

TABLES = ["employees", "evaluations", "prediction_requests", "prediction_results", "surveys"]


def test_reference_data_loaded(db, dataset):
    assert db.scalar(select(func.count()).select_from(Employee)) == 1470
    assert db.scalar(select(func.count()).select_from(Evaluation)) == 1470
    assert db.scalar(select(func.count()).select_from(Survey)) == 1470
    assert db.scalar(select(func.count()).select_from(Survey).where(Survey.a_quitte_l_entreprise)) == 237


def test_db_content_matches_csv(db, dataset):
    """Cohérence entre les données en base et celles vues par le modèle."""
    for row in dataset.sample(20, random_state=0).itertuples():
        emp = get_employee(db, row.id_employee)
        feats = employee_features(emp)
        assert feats["revenu_mensuel"] == row.revenu_mensuel
        assert feats["note_evaluation_actuelle"] == row.note_evaluation_actuelle
        assert feats["distance_domicile_travail"] == row.distance_domicile_travail
        assert emp.evaluation.augmentation_salaire_precedente_pct == row.augmentation_salaire_precedente_pct


def test_employee_features_incomplete(db):
    emp = Employee(id_employee=1)
    with pytest.raises(LookupError):
        employee_features(emp)


def test_load_is_idempotent(db, data_dir):
    assert load_dataset.load(db, data_dir) == {"employees": 0, "evaluations": 0, "surveys": 0}


def test_create_db_on_fresh_sqlite(tmp_path, data_dir):
    url = f"sqlite:///{tmp_path / 'fresh.db'}"
    assert create_db.main(["--database-url", url]) == TABLES
    assert sorted(inspect(make_engine(url)).get_table_names()) == TABLES
    assert load_dataset.main(["--database-url", url, "--data-dir", str(data_dir)])["employees"] == 1470
    assert (
        load_dataset.main(["--database-url", url, "--data-dir", str(data_dir), "--replace"])["employees"]
        == 1470
    )
    assert create_db.main(["--database-url", url, "--drop"]) == TABLES


def test_ensure_database_noop_on_sqlite():
    assert create_db.ensure_database(make_url("sqlite://")) is False


def test_schema_sql_is_up_to_date(tmp_path):
    """db/schema.sql doit correspondre aux modèles ORM (régénérer avec --dump-sql)."""
    out = tmp_path / "schema.sql"
    create_db.main(["--dump-sql", str(out)])
    committed = (create_db.Path(create_db.__file__).parent / "schema.sql").read_text(encoding="utf-8")
    assert out.read_text(encoding="utf-8") == committed
    for table in TABLES:
        assert f"CREATE TABLE IF NOT EXISTS {table}" in committed


@pytest.mark.postgres
def test_ensure_database_creates_pg_database(database_url, is_postgres):
    if not is_postgres:
        pytest.skip("PostgreSQL requis")
    url = make_url(database_url).set(database="attrition_tmp_test")
    from sqlalchemy import create_engine, text

    create_db.ensure_database(url)
    assert create_db.ensure_database(url) is False  # déjà créée
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text('DROP DATABASE "attrition_tmp_test"'))
    admin.dispose()


def test_predict_employees_script(db, model, dataset):
    ids = dataset["id_employee"].head(3).tolist()  # les identifiants ne sont pas contigus
    summary = predict_employees.run(db, model, ids=ids + [999999])
    assert summary["processed"] == 3
    assert 0 <= summary["accuracy_vs_actual"] <= 1
    rows = db.scalars(select(PredictionRequest)).all()
    assert {r.id_employee for r in rows} == set(ids)
    assert all(r.status == "done" and r.result is not None for r in rows)


def test_predict_employees_empty(db, model):
    assert predict_employees.run(db, model, ids=[999999])["processed"] == 0


def test_predict_employees_main(db, database_url):
    assert predict_employees.main(["--database-url", database_url, "--limit", "5"])["processed"] == 5


def test_query_db_commands(db, model, database_url, capsys):
    predict_employees.run(db, model, ids=[1])
    stats = query_db.main(["--database-url", database_url, "stats"])
    assert stats["employees"] == 1470 and stats["prediction_results"] == 1
    assert set(stats["attrition_by_department"]) == {"Commercial", "Consulting", "Ressources Humaines"}
    emp = query_db.main(["--database-url", database_url, "employee", "1"])
    assert emp["id_employee"] == 1 and len(emp["predictions"]) == 1
    assert query_db.main(["--database-url", database_url, "employee", "999999"]) is None
    assert len(query_db.main(["--database-url", database_url, "history", "--limit", "5"])) == 1
    assert query_db.main(["--database-url", database_url, "errors"]) == []
    assert "employees" in capsys.readouterr().out


def test_export_examples(db, model, database_url, tmp_path):
    predict_employees.run(db, model, ids=[1, 2])
    out = tmp_path / "ex.csv"
    assert export_examples.main(["--database-url", database_url, "--out", str(out)]) == 2
    rows = list(csv.DictReader(out.open(encoding="utf-8")))
    assert len(rows) == 2
    assert rows[0]["id_employee"] == "1" and rows[0]["label"] in ("Oui", "Non")
    assert rows[0]["age"] != ""


def test_session_scope_closes():
    from app.database import make_session_factory, session_scope

    factory = make_session_factory(make_engine("sqlite://"))
    gen = session_scope(factory)
    session = next(gen)
    assert isinstance(session, Session)
    gen.close()
