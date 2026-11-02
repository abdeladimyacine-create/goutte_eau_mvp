# 💧 Projet Goutte d'Eau – MVP

Prototype de prévision du **risque de pluie à 24 h** pour les agriculteurs, développé pour France Météo.
Périmètre du MVP : **une station : Paris 20e - Porte de Vincennes (réseau Infoclimat, identifiant 000EW)**, cohérent avec le pilote du département 75.

Chaîne complète : **API Infoclimat → SQLite → modèle ML → API FastAPI → interface Streamlit**.

## Architecture

```
API Infoclimat ──> collecte.py ──> SQLite (raw_observations)
                                        │
                                  nettoyage.py
                                        ▼
                               SQLite (daily_observations)
                                        │
                                 entrainement.py ──> model/modele.joblib + metriques.json
                                        │
                                     api.py (FastAPI) ──> app.py (Streamlit)
```

| Fichier | Rôle |
|---|---|
| `choisir_station.py` | Compare 5 stations parisiennes (part des heures où la pluie est mesurée) pour choisir la plus complète |
| `test_api.py` | Vérifie que la clé API donne accès à la station |
| `collecte.py` | Récupère les mesures (environ toutes les 10 min) par tranches de 7 jours et les stocke (table `raw_observations`) |
| `nettoyage.py` | Supprime doublons et valeurs aberrantes, agrège par jour (table `daily_observations`) |
| `features.py` | Calcule les variables du modèle (mesures de la veille + saison), partagé par l'entraînement et l'API |
| `entrainement.py` | Entraîne une régression logistique, l'évalue et l'enregistre |
| `api.py` | API REST : `/health`, `/predict`, `/metrics` |
| `app.py` | Interface de démonstration |
| `analyse.ipynb` | Notebook : exploration, qualité et nettoyage des données, analyses univariées et bivariées, modèle, évaluation |

## Installation

```bash
git clone <url-du-repo>
cd goutte-deau-mvp
python -m venv venv
venv\Scripts\activate          # Windows  (Mac/Linux : source venv/bin/activate)
pip install -r requirements.txt
```

Créer un fichier `.env` (voir `.env.example`) avec la clé API Infoclimat :

```
INFOCLIMAT_TOKEN=votre_cle
```

## Lancement (dans l'ordre)

```bash
python test_api.py         # 0. vérifie la clé et l'accès à la station
python collecte.py         # 1. collecte (quelques minutes)
python nettoyage.py        # 2. nettoyage et agrégation journalière
python entrainement.py     # 3. entraînement + indicateurs qualité
# (facultatif) ouvrir analyse.ipynb dans VS Code et cliquer sur « Exécuter tout »
uvicorn api:app --reload   # 4. API  -> http://127.0.0.1:8000/docs
streamlit run app.py       # 5. interface (dans un 2e terminal)
```

## API

| Méthode | Route | Description | Exemple |
|---|---|---|---|
| GET | `/health` | État du service | `{"statut": "ok"}` |
| GET | `/predict?date_cible=AAAA-MM-JJ` | Probabilité et niveau de risque de pluie | `{"probabilite_pluie": 0.644, "risque": "élevé", "alerte": true}` |
| GET | `/metrics` | Indicateurs qualité du modèle | accuracy, rappel, F1, ROC-AUC |

## Choix du modèle

- **Cible** : jour de pluie si cumul ≥ 1 mm (définition Météo-France).
- **Variables** : mesures de la veille (température, pression, humidité, vent, pluie), tendance de pression, saison.
  On prédit donc le jour J avec les données de J-1 : c'est une vraie prévision à 24 h.
- **Modèle** : régression logistique. Léger (entraînement en moins d'une seconde sur CPU), explicable, sans deep learning.
- **Seuil d'alerte** : choisi sur l'entraînement seul (validation chronologique), pour privilégier la détection des pluies.
- **Évaluation** : découpage chronologique (80 % passé / 20 % période récente) et comparaison
  avec une règle de référence (« il pleuvra demain s'il a plu aujourd'hui »).

## Indicateurs qualité (données réelles)

Données : 143 923 mesures (janvier 2024 à octobre 2026) → 1 011 jours nettoyés, 27,8 % de jours de pluie.
Évaluation sur la période de test (201 jours, avril à octobre 2026), seuil d'alerte 0,40 choisi sur l'entraînement :

| Indicateur | Modèle | Référence (persistance) |
|---|---|---|
| Rappel (jours de pluie détectés) | 0,77 | 0,40 |
| F1-score | 0,52 | 0,40 |
| ROC-AUC | 0,84 | – |
| Accuracy | 0,79 | 0,82 |
| Précision | 0,40 | 0,40 |

Détails, graphiques et analyses : `analyse.ipynb` et dossier `figures/`.

## Sécurité

La clé API est stockée dans `.env`, exclu du dépôt via `.gitignore`.
