# Modèle de Machine Learning (fiche modèle)

## Objectif

Estimer la probabilité qu'un employé de TechNova Partners quitte l'entreprise, afin d'aider les
RH à prioriser des actions de rétention. Le modèle est **un outil d'aide à la décision**, pas
un outil de décision automatique.

## Données

* Source : 3 extraits RH (SIRH, évaluations, sondage), soit **1 470 employés**, sans valeur manquante.
* Cible : `a_quitte_l_entreprise`, avec **237 départs (16,1 %)**, donc classes déséquilibrées.
* Empreinte des données d'entraînement : `data_fingerprint` dans `models/metrics.json`.

## Features (9)

| Numériques (StandardScaler) | Catégorielles (OneHotEncoder) |
|---|---|
| revenu_mensuel, nombre_experiences_precedentes, age, note_evaluation_actuelle, note_evaluation_precedente, satisfaction_employee_equilibre_pro_perso, distance_domicile_travail | genre, departement |

## Algorithme

`Pipeline(ColumnTransformer -> LogisticRegression(class_weight="balanced", max_iter=1000))`.
La pondération des classes compense le déséquilibre et privilégie le rappel sur les départs.
Le modèle réentraîné par `scripts/train_model.py` est identique (mêmes coefficients) à celui du
projet 4 publié sur Hugging Face (`PierreBrblt/attrition-model`). Ce script le rend
reproductible et traçable.

Effets appris (coefficients sur variables standardisées) :

| Augmente le risque | Diminue le risque |
|---|---|
| nombre d'expériences précédentes (+0,36), département Commercial (+0,33), distance domicile-travail (+0,30) | âge (−0,47), revenu mensuel (−0,43), département Consulting (−0,42), note d'évaluation précédente (−0,31), satisfaction équilibre pro/perso (−0,21) |

## Performances

Split stratifié 80/20 (`random_state=42`) : 1 176 lignes en entraînement, 294 en test.

| Métrique | Valeur |
|---|---|
| ROC AUC, validation croisée 5 plis (train) | **0,719 ± 0,044** |
| ROC AUC, jeu de test | **0,646** |
| Rappel « départ », test | **0,57** (27 départs détectés sur 47) |
| Précision « départ », test | 0,23 |
| F1 « départ », test | 0,33 |
| Accuracy, test | 0,63 |
| Latence d'inférence | < 1 ms par employé (100 prédictions < 1 s, testé) |

Matrice de confusion (test, seuil 0,5) : TN = 157, FP = 90, FN = 20, TP = 27.

!!! warning "Limites"
    * Performances **modestes** : le modèle détecte plus de la moitié des départs, mais génère
      beaucoup de faux positifs. L'écart entre la validation croisée (0,72) et le test (0,65)
      traduit une variance importante liée à la petite taille du jeu de test (47 départs).
    * Seules 9 variables sont utilisées. Des variables disponibles en base et non exploitées
      (heures supplémentaires, ancienneté dans le poste, dernière promotion, fréquence de
      déplacement…) sont des pistes d'amélioration prioritaires.
    * `genre` est une variable sensible : son poids est faible (−0,10 / +0,02), mais son usage
      doit être validé avec les RH et le DPO (biais, RGPD).
    * Catégories hors apprentissage (ex. un nouveau département) : refusées par l'API (422).
      Il faut réentraîner le modèle pour les intégrer.

## Seuils d'acceptation (testés en CI)

`tests/functional/test_model_performance.py` bloque toute version qui ne respecte pas :
ROC AUC test ≥ 0,60, rappel « départ » ≥ 0,50, reproductibilité de l'entraînement,
cohérence entre `metrics.json` et l'artefact, et sens métier attendu (revenu et âge plus
élevés : risque plus faible).

## Maintenance et protocole de mise à jour

1. **Suivi continu** : les tables `prediction_requests` et `prediction_results` permettent de
   suivre le volume, la latence, la distribution des probabilités et des inputs (dérive)
   via `db/queries.sql`.
2. **Revue trimestrielle** (ou dès qu'un nouvel extrait RH est disponible) : comparer les
   prédictions aux départs réels (requête 5 de `db/queries.sql`), et contrôler la dérive des
   distributions (âge, revenu, répartition par département).
3. **Réentraînement** sur une branche `feature/model-vX.Y` :
   `python -m scripts.train_model --version X.Y.Z`, puis mise à jour de `models/metrics.json`.
4. **Validation** : la CI rejoue les seuils d'acceptation. Toute baisse doit être justifiée
   dans la PR.
5. **Release** : merge `develop` vers `main`, tag `vX.Y.Z`, puis déploiement prod après
   approbation. Chaque prédiction stocke `model_version`, ce qui permet de comparer les versions
   a posteriori.
6. **Rollback** : redéployer l'image du tag précédent (`ghcr.io/…:X.Y.Z`).
7. **Évolutions du contrat** (ajout de features) : version majeure de l'API, avec mise à jour
   des schémas Pydantic, de la table `prediction_requests` et de cette fiche.
