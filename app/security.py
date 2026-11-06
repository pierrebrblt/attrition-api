"""Authentification par clé d'API (en-tête ``X-API-Key``)."""

import hashlib
import logging
import secrets

from fastapi import Depends, HTTPException, Request, Security, status
from fastapi.security import APIKeyHeader

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)

api_key_header = APIKeyHeader(
    name="X-API-Key",
    auto_error=False,
    description="Clé d'API fournie par l'administrateur (variable d'environnement API_KEYS).",
)


def fingerprint(key: str) -> str:
    """Empreinte non réversible d'une clé, stockée en base pour la traçabilité (jamais la clé elle-même)."""
    return hashlib.sha256(key.encode()).hexdigest()[:12]


def app_settings(request: Request) -> Settings:
    """Configuration de l'instance d'application courante (et non la configuration globale)."""
    return getattr(request.app.state, "settings", None) or get_settings()


def require_api_key(
    api_key: str | None = Security(api_key_header),
    settings: Settings = Depends(app_settings),
) -> str:
    """Valide la clé et renvoie l'identifiant client (empreinte) associé.

    Si aucune clé n'est configurée (dev/test uniquement, la prod l'interdit), l'authentification
    est désactivée et le client est identifié comme ``anonymous``.
    """
    if not settings.auth_enabled:
        return "anonymous"
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Clé d'API manquante (en-tête X-API-Key).",
            headers={"WWW-Authenticate": "API-Key"},
        )
    for valid in settings.api_key_list:
        if secrets.compare_digest(api_key.encode(), valid.encode()):
            return fingerprint(api_key)
    logger.warning("Tentative d'accès avec une clé invalide (empreinte %s)", fingerprint(api_key))
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Clé d'API invalide.")
