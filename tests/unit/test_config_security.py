"""Configuration (gestion des environnements) et authentification."""

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.config import Settings
from app.security import fingerprint, require_api_key

PG = "postgresql+psycopg2://u:p@localhost/db"


def test_api_key_list_parsing():
    s = Settings(api_keys=" a , b,,c ")
    assert s.api_key_list == ["a", "b", "c"]
    assert s.auth_enabled


def test_auth_disabled_without_keys_in_dev():
    assert not Settings(app_env="dev", api_keys="").auth_enabled


@pytest.mark.parametrize(
    "kwargs, msg",
    [
        ({"api_keys": ""}, "API_KEYS"),
        ({"api_keys": "trop-courte"}, "16 caractères"),
        ({"api_keys": "x" * 32, "database_url": "sqlite:///x.db"}, "PostgreSQL"),
    ],
)
def test_prod_guards(kwargs, msg):
    with pytest.raises(ValidationError, match=msg):
        Settings(app_env="prod", **{"database_url": PG, **kwargs})


def test_prod_valid():
    s = Settings(app_env="prod", api_keys="x" * 32, database_url=PG)
    assert s.app_env == "prod"


def test_unknown_env_rejected():
    with pytest.raises(ValidationError):
        Settings(app_env="staging")


def test_threshold_bounds():
    with pytest.raises(ValidationError):
        Settings(decision_threshold=1.5)


def test_settings_from_env(monkeypatch):
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("DECISION_THRESHOLD", "0.3")
    assert Settings().decision_threshold == 0.3


def test_require_api_key_valid():
    s = Settings(api_keys="k1-aaaaaaaaaaaaaaaa,k2-bbbbbbbbbbbbbbbb")
    assert require_api_key("k2-bbbbbbbbbbbbbbbb", s) == fingerprint("k2-bbbbbbbbbbbbbbbb")


def test_require_api_key_missing():
    with pytest.raises(HTTPException) as exc:
        require_api_key(None, Settings(api_keys="k"))
    assert exc.value.status_code == 401


def test_require_api_key_invalid():
    with pytest.raises(HTTPException) as exc:
        require_api_key("mauvaise", Settings(api_keys="k"))
    assert exc.value.status_code == 403


def test_require_api_key_disabled():
    assert require_api_key(None, Settings(app_env="dev", api_keys="")) == "anonymous"


def test_fingerprint_does_not_leak_key():
    fp = fingerprint("super-secret-key")
    assert len(fp) == 12 and "secret" not in fp
    assert fp == fingerprint("super-secret-key")
