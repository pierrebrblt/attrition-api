"""Configuration de l'application, lue depuis les variables d'environnement (ou un fichier .env).

Aucun secret n'est codé en dur : les clés d'API et l'URL de la base sont fournies par
l'environnement (fichier .env local, secrets GitHub Actions, variables du conteneur...).
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: Literal["dev", "test", "prod"] = "dev"
    database_url: str = f"sqlite:///{ROOT_DIR / 'attrition_dev.db'}"
    # Liste de clés séparées par des virgules. Obligatoire en production.
    api_keys: str = ""
    model_path: Path = ROOT_DIR / "models" / "attrition_model.joblib"
    metrics_path: Path = ROOT_DIR / "models" / "metrics.json"
    # Seuil de décision appliqué à la probabilité de départ.
    decision_threshold: float = Field(default=0.5, gt=0.0, lt=1.0)
    # Création automatique des tables au démarrage (désactivée en prod : on passe par db/create_db.py).
    auto_create_tables: bool = True
    max_batch_size: int = Field(default=100, ge=1, le=1000)
    log_level: str = "INFO"

    @property
    def api_key_list(self) -> list[str]:
        return [k.strip() for k in self.api_keys.split(",") if k.strip()]

    @property
    def auth_enabled(self) -> bool:
        return bool(self.api_key_list)

    @model_validator(mode="after")
    def _check_prod(self) -> "Settings":
        if self.app_env == "prod":
            if not self.api_key_list:
                raise ValueError("API_KEYS doit être défini en production.")
            if any(len(k) < 16 for k in self.api_key_list):
                raise ValueError("Chaque clé d'API doit faire au moins 16 caractères en production.")
            if self.database_url.startswith("sqlite"):
                raise ValueError("La production doit utiliser PostgreSQL.")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
