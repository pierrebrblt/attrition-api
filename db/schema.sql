-- Schéma de la base attrition (généré par `python -m db.create_db --dump-sql`).
-- Ne pas éditer à la main : modifier app/db_models.py puis régénérer.

CREATE TABLE IF NOT EXISTS employees (
	id_employee INTEGER NOT NULL, 
	age INTEGER NOT NULL, 
	genre VARCHAR(1) NOT NULL, 
	revenu_mensuel INTEGER NOT NULL, 
	statut_marital VARCHAR(30) NOT NULL, 
	departement VARCHAR(50) NOT NULL, 
	poste VARCHAR(50) NOT NULL, 
	nombre_experiences_precedentes INTEGER NOT NULL, 
	nombre_heures_travaillees INTEGER NOT NULL, 
	annee_experience_totale INTEGER NOT NULL, 
	annees_dans_l_entreprise INTEGER NOT NULL, 
	annees_dans_le_poste_actuel INTEGER NOT NULL, 
	PRIMARY KEY (id_employee), 
	CONSTRAINT ck_employees_age CHECK (age BETWEEN 16 AND 80), 
	CONSTRAINT ck_employees_genre CHECK (genre IN ('F', 'M')), 
	CONSTRAINT ck_employees_revenu CHECK (revenu_mensuel > 0)
);

CREATE INDEX IF NOT EXISTS ix_employees_departement ON employees (departement);

CREATE TABLE IF NOT EXISTS evaluations (
	id_employee INTEGER NOT NULL, 
	eval_number VARCHAR(20) NOT NULL, 
	satisfaction_employee_environnement INTEGER NOT NULL, 
	satisfaction_employee_nature_travail INTEGER NOT NULL, 
	satisfaction_employee_equipe INTEGER NOT NULL, 
	satisfaction_employee_equilibre_pro_perso INTEGER NOT NULL, 
	note_evaluation_precedente INTEGER NOT NULL, 
	note_evaluation_actuelle INTEGER NOT NULL, 
	niveau_hierarchique_poste INTEGER NOT NULL, 
	heure_supplementaires BOOLEAN NOT NULL, 
	augmentation_salaire_precedente_pct INTEGER NOT NULL, 
	PRIMARY KEY (id_employee), 
	CONSTRAINT ck_eval_note_act CHECK (note_evaluation_actuelle BETWEEN 1 AND 4), 
	CONSTRAINT ck_eval_note_prec CHECK (note_evaluation_precedente BETWEEN 1 AND 4), 
	FOREIGN KEY(id_employee) REFERENCES employees (id_employee) ON DELETE CASCADE, 
	UNIQUE (eval_number)
);


CREATE TABLE IF NOT EXISTS prediction_requests (
	id SERIAL NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	source VARCHAR(20) NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	error_message TEXT, 
	client_id VARCHAR(64) NOT NULL, 
	id_employee INTEGER, 
	revenu_mensuel FLOAT NOT NULL, 
	nombre_experiences_precedentes INTEGER NOT NULL, 
	age INTEGER NOT NULL, 
	note_evaluation_actuelle INTEGER NOT NULL, 
	note_evaluation_precedente INTEGER NOT NULL, 
	satisfaction_employee_equilibre_pro_perso INTEGER NOT NULL, 
	distance_domicile_travail FLOAT NOT NULL, 
	genre VARCHAR(1) NOT NULL, 
	departement VARCHAR(50) NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_req_source CHECK (source IN ('api', 'employee', 'batch')), 
	CONSTRAINT ck_req_status CHECK (status IN ('pending', 'done', 'error')), 
	FOREIGN KEY(id_employee) REFERENCES employees (id_employee) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS ix_prediction_requests_created_at ON prediction_requests (created_at);
CREATE INDEX IF NOT EXISTS ix_prediction_requests_id_employee ON prediction_requests (id_employee);

CREATE TABLE IF NOT EXISTS surveys (
	id_employee INTEGER NOT NULL, 
	code_sondage VARCHAR(20) NOT NULL, 
	a_quitte_l_entreprise BOOLEAN NOT NULL, 
	nombre_participation_pee INTEGER NOT NULL, 
	nb_formations_suivies INTEGER NOT NULL, 
	nombre_employee_sous_responsabilite INTEGER NOT NULL, 
	distance_domicile_travail INTEGER NOT NULL, 
	niveau_education INTEGER NOT NULL, 
	domaine_etude VARCHAR(50) NOT NULL, 
	ayant_enfants BOOLEAN NOT NULL, 
	frequence_deplacement VARCHAR(20) NOT NULL, 
	annees_depuis_la_derniere_promotion INTEGER NOT NULL, 
	annees_sous_responsable_actuel INTEGER NOT NULL, 
	PRIMARY KEY (id_employee), 
	FOREIGN KEY(id_employee) REFERENCES employees (id_employee) ON DELETE CASCADE, 
	UNIQUE (code_sondage)
);

CREATE INDEX IF NOT EXISTS ix_surveys_a_quitte_l_entreprise ON surveys (a_quitte_l_entreprise);

CREATE TABLE IF NOT EXISTS prediction_results (
	id SERIAL NOT NULL, 
	request_id INTEGER NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	prediction INTEGER NOT NULL, 
	label VARCHAR(3) NOT NULL, 
	probabilite_attrition FLOAT NOT NULL, 
	decision_threshold FLOAT NOT NULL, 
	model_version VARCHAR(50) NOT NULL, 
	latency_ms FLOAT NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_res_prediction CHECK (prediction IN (0, 1)), 
	CONSTRAINT ck_res_proba CHECK (probabilite_attrition BETWEEN 0 AND 1), 
	UNIQUE (request_id), 
	FOREIGN KEY(request_id) REFERENCES prediction_requests (id) ON DELETE CASCADE
);
