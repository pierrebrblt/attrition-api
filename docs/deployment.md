# Déploiement

## Option 1 : conteneurs (recommandé)

Prérequis : Docker et Docker Compose.

```bash
cp .env.example .env          # définir POSTGRES_PASSWORD et API_KEYS (clés fortes)
docker compose up -d --build  # PostgreSQL + API (APP_ENV=prod)
docker compose run --rm api python -m db.create_db
docker compose run --rm api python -m db.load_dataset
curl http://localhost:8000/health
```

Ou en une commande (identique à la CD) :

```bash
export API_KEYS=... POSTGRES_PASSWORD=...
./scripts/deploy.sh                                   # image construite localement
API_IMAGE=ghcr.io/pierrebrblt/attrition-api:1.0.0 ./scripts/deploy.sh   # image publiée par la CI
```

Les ports ne sont exposés que sur `127.0.0.1`. L'image tourne avec un utilisateur non-root et
intègre un `HEALTHCHECK`.

## Option 2 : environnement Python local (développement)

```bash
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
docker compose up -d db                       # ou un PostgreSQL existant
python -m db.create_db && python -m db.load_dataset
uvicorn app.main:app --reload
```

## Mise à jour

```bash
git pull && ./scripts/deploy.sh      # ou API_IMAGE=...:X.Y.Z pour une version publiée
```

Rollback : relancer `deploy.sh` avec l'image du tag précédent. Les données sont conservées
dans le volume `pgdata`.
