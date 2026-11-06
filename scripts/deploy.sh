#!/usr/bin/env bash
# Déploiement local via docker compose (utilisé par la CD sur runner auto-hébergé, ou à la main).
# Variables attendues : API_IMAGE, APP_ENV, API_KEYS, POSTGRES_PASSWORD (jamais écrites sur disque).
set -euo pipefail

: "${API_KEYS:?API_KEYS manquant}"
: "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD manquant}"
export API_IMAGE="${API_IMAGE:-attrition-api:local}"
export APP_ENV="${APP_ENV:-prod}"

echo "Déploiement de ${API_IMAGE} (env=${APP_ENV})"
if [[ "${API_IMAGE}" == *"/"* ]]; then
  docker compose pull api
else
  docker compose build api
fi
docker compose up -d --wait db
docker compose run --rm --no-deps api python -m db.create_db
docker compose run --rm --no-deps api python -m db.load_dataset
docker compose up -d --no-build api

for _ in $(seq 1 30); do
  if curl -fs http://localhost:8000/health | grep -q '"status":"ok"'; then
    echo "API opérationnelle"; exit 0
  fi
  sleep 2
done
echo "L'API ne répond pas" >&2
docker compose logs --tail 50 api >&2
exit 1
