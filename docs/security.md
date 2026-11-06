# Authentification et sécurisation

## Authentification de l'API

* Les routes de prédiction, d'historique et `/model/info` exigent l'en-tête `X-API-Key`.
* Les clés valides sont listées dans la variable `API_KEYS` (séparées par des virgules), ce
  qui permet une clé par client et une rotation sans interruption (ajouter la nouvelle clé,
  migrer les clients, retirer l'ancienne).
* La comparaison se fait en temps constant (`secrets.compare_digest`).
* Seule une **empreinte SHA-256 tronquée** de la clé est stockée (`client_id`), jamais la clé.
* Codes de retour : `401` si la clé est absente, `403` si elle est invalide. Les tentatives
  invalides sont journalisées (avec l'empreinte uniquement).
* En `dev` et `test`, sans clé configurée, l'authentification est désactivée avec un
  avertissement. En `prod`, l'API **refuse de démarrer** sans clé d'au moins 16 caractères.

Générer une clé : `python -c "import secrets; print(secrets.token_urlsafe(32))"`.

## Secrets

| Secret | Où |
|---|---|
| `API_KEYS`, `POSTGRES_PASSWORD`, `DATABASE_URL` | `.env` local (ignoré par Git), secrets d'environnement GitHub, variables du conteneur |
| `GITHUB_TOKEN` | Fourni par GitHub Actions, éphémère |

## Base de données

* Rôles à privilèges minimaux (`db/roles.sql`) : l'API ne peut ni supprimer l'historique, ni
  modifier le schéma.
* PostgreSQL n'est exposé que sur `127.0.0.1`.
* Contraintes `CHECK` en base (bornes, catégories), en complément de la validation Pydantic.
* Requêtes paramétrées via SQLAlchemy (pas d'injection SQL).

## Données personnelles

Les données RH sont personnelles (RGPD). Recommandations pour une mise en production réelle :
pseudonymisation des identifiants, durée de conservation de l'historique, registre de
traitement, accès restreint aux équipes RH habilitées, revue du biais lié à `genre`, et
exposition derrière un reverse proxy HTTPS (TLS).

## Validation des entrées

Schémas Pydantic stricts (types, bornes, catégories fermées, `extra="forbid"`) et taille de
batch limitée (`MAX_BATCH_SIZE`, sinon 413).
