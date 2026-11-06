-- Gestion fine des accès (principe du moindre privilège).
--
-- Usage (en tant que propriétaire de la base, APRÈS db/create_db.py) :
--   psql "$ADMIN_DATABASE_URL" -v app_password="'...'" -v reader_password="'...'" -f db/roles.sql
--
-- * attrition_app    : compte utilisé par l'API. Lecture du référentiel, écriture uniquement
--                      dans les tables de traçabilité. Aucun DROP/ALTER/TRUNCATE possible.
-- * attrition_reader : compte d'analyse en lecture seule (reporting, data science).

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'attrition_app') THEN
        CREATE ROLE attrition_app LOGIN;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'attrition_reader') THEN
        CREATE ROLE attrition_reader LOGIN;
    END IF;
END
$$;

ALTER ROLE attrition_app PASSWORD :app_password;
ALTER ROLE attrition_reader PASSWORD :reader_password;

REVOKE ALL ON ALL TABLES IN SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO attrition_app, attrition_reader;

-- API : lecture du référentiel
GRANT SELECT ON employees, evaluations, surveys TO attrition_app;
-- API : traçabilité (pas de DELETE : l'historique est conservé)
GRANT SELECT, INSERT, UPDATE ON prediction_requests, prediction_results TO attrition_app;
GRANT USAGE, SELECT ON SEQUENCE prediction_requests_id_seq, prediction_results_id_seq TO attrition_app;

-- Analyse : lecture seule sur tout
GRANT SELECT ON ALL TABLES IN SCHEMA public TO attrition_reader;
