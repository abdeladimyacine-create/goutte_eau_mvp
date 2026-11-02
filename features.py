"""
Construction des variables du modèle (utilisé par l'entraînement ET par l'API,
pour être sûr que les deux calculent exactement la même chose).

Principe : pour prédire la pluie du jour J, on utilise uniquement
les observations de la veille (J-1) et la saison. C'est donc une vraie
prévision à 24 h, cohérente avec le cahier des charges.
"""
import numpy as np
import pandas as pd

SEUIL_PLUIE_MM = 1.0   # définition Météo-France d'un "jour de pluie" : >= 1 mm

VARIABLES_JOUR = ["temp_moy", "temp_min", "temp_max", "pression_moy",
                  "humidite_moy", "vent_moy", "rafales_max", "pluie_mm"]

COLONNES_MODELE = [v + "_veille" for v in VARIABLES_JOUR] + [
    "tendance_pression", "saison_sin", "saison_cos"]


def preparer(jours, date_fin=None):
    """Reçoit le tableau journalier et renvoie un tableau indexé par date
    avec les variables du modèle et la cible 'pluie' (0/1)."""
    df = jours.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").sort_index()

    # Calendrier complet : un jour manquant reste vide (pas de faux "veille")
    fin = df.index.max()
    if date_fin is not None and pd.Timestamp(date_fin) > fin:
        fin = pd.Timestamp(date_fin)
    df = df.reindex(pd.date_range(df.index.min(), fin, freq="D"))

    for v in VARIABLES_JOUR:
        df[v + "_veille"] = df[v].shift(1)
    df["tendance_pression"] = df["pression_moy"].shift(1) - df["pression_moy"].shift(2)

    jour_annee = df.index.dayofyear
    df["saison_sin"] = np.sin(2 * np.pi * jour_annee / 365.25)
    df["saison_cos"] = np.cos(2 * np.pi * jour_annee / 365.25)

    df["pluie"] = (df["pluie_mm"] >= SEUIL_PLUIE_MM).astype(int)
    df.loc[df["pluie_mm"].isna(), "pluie"] = -1   # -1 = pluie inconnue
    return df
