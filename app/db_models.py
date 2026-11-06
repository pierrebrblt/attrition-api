"""Modèle de données (ORM SQLAlchemy).

Deux familles de tables :

* **Référentiel** (dataset TechNova) : ``employees``, ``evaluations``, ``surveys`` (relation 1-1
  sur ``id_employee``).
* **Traçabilité du modèle** : ``prediction_requests`` (inputs envoyés au modèle) et
  ``prediction_results`` (outputs générés), reliées en 1-1. Toute prédiction, qu'elle vienne
  de l'API, d'un employé du référentiel ou d'un batch, passe par ces deux tables.
"""

from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


# --------------------------------------------------------------------------------------------
# Référentiel
# --------------------------------------------------------------------------------------------
class Employee(Base):
    """Données SIRH (extrait_sirh.csv)."""

    __tablename__ = "employees"
    __table_args__ = (
        CheckConstraint("age BETWEEN 16 AND 80", name="ck_employees_age"),
        CheckConstraint("genre IN ('F', 'M')", name="ck_employees_genre"),
        CheckConstraint("revenu_mensuel > 0", name="ck_employees_revenu"),
    )

    id_employee: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    age: Mapped[int] = mapped_column(Integer, nullable=False)
    genre: Mapped[str] = mapped_column(String(1), nullable=False)
    revenu_mensuel: Mapped[int] = mapped_column(Integer, nullable=False)
    statut_marital: Mapped[str] = mapped_column(String(30), nullable=False)
    departement: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    poste: Mapped[str] = mapped_column(String(50), nullable=False)
    nombre_experiences_precedentes: Mapped[int] = mapped_column(Integer, nullable=False)
    nombre_heures_travaillees: Mapped[int] = mapped_column(Integer, nullable=False)
    annee_experience_totale: Mapped[int] = mapped_column(Integer, nullable=False)
    annees_dans_l_entreprise: Mapped[int] = mapped_column(Integer, nullable=False)
    annees_dans_le_poste_actuel: Mapped[int] = mapped_column(Integer, nullable=False)

    evaluation: Mapped["Evaluation"] = relationship(back_populates="employee", uselist=False)
    survey: Mapped["Survey"] = relationship(back_populates="employee", uselist=False)


class Evaluation(Base):
    """Évaluations annuelles (extrait_eval.csv). ``eval_number`` = 'E_<id_employee>'."""

    __tablename__ = "evaluations"
    __table_args__ = (
        CheckConstraint("note_evaluation_actuelle BETWEEN 1 AND 4", name="ck_eval_note_act"),
        CheckConstraint("note_evaluation_precedente BETWEEN 1 AND 4", name="ck_eval_note_prec"),
    )

    id_employee: Mapped[int] = mapped_column(
        ForeignKey("employees.id_employee", ondelete="CASCADE"), primary_key=True
    )
    eval_number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    satisfaction_employee_environnement: Mapped[int] = mapped_column(Integer, nullable=False)
    satisfaction_employee_nature_travail: Mapped[int] = mapped_column(Integer, nullable=False)
    satisfaction_employee_equipe: Mapped[int] = mapped_column(Integer, nullable=False)
    satisfaction_employee_equilibre_pro_perso: Mapped[int] = mapped_column(Integer, nullable=False)
    note_evaluation_precedente: Mapped[int] = mapped_column(Integer, nullable=False)
    note_evaluation_actuelle: Mapped[int] = mapped_column(Integer, nullable=False)
    niveau_hierarchique_poste: Mapped[int] = mapped_column(Integer, nullable=False)
    heure_supplementaires: Mapped[bool] = mapped_column(Boolean, nullable=False)
    augmentation_salaire_precedente_pct: Mapped[int] = mapped_column(Integer, nullable=False)

    employee: Mapped[Employee] = relationship(back_populates="evaluation")


