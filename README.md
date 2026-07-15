# Attrition API

API de prédiction d'attrition des employés — TechNova Partners  
Déployée avec FastAPI · PostgreSQL · GitHub Actions · Hugging Face Spaces

## Stack technique
- Python 3.10
- FastAPI + Pydantic
- scikit-learn + imbalanced-learn
- PostgreSQL + SQLAlchemy
- Pytest + pytest-cov
- GitHub Actions CI/CD
- Hugging Face Spaces

## Installation
```bash
pip install -r requirements.txt
```

## Lancer l'API
```bash
uvicorn app.main:app --reload
```