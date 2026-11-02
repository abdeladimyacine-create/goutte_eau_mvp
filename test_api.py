"""
Test rapide de l'accès à l'API Infoclimat (clé + station).
Lancement : python test_api.py
"""
import os
import requests
from dotenv import load_dotenv

load_dotenv()
parametres = {
    "version": "2",
    "method": "get",
    "format": "json",
    "stations[]": "000EW",
    "start": "2026-10-01",
    "end": "2026-10-02",
    "token": os.getenv("INFOCLIMAT_TOKEN"),
}
reponse = requests.get("https://www.infoclimat.fr/opendata/", params=parametres, timeout=30)
print("Code HTTP :", reponse.status_code)
print(reponse.text[:1500])
