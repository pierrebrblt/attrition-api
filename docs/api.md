# Documentation de l'API

Documentation interactive générée par FastAPI :

* **Swagger UI** : <http://localhost:8000/docs> (bouton *Authorize* pour saisir la clé)
* **ReDoc** : <http://localhost:8000/redoc>
* **Spécification OpenAPI** : <http://localhost:8000/openapi.json>

## Endpoints

| Méthode | Route | Auth | Description |
|---------|-------|------|-------------|
| GET  | `/` | non | Message d'accueil, version |
| GET  | `/health` | non | État de l'API, du modèle et de la base (`ok` / `degraded`) |
| GET  | `/model/info` | oui | Version, features, seuil, métriques du modèle |
| POST | `/predict` | oui | Prédiction pour un employé décrit dans le corps |
| POST | `/predict/batch` | oui | Prédiction pour une liste (max `MAX_BATCH_SIZE`, 100 par défaut) |
| POST | `/predict/employee/{id_employee}` | oui | Prédiction pour un employé du référentiel (features lues en base) |
| GET  | `/predictions` | oui | Historique paginé (`limit`, `offset`, filtres `id_employee`, `source`) |
| GET  | `/predictions/{request_id}` | oui | Détail d'une prédiction (input + output) |

L'authentification se fait par l'en-tête `X-API-Key` (voir [Sécurité](security.md)).

## Schéma d'entrée `EmployeeInput`

| Champ | Type | Contraintes |
|-------|------|-------------|
| `revenu_mensuel` | nombre | > 0, ≤ 100 000 |
| `nombre_experiences_precedentes` | entier | 0 à 50 |
| `age` | entier | 16 à 80 |
| `note_evaluation_actuelle` | entier | 1 à 4 |
| `note_evaluation_precedente` | entier | 1 à 4 |
| `satisfaction_employee_equilibre_pro_perso` | entier | 1 à 4 |
| `distance_domicile_travail` | nombre | 0 à 500 (km) |
| `genre` | texte | `"F"` ou `"M"` |
| `departement` | texte | `"Commercial"`, `"Consulting"` ou `"Ressources Humaines"` |

Tout champ manquant, mal typé, hors bornes, toute catégorie inconnue ou tout champ
supplémentaire est rejeté avec un **422** détaillant le champ fautif. Aucune ligne n'est alors
écrite en base.

## Exemples

```bash
KEY=dev-key-change-me-0123456789

curl -X POST http://localhost:8000/predict \
  -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
  -d '{"revenu_mensuel": 2100, "nombre_experiences_precedentes": 6, "age": 24,
       "note_evaluation_actuelle": 3, "note_evaluation_precedente": 2,
       "satisfaction_employee_equilibre_pro_perso": 1, "distance_domicile_travail": 25,
       "genre": "F", "departement": "Commercial"}'
```

```json
{
  "request_id": 1,
  "prediction": 1,
  "label": "Oui",
  "probabilite_attrition": 0.9564,
  "model_version": "1.0.0",
  "created_at": "2026-11-06T10:38:37.261223Z"
}
```

```bash
curl -X POST http://localhost:8000/predict/employee/1 -H "X-API-Key: $KEY"
# {..., "id_employee": 1, "a_quitte_l_entreprise": true, "probabilite_attrition": 0.6988}

curl "http://localhost:8000/predictions?source=employee&limit=5" -H "X-API-Key: $KEY"
```

En Python : `python -m scripts.api_client_example` (variables `API_URL`, `API_KEY`).

## Codes de retour

| Code | Cas |
|------|-----|
| 200 | Succès |
| 401 | Clé d'API absente |
| 403 | Clé d'API invalide |
| 404 | Employé ou prédiction introuvable |
| 413 | Batch trop volumineux |
| 422 | Données invalides (détail par champ) |
| 500 | Échec du modèle ; la requête reste tracée avec `status = error`, et ses `request_ids` sont renvoyés |
| 503 | Modèle non chargé ou base indisponible |
