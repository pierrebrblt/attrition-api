-- Requêtes d'exemple sur la base attrition (psql "$DATABASE_URL" -f db/queries.sql)

-- 1. Volume du référentiel
SELECT (SELECT count(*) FROM employees)   AS employees,
       (SELECT count(*) FROM evaluations) AS evaluations,
       (SELECT count(*) FROM surveys)     AS surveys;

-- 2. Taux d'attrition réel par département
SELECT e.departement,
       count(*)                                              AS effectif,
       round(100.0 * avg(s.a_quitte_l_entreprise::int), 1)  AS taux_attrition_pct
FROM employees e
JOIN surveys s USING (id_employee)
GROUP BY e.departement
ORDER BY taux_attrition_pct DESC;

-- 3. Les 10 dernières prédictions (input + output)
SELECT r.id, r.created_at, r.source, r.status, r.id_employee,
       r.age, r.revenu_mensuel, r.departement,
       p.label, p.probabilite_attrition, p.model_version
FROM prediction_requests r
LEFT JOIN prediction_results p ON p.request_id = r.id
ORDER BY r.id DESC
LIMIT 10;

-- 4. Requêtes en erreur (traçabilité des échecs)
SELECT id, created_at, source, error_message FROM prediction_requests WHERE status = 'error';

-- 5. Prédit vs réel pour les employés du référentiel (dernière prédiction par employé)
WITH last_pred AS (
    SELECT DISTINCT ON (r.id_employee) r.id_employee, p.prediction
    FROM prediction_requests r
    JOIN prediction_results p ON p.request_id = r.id
    WHERE r.id_employee IS NOT NULL
    ORDER BY r.id_employee, r.id DESC
)
SELECT s.a_quitte_l_entreprise AS reel,
       lp.prediction = 1       AS predit,
       count(*)                AS nb
FROM last_pred lp
JOIN surveys s USING (id_employee)
GROUP BY 1, 2
ORDER BY 1, 2;

-- 6. Activité et latence par client et par jour
SELECT r.client_id, date_trunc('day', r.created_at) AS jour,
       count(*) AS nb_requetes, round(avg(p.latency_ms)::numeric, 2) AS latence_moy_ms
FROM prediction_requests r
LEFT JOIN prediction_results p ON p.request_id = r.id
GROUP BY 1, 2
ORDER BY 2 DESC, 1;
