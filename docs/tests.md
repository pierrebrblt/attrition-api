# Tests

```bash
pytest                                   # SQLite temporaire, environ 4 s
TEST_DATABASE_URL=postgresql+psycopg2://user:pw@localhost:5432/attrition_test pytest   # PostgreSQL (CI)
pytest --cov --cov-report=html:reports/htmlcov   # rapport HTML de couverture
```

La CI exécute la suite sur **PostgreSQL 16** et publie les rapports (`coverage.xml`, HTML,
JUnit) en artefact `test-reports`. Le seuil `fail_under = 90` (pyproject.toml) fait échouer le
pipeline si la couverture baisse.

## Organisation

| Fichier | Type | Couvre |
|---|---|---|
| `tests/unit/test_schemas.py` | unitaire | Champs requis, types, bornes, catégories inconnues (`R&D`), champs en trop, cohérence avec les catégories du modèle |
| `tests/unit/test_model.py` | unitaire | Chargement (fichier absent, métriques absentes), ordre des features, déterminisme, seuil de décision, erreurs |
| `tests/unit/test_data_prep.py` | unitaire | Jointure des 3 CSV, conversions (%, Oui/Non), identifiants incohérents, doublons, valeurs inattendues |
| `tests/unit/test_config_security.py` | unitaire | Environnements dev/test/prod, garde-fous prod, clés d'API (401/403), empreinte |
| `tests/functional/test_api.py` | fonctionnel | Tous les endpoints, authentification, traçabilité en base, erreurs 404/413/422/500/503, modèle ou base indisponible |
| `tests/functional/test_database.py` | fonctionnel | Création de la base, chargement idempotent, cohérence base/CSV, synchronisation de `schema.sql`, scripts |
| `tests/functional/test_model_performance.py` | fonctionnel | Seuils de performance, reproductibilité de l'entraînement, sens métier, entrées extrêmes, latence |

## Résultats (v1.0.0)

* **138 tests réussis** sur PostgreSQL (137 + 1 ignoré sur SQLite : création de base propre à PostgreSQL) ;
* **couverture 99,6 %** (branches incluses), voir `reports/coverage.txt`.

## Points faibles identifiés et corrigés grâce aux tests

| Problème | Correction |
|---|---|
| Le schéma initial annonçait le département `R&D`, inconnu du modèle : erreur **500** | `Literal` sur les catégories apprises, d'où un 422 ; test de cohérence schéma/modèle |
| Notes d'évaluation acceptées en `float` sans bornes | Entiers bornés 1 à 4 |
| L'authentification lisait la config globale au lieu de celle de l'application | Dépendance `app_settings(request)` |
| La CI dépendait du téléchargement du modèle sur Hugging Face | Artefact versionné, testé tel quel |
| Les identifiants employés ne sont pas contigus (1 à 2068 pour 1 470 lignes) | Les tests utilisent les identifiants réels du dataset |
