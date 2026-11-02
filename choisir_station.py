"""
Choix de la station : compare 5 stations parisiennes sur 5 semaines (2024-2026)
et calcule la part des heures où la pluie est réellement mesurée.

Lancement : python choisir_station.py
"""
import os
import time

import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("INFOCLIMAT_TOKEN")
STATIONS = ["000BV", "ME098", "000CT", "000EW", "STATIC0061"]
SEMAINES = [("2024-03-04", "2024-03-10"), ("2024-10-07", "2024-10-13"),
            ("2025-05-05", "2025-05-11"), ("2025-11-03", "2025-11-09"),
            ("2026-06-01", "2026-06-07")]

resultats = []
for debut, fin in SEMAINES:
    parametres = {"version": "2", "method": "get", "format": "json",
                  "stations[]": STATIONS, "start": debut, "end": fin, "token": TOKEN}
    donnees = requests.get("https://www.infoclimat.fr/opendata/", params=parametres, timeout=60).json()
    for station in STATIONS:
        mesures = pd.DataFrame(donnees.get("hourly", {}).get(station, []))
        ligne = {"station": station, "semaine": debut}
        if len(mesures) > 0 and "pluie_1h" in mesures:
            mesures["heure"] = pd.to_datetime(mesures["dh_utc"]).dt.floor("h")
            pluie = pd.to_numeric(mesures["pluie_1h"], errors="coerce")
            ligne["pluie_%"] = round(100 * mesures.loc[pluie.notna(), "heure"].nunique() / 168)
        else:
            ligne["pluie_%"] = 0
        resultats.append(ligne)
    time.sleep(1)

tableau = pd.DataFrame(resultats).pivot(index="station", columns="semaine", values="pluie_%")
tableau["moyenne"] = tableau.mean(axis=1).round()
print(tableau.sort_values("moyenne", ascending=False))
print("Station recommandée :", tableau["moyenne"].idxmax())
