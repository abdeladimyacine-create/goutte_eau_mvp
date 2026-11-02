"""
Étape 1 - Collecte des données
Récupère les observations horaires d'une station via l'API Infoclimat (Open Data)
et les enregistre dans la base SQLite (table raw_observations).

Lancement : python collecte.py
"""
import os
import time
import sqlite3
from datetime import date, timedelta

import requests
from dotenv import load_dotenv

# ---------- Paramètres ----------
load_dotenv()
TOKEN = os.getenv("INFOCLIMAT_TOKEN")

STATION = "000EW"            # Paris 20e - Porte de Vincennes (75), choisie avec choisir_station.py
DATE_DEBUT = date(2024, 1, 1)
DATE_FIN = date(2026, 10, 31)
DB_PATH = "data/meteo.db"
URL_API = "https://www.infoclimat.fr/opendata/"

# Seules les colonnes utiles au modèle sont conservées (dataset minimal)
CHAMPS = ["temperature", "pression", "humidite", "vent_moyen",
          "vent_rafales", "pluie_1h", "pluie_3h"]


def creer_table(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS raw_observations (
            station      TEXT,
            dh_utc       TEXT,
            temperature  REAL,
            pression     REAL,
            humidite     REAL,
            vent_moyen   REAL,
            vent_rafales REAL,
            pluie_1h     REAL,
            pluie_3h     REAL,
            UNIQUE(station, dh_utc)
        )
    """)
    conn.commit()


def appeler_api(debut, fin):
    """Appelle l'API pour une période de 7 jours maximum (limite Infoclimat)."""
    parametres = {
        "version": "2",
        "method": "get",
        "format": "json",
        "stations[]": STATION,
        "start": debut.isoformat(),
        "end": fin.isoformat(),
        "token": TOKEN,
    }
    reponse = requests.get(URL_API, params=parametres, timeout=30)
    reponse.raise_for_status()
    return reponse.json()


def en_nombre(valeur):
    """Convertit une valeur de l'API en nombre (None si vide)."""
    try:
        return float(valeur)
    except (TypeError, ValueError):
        return None


def enregistrer(conn, mesures):
    lignes = []
    for m in mesures:
        ligne = [STATION, m.get("dh_utc")]
        for champ in CHAMPS:
            ligne.append(en_nombre(m.get(champ)))
        lignes.append(ligne)
    conn.executemany(
        "INSERT OR IGNORE INTO raw_observations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        lignes,
    )
    conn.commit()
    return len(lignes)


def main():
    if not TOKEN:
        print("Erreur : ajoute INFOCLIMAT_TOKEN=ta_cle dans le fichier .env")
        return

    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    creer_table(conn)

    jour = DATE_DEBUT
    while jour < DATE_FIN:
        fin_semaine = min(jour + timedelta(days=6), DATE_FIN)
        try:
            donnees = appeler_api(jour, fin_semaine)
            mesures = donnees.get("hourly", {}).get(STATION, [])
            nb = enregistrer(conn, mesures)
            print(f"{jour} -> {fin_semaine} : {nb} mesures")
        except Exception as erreur:
            print(f"{jour} -> {fin_semaine} : échec ({erreur})")
        jour = fin_semaine + timedelta(days=1)
        time.sleep(1)  # on respecte le "fair use" du service (bénévole)

    total = conn.execute("SELECT COUNT(*) FROM raw_observations").fetchone()[0]
    print(f"Terminé : {total} observations en base")
    conn.close()


if __name__ == "__main__":
    main()
