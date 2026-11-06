# Base de données

PostgreSQL 16. Le schéma est défini dans `app/db_models.py` (SQLAlchemy). `db/schema.sql` en
est la traduction SQL générée ; un test vérifie que les deux restent synchronisés.

## Schéma (UML / entité-association)

```mermaid
erDiagram
    employees ||--|| evaluations : "1-1"
    employees ||--|| surveys : "1-1"
    employees |o--o{ prediction_requests : "0..n"
    prediction_requests ||--o| prediction_results : "0..1"

    employees {
        int id_employee PK
        int age
        string genre "F/M"
        int revenu_mensuel
        string statut_marital
        string departement
        string poste
        int nombre_experiences_precedentes
        int nombre_heures_travaillees
        int annee_experience_totale
        int annees_dans_l_entreprise
        int annees_dans_le_poste_actuel
    }
    evaluations {
        int id_employee PK,FK
        string eval_number UK "E_<id>"
        int satisfaction_employee_environnement
        int satisfaction_employee_nature_travail
        int satisfaction_employee_equipe
        int satisfaction_employee_equilibre_pro_perso
        int note_evaluation_precedente
        int note_evaluation_actuelle
        int niveau_hierarchique_poste
        bool heure_supplementaires
        int augmentation_salaire_precedente_pct
    }
    surveys {
        int id_employee PK,FK
        string code_sondage UK
        bool a_quitte_l_entreprise "cible"
        int nombre_participation_pee
        int nb_formations_suivies
        int nombre_employee_sous_responsabilite
        int distance_domicile_travail
        int niveau_education
        string domaine_etude
        bool ayant_enfants
        string frequence_deplacement
        int annees_depuis_la_derniere_promotion
        int annees_sous_responsable_actuel
    }
    prediction_requests {
        int id PK
        datetime created_at
        string source "api/employee/batch"
        string status "pending/done/error"
        text error_message
        string client_id "empreinte de la clé"
        int id_employee FK "nullable"
        float revenu_mensuel
        int nombre_experiences_precedentes
        int age
        int note_evaluation_actuelle
        int note_evaluation_precedente
        int satisfaction_employee_equilibre_pro_perso
        float distance_domicile_travail
        string genre
        string departement
    }
    prediction_results {
        int id PK
        int request_id FK,UK
        datetime created_at
        int prediction "0/1"
        string label "Oui/Non"
        float probabilite_attrition
        float decision_threshold
        string model_version
        float latency_ms
    }
```

## Tables

**Référentiel** (dataset TechNova, 1 470 employés, chargé par `db/load_dataset.py`) :

* `employees` ← `extrait_sirh.csv`
* `evaluations` ← `extrait_eval.csv` (`eval_number = 'E_<id_employee>'`)
* `surveys` ← `extrait_sondage.csv` (`code_sondage` = id zéro-paddé), contient la cible

Transformations appliquées (`app/ml/data_prep.py`) : `"Oui"/"Non"` et `"Y"/"N"` convertis en
booléens, `"11 %"` converti en `11`, coquilles des noms de colonnes corrigées
(`nombre_heures_travailless`, `augementation_…`, `annes_…`). Le chargement échoue explicitement
si les identifiants des 3 fichiers ne correspondent pas ou si une valeur est inattendue.

**Traçabilité** : chaque appel au modèle crée une ligne `prediction_requests` (input, écrite
**avant** l'inférence), puis une ligne `prediction_results` (output). Les features envoyées au
modèle sont relues depuis la ligne enregistrée. En cas d'échec, la requête est conservée avec
`status = 'error'` et le message d'erreur.

**Volumétrie** : index sur `created_at`, `id_employee`, `departement` et
`a_quitte_l_entreprise` ; insertions groupées pour les batchs ; pagination de l'historique.

## Scripts

```bash
python -m db.create_db                      # crée la base (si absente) et les tables
python -m db.create_db --dump-sql db/schema.sql
python -m db.load_dataset [--replace]       # insère le dataset (idempotent)
psql "$ADMIN_URL" -v app_password="'...'" -v reader_password="'...'" -f db/roles.sql
python -m scripts.predict_employees --limit 100   # prédictions en lot via la base
python -m scripts.query_db stats|employee <id>|history|errors
python -m scripts.export_examples           # -> data/examples/predictions_examples.csv
psql "$DATABASE_URL" -f db/queries.sql      # requêtes SQL d'analyse
```

## Exemples d'entrées en base

* `data/examples/predictions_examples.csv` : 44 inputs/outputs réels (sources `api`, `employee`, `batch`) ;
* `data/examples/predictions_examples.sql` : mêmes données en `INSERT` PostgreSQL.

## Gestion des accès

`db/roles.sql` crée deux rôles selon le principe du moindre privilège :

| Rôle | Référentiel | Traçabilité | DDL |
|------|-------------|-------------|-----|
| `attrition_app` (API) | SELECT | SELECT, INSERT, UPDATE (pas de DELETE) | non |
| `attrition_reader` (analyse) | SELECT | SELECT | non |

Vérifié en local : `attrition_app` reçoit `permission denied` sur `DELETE FROM prediction_requests`
et `must be owner` sur `DROP TABLE`.
