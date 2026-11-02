"""
Étape 2 - Nettoyage et agrégation
Lit les mesures brutes, supprime les valeurs aberrantes, agrège par jour
et enregistre le résultat dans la table daily_observations (données nettoyées).

Les fonctions sont aussi utilisées dans le notebook analyse.ipynb.
Lancement : python nettoyage.py
"""
import sqlite3
import pandas as pd

from collecte import STATION

DB_PATH = "data/meteo.db"
MIN_MESURES_PAR_JOUR = 12   # un jour avec trop peu de mesures n'est pas fiable
MIN_HEURES_PLUIE = 18       # pluie du jour connue seulement si au moins 18 h sur 24 sont renseignées

# Plages de valeurs plausibles : en dehors, la mesure est considérée comme erronée
LIMITES = {
    "temperature": (-30, 50),
    "pression": (950, 1060),
    "humidite": (0, 100),
    "vent_moyen": (0, 150),
    "vent_rafales": (0, 250),
    "pluie_1h": (0, 150),
    "pluie_3h": (0, 300),
}

COLONNES_JOUR = ["date", "temp_moy", "temp_min", "temp_max", "pression_moy",
                 "humidite_moy", "vent_moy", "rafales_max", "pluie_mm"]


def charger_brut(conn):
    """Lit les mesures brutes, supprime les doublons et convertit les dates."""
    brut = pd.read_sql("SELECT * FROM raw_observations", conn)
    brut = brut[brut["station"] == STATION]   # une seule station dans le MVP
    brut = brut.drop_duplicates(subset=["station", "dh_utc"])
    brut["dh_utc"] = pd.to_datetime(brut["dh_utc"], errors="coerce")
    brut = brut.dropna(subset=["dh_utc"]).sort_values("dh_utc")
    return brut


def supprimer_aberrants(brut):
    """Remplace les valeurs hors plage plausible par des vides.
    Renvoie les données corrigées et le nombre de valeurs supprimées par colonne."""
    brut = brut.copy()
    nb_supprimees = {}
    for colonne, (mini, maxi) in LIMITES.items():
        hors_plage = (brut[colonne] < mini) | (brut[colonne] > maxi)
        nb_supprimees[colonne] = int(hors_plage.sum())
        brut.loc[hors_plage, colonne] = None
    return brut, nb_supprimees


def pluie_par_jour(brut, colonne, periode):
    """Cumul de pluie par jour. La station mesure environ toutes les 10 min, mais
    'pluie_1h' est le cumul de la dernière heure, répété à chaque mesure : on garde
    la dernière mesure de chaque heure, puis on additionne les heures du jour."""
    mesures = brut.dropna(subset=[colonne])
    par_periode = mesures.groupby(mesures["dh_utc"].dt.floor(periode))[colonne].last()
    par_jour = par_periode.groupby(par_periode.index.date)
    # Un jour dont la pluie n'est connue que quelques heures n'est pas fiable :
    # on ne le compte pas comme "sec", on le laisse inconnu.
    heures_couvertes = par_jour.size() * (3 if periode == "3h" else 1)
    return par_jour.sum()[heures_couvertes >= MIN_HEURES_PLUIE]


def agreger_par_jour(brut):
    """Agrège les mesures par jour et écarte les jours incomplets."""
    brut = brut.copy()
    brut["date"] = brut["dh_utc"].dt.date
    jours = brut.groupby("date").agg(
        nb_mesures=("dh_utc", "count"),
        temp_moy=("temperature", "mean"),
        temp_min=("temperature", "min"),
        temp_max=("temperature", "max"),
        pression_moy=("pression", "mean"),
        humidite_moy=("humidite", "mean"),
        vent_moy=("vent_moyen", "mean"),
        rafales_max=("vent_rafales", "max"),
    )
    pluie_1h = pluie_par_jour(brut, "pluie_1h", "h")
    pluie_3h = pluie_par_jour(brut, "pluie_3h", "3h")
    jours["pluie_mm"] = pluie_1h.reindex(jours.index)
    jours["pluie_mm"] = jours["pluie_mm"].fillna(pluie_3h.reindex(jours.index))

    jours = jours[jours["nb_mesures"] >= MIN_MESURES_PAR_JOUR].reset_index()
    jours = jours[COLONNES_JOUR].round(2)
    jours["date"] = jours["date"].astype(str)
    return jours


def main():
    conn = sqlite3.connect(DB_PATH)
    brut = charger_brut(conn)
    print(f"Mesures brutes : {len(brut)}")

    brut, nb_supprimees = supprimer_aberrants(brut)
    print(f"Valeurs aberrantes supprimées : {sum(nb_supprimees.values())}")

    jours = agreger_par_jour(brut)
    jours.to_sql("daily_observations", conn, if_exists="replace", index=False)
    print(f"Jours nettoyés enregistrés : {len(jours)}")
    print("Jours renseignés par colonne :")
    print(jours.count().to_string())
    conn.close()


if __name__ == "__main__":
    main()
