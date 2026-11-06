# Attrition API

Proof of Concept réalisé pour **Futurisys** : rendre opérationnel le modèle de prédiction
d'attrition des employés de TechNova Partners (projet 4) via une API REST documentée, testée,
tracée en base PostgreSQL et livrée par un pipeline CI/CD.

| Besoin                         | Réponse                                                        |
|--------------------------------|----------------------------------------------------------------|
| Exposer le modèle              | FastAPI + validation Pydantic, Swagger sur `/docs`             |
| Fiabilité                      | 138 tests Pytest, couverture ≈ 99 % (PostgreSQL)               |
| Traçabilité                    | Chaque input/output du modèle est stocké dans PostgreSQL       |
| Collaboration                  | Git (branches `feature/*`, PR vers `develop`, tags `vX.Y.Z`)   |
| Automatisation                 | GitHub Actions : lint, tests, docs, image Docker, déploiement  |
| Sécurité                       | Clé d'API, secrets hors du code, rôles PostgreSQL restreints   |

## Démarrage rapide

```bash
cp .env.example .env                 # puis adapter les secrets
docker compose up -d db              # PostgreSQL local
pip install -r requirements-dev.txt
python -m db.create_db && python -m db.load_dataset
uvicorn app.main:app --reload        # http://localhost:8000/docs
```

Voir [Déploiement](deployment.md) pour le déploiement complet en conteneurs.