class Survey(Base):
    """Sondage interne (extrait_sondage.csv), contient la cible ``a_quitte_l_entreprise``."""

    __tablename__ = "surveys"

    id_employee: Mapped[int] = mapped_column(
        ForeignKey("employees.id_employee", ondelete="CASCADE"), primary_key=True
    )
    code_sondage: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    a_quitte_l_entreprise: Mapped[bool] = mapped_column(Boolean, nullable=False, index=True)
    nombre_participation_pee: Mapped[int] = mapped_column(Integer, nullable=False)
    nb_formations_suivies: Mapped[int] = mapped_column(Integer, nullable=False)
    nombre_employee_sous_responsabilite: Mapped[int] = mapped_column(Integer, nullable=False)
    distance_domicile_travail: Mapped[int] = mapped_column(Integer, nullable=False)
    niveau_education: Mapped[int] = mapped_column(Integer, nullable=False)
    domaine_etude: Mapped[str] = mapped_column(String(50), nullable=False)
    ayant_enfants: Mapped[bool] = mapped_column(Boolean, nullable=False)
    frequence_deplacement: Mapped[str] = mapped_column(String(20), nullable=False)
    annees_depuis_la_derniere_promotion: Mapped[int] = mapped_column(Integer, nullable=False)
    annees_sous_responsable_actuel: Mapped[int] = mapped_column(Integer, nullable=False)

    employee: Mapped[Employee] = relationship(back_populates="survey")


# --------------------------------------------------------------------------------------------
# Traçabilité des échanges avec le modèle
# --------------------------------------------------------------------------------------------
class PredictionRequest(Base):
    """Input envoyé au modèle. Enregistré AVANT l'inférence : le modèle lit ses features ici."""

    __tablename__ = "prediction_requests"
    __table_args__ = (
        CheckConstraint("source IN ('api', 'employee', 'batch')", name="ck_req_source"),
        CheckConstraint("status IN ('pending', 'done', 'error')", name="ck_req_status"),
        Index("ix_prediction_requests_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    client_id: Mapped[str] = mapped_column(String(64), nullable=False, default="anonymous")
    id_employee: Mapped[int | None] = mapped_column(
        ForeignKey("employees.id_employee", ondelete="SET NULL"), nullable=True, index=True
    )
    # --- Features du modèle ---
    revenu_mensuel: Mapped[float] = mapped_column(Float, nullable=False)
    nombre_experiences_precedentes: Mapped[int] = mapped_column(Integer, nullable=False)
    age: Mapped[int] = mapped_column(Integer, nullable=False)
    note_evaluation_actuelle: Mapped[int] = mapped_column(Integer, nullable=False)
    note_evaluation_precedente: Mapped[int] = mapped_column(Integer, nullable=False)
    satisfaction_employee_equilibre_pro_perso: Mapped[int] = mapped_column(Integer, nullable=False)
    distance_domicile_travail: Mapped[float] = mapped_column(Float, nullable=False)
    genre: Mapped[str] = mapped_column(String(1), nullable=False)
    departement: Mapped[str] = mapped_column(String(50), nullable=False)

    result: Mapped["PredictionResult | None"] = relationship(
        back_populates="request", uselist=False, cascade="all, delete-orphan"
    )


class PredictionResult(Base):
    """Output généré par le modèle pour une ``PredictionRequest``."""

    __tablename__ = "prediction_results"
    __table_args__ = (
        CheckConstraint("prediction IN (0, 1)", name="ck_res_prediction"),
        CheckConstraint("probabilite_attrition BETWEEN 0 AND 1", name="ck_res_proba"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    request_id: Mapped[int] = mapped_column(
        ForeignKey("prediction_requests.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    prediction: Mapped[int] = mapped_column(Integer, nullable=False)
    label: Mapped[str] = mapped_column(String(3), nullable=False)
    probabilite_attrition: Mapped[float] = mapped_column(Float, nullable=False)
    decision_threshold: Mapped[float] = mapped_column(Float, nullable=False)
    model_version: Mapped[str] = mapped_column(String(50), nullable=False)
    latency_ms: Mapped[float] = mapped_column(Float, nullable=False)

    request: Mapped[PredictionRequest] = relationship(back_populates="result")
