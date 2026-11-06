"""Exemple de client Python pour l'API (nécessite l'API démarrée).

Usage :
    API_URL=http://localhost:8000 API_KEY=... python -m scripts.api_client_example
"""

import json
import os

import httpx

from app.schemas import EXAMPLE_EMPLOYEE


def main() -> None:
    base = os.environ.get("API_URL", "http://localhost:8000")
    headers = {"X-API-Key": os.environ.get("API_KEY", "")}
    with httpx.Client(base_url=base, headers=headers, timeout=10) as client:
        for method, path, body in [
            ("GET", "/health", None),
            ("POST", "/predict", EXAMPLE_EMPLOYEE),
            ("POST", "/predict/employee/1", None),
            ("GET", "/predictions?limit=3", None),
        ]:
            resp = client.request(method, path, json=body)
            print(f"{method} {path} -> {resp.status_code}")
            print(json.dumps(resp.json(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
