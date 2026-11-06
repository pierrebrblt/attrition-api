# Changelog

Format : [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/), versionnage sémantique.

## [1.0.0] - 2026-11-06

### Ajouté
- Pipeline CI/CD : lint, tests PostgreSQL avec couverture, build de la doc, image Docker avec
  smoke test, publication GHCR, déploiement dev/prod par environnement avec secrets.
- Image Docker (non-root, healthcheck), `docker-compose.yml` et `scripts/deploy.sh`.
- Documentation complète (README, MkDocs : architecture, API, base, modèle, tests, CI/CD,
  sécurité, standards).

## [0.4.0] - 2026-11-06

### Ajouté
- 138 tests unitaires et fonctionnels, couverture 99,6 %, seuil de couverture à 90 %.
- Tests de performance et de reproductibilité du modèle.

### Corrigé
- L'authentification lisait la configuration globale au lieu de celle de l'application.

## [0.3.0] - 2026-11-06

### Ajouté
- Traçabilité systématique : chaque input est enregistré avant l'inférence, puis l'output.
- Endpoints `/health`, `/model/info`, `/predict/batch`, `/predict/employee/{id}`,
  `/predictions`, `/predictions/{id}`.
- Authentification par clé d'API, configuration par environnement (dev / test / prod).
- Scripts de prédiction en lot, de requêtes et d'export d'exemples.

### Corrigé
- Le département `R&D` (inconnu du modèle) provoquait une erreur 500 : catégories et bornes
  désormais validées (422).

## [0.2.0] - 2026-11-06

### Ajouté
- Base PostgreSQL : 5 tables (référentiel + traçabilité), `create_db.py`, `schema.sql`.
- Chargement du dataset complet (1 470 employés), rôles à privilèges minimaux, requêtes SQL.

## [0.1.0] - 2026-11-06

### Ajouté
- Préparation des données partagée, script d'entraînement reproductible, artefact du modèle et
  `metrics.json` versionnés.
- Dépendances figées, configuration ruff / pytest.

## [0.0.1] - 2026-07-15

### Ajouté
- Structure initiale du projet, première API `/predict`, premiers tests, CI GitHub Actions.
