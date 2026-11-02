"""
Étape 4 - API de restitution des prévisions (FastAPI)

Lancement : uvicorn api:app --reload
Documentation interactive (Swagger) : http://127.0.0.1:8000/docs
"""
import json
import warnings
import sqlite3
from datetime import date, timedelta

import joblib
import pandas as pd
from fastapi import FastAPI, HTTPException

from features import preparer, COLONNES_MODELE

DB_PATH = "data/meteo.db"
warnings.filterwarnings("ignore", message="Skipping features")
VERSION = "1.0.0"

app = FastAPI(
    title="API Goutte d'Eau",
    description="Estimation du risque de pluie à 24 h pour une date donnée (MVP).",
    version=VERSION,
)

modele = joblib.load("model/modele.joblib")
with open("model/metriques.json", encoding="utf-8") as f:
    metriques = json.load(f)


SEUIL_ALERTE = metriques.get("seuil_alerte", 0.5)   # choisi lors de l'entraînement


def niveau_risque(probabilite):
    if probabilite >= SEUIL_ALERTE:
        return "élevé"
    if probabilite >= SEUIL_ALERTE - 0.15:
        return "modéré"
    return "faible"


@app.get("/health")
def health():
    """Vérifie que le service fonctionne et indique la dernière prévision possible."""
    conn = sqlite3.connect(DB_PATH)
    derniere = conn.execute("SELECT MAX(date) FROM daily_observations").fetchone()[0]
    conn.close()
    prochaine = date.fromisoformat(derniere) + timedelta(days=1)
    return {"statut": "ok", "version": VERSION, "derniere_date_prevue": str(prochaine)}


@app.get("/predict")
def predict(date_cible: date):
    """Renvoie le risque de pluie pour la date demandée (format AAAA-MM-JJ).
    Le calcul utilise les observations de la veille."""
    conn = sqlite3.connect(DB_PATH)
    jours = pd.read_sql("SELECT * FROM daily_observations", conn)
    conn.close()

    premiere = pd.Timestamp(jours["date"].min()).date()
    derniere = pd.Timestamp(jours["date"].max()).date()
    if date_cible <= premiere + timedelta(days=1) or date_cible > derniere + timedelta(days=1):
        raise HTTPException(
            status_code=404,
            detail=f"Date hors période disponible : choisir entre "
                   f"{premiere + timedelta(days=2)} et {derniere + timedelta(days=1)}.",
        )

    df = preparer(jours, date_fin=date_cible)
    ligne = df.loc[[pd.Timestamp(date_cible)]]
    if ligne[COLONNES_MODELE].isna().mean(axis=1).iloc[0] > 0.5:
        raise HTTPException(status_code=404,
                            detail="Observations de la veille manquantes pour cette date.")

    probabilite = float(modele.predict_proba(ligne[COLONNES_MODELE])[0, 1])
    pluie_observee = ligne["pluie_mm"].iloc[0]

    return {
        "date": str(date_cible),
        "probabilite_pluie": round(probabilite, 3),
        "risque": niveau_risque(probabilite),
        "alerte": probabilite >= SEUIL_ALERTE,
        "pluie_observee_mm": None if pd.isna(pluie_observee) else float(pluie_observee),
    }


@app.get("/metrics")
def metrics():
    """Indicateurs qualité du modèle calculés sur la période de test."""
    return metriques
