"""
Étape 3 - Entraînement et évaluation du modèle
Modèle : régression logistique (léger, rapide, explicable, sans GPU).
Découpage chronologique : on apprend sur le passé et on teste sur la période
la plus récente, comme en conditions réelles.

Lancement : python entrainement.py
"""
import os
import json
import warnings
import sqlite3

import joblib
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import (accuracy_score, precision_score, recall_score,
                             f1_score, roc_auc_score, confusion_matrix)

from features import preparer, COLONNES_MODELE, SEUIL_PLUIE_MM

DB_PATH = "data/meteo.db"
warnings.filterwarnings("ignore", message="Skipping features")  
PART_TEST = 0.2


def evaluer(vrai, predit, proba=None):
    resultat = {
        "accuracy": round(accuracy_score(vrai, predit), 3),
        "precision": round(precision_score(vrai, predit, zero_division=0), 3),
        "rappel": round(recall_score(vrai, predit, zero_division=0), 3),
        "f1": round(f1_score(vrai, predit, zero_division=0), 3),
    }
    if proba is not None:
        resultat["roc_auc"] = round(roc_auc_score(vrai, proba), 3)
    vn, fp, fn, vp = confusion_matrix(vrai, predit).ravel()
    resultat["matrice_confusion"] = {"vrais_negatifs": int(vn), "faux_positifs": int(fp),
                                     "faux_negatifs": int(fn), "vrais_positifs": int(vp)}
    return resultat


def nouveau_modele():
    return make_pipeline(
        SimpleImputer(strategy="median"),
        StandardScaler(),
        LogisticRegression(class_weight="balanced", max_iter=1000),
    )


def choisir_seuil_alerte(train):
    """Choisit le seuil de probabilité qui déclenche une alerte pluie.
    On n'utilise QUE les données d'entraînement : validation chronologique en 4 blocs,
    puis on garde le seuil qui maximise le F1-score (équilibre rappel / précision)."""
    probas, vrais = [], []
    for idx_a, idx_b in TimeSeriesSplit(n_splits=4).split(train):
        a, b = train.iloc[idx_a], train.iloc[idx_b]
        m = nouveau_modele().fit(a[COLONNES_MODELE], a["pluie"])
        probas += list(m.predict_proba(b[COLONNES_MODELE])[:, 1])
        vrais += list(b["pluie"])
    seuils = [0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60]
    scores = [f1_score(vrais, [int(p >= s) for p in probas]) for s in seuils]
    return seuils[scores.index(max(scores))]


def main():
    conn = sqlite3.connect(DB_PATH)
    jours = pd.read_sql("SELECT * FROM daily_observations", conn)
    conn.close()

    df = preparer(jours)
    
    df = df[df["pluie"] >= 0]
    df = df[df[COLONNES_MODELE].isna().mean(axis=1) <= 0.5]
    print(f"Jours utilisables pour le modèle : {len(df)}")

    
    coupure = int(len(df) * (1 - PART_TEST))
    train, test = df.iloc[:coupure], df.iloc[coupure:]
    X_train, y_train = train[COLONNES_MODELE], train["pluie"]
    X_test, y_test = test[COLONNES_MODELE], test["pluie"]

    seuil_alerte = choisir_seuil_alerte(train)
    print(f"Seuil d'alerte choisi sur l'entraînement : {seuil_alerte}")

    modele = nouveau_modele()
    modele.fit(X_train, y_train)

    proba = modele.predict_proba(X_test)[:, 1]
    scores_modele = evaluer(y_test, (proba >= seuil_alerte).astype(int), proba)
    scores_seuil_defaut = evaluer(y_test, (proba >= 0.5).astype(int), proba)

  
    predit_ref = (test["pluie_mm_veille"] >= SEUIL_PLUIE_MM).astype(int)
    scores_ref = evaluer(y_test, predit_ref)

    metriques = {
        "modele": "Régression logistique",
        "seuil_pluie_mm": SEUIL_PLUIE_MM,
        "periode_entrainement": f"{train.index.min().date()} -> {train.index.max().date()}",
        "periode_test": f"{test.index.min().date()} -> {test.index.max().date()}",
        "nb_jours_entrainement": len(train),
        "nb_jours_test": len(test),
        "taux_jours_pluvieux": round(float(df["pluie"].mean()), 3),
        "seuil_alerte": seuil_alerte,
        "scores_modele": scores_modele,
        "scores_modele_seuil_0_5": scores_seuil_defaut,
        "scores_reference_persistance": scores_ref,
    }

    os.makedirs("model", exist_ok=True)
    joblib.dump(modele, "model/modele.joblib")
    with open("model/metriques.json", "w", encoding="utf-8") as f:
        json.dump(metriques, f, ensure_ascii=False, indent=2)

    print(json.dumps(metriques, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
