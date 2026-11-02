"""
Étape 5 - Interface de démonstration (Streamlit)
Appelle l'API et affiche le risque de pluie pour la date choisie.

Lancement (l'API doit tourner en parallèle) : streamlit run app.py
"""
from datetime import date

import requests
import streamlit as st

URL_API = "http://127.0.0.1:8000"

st.set_page_config(page_title="Goutte d'Eau - Risque de pluie", page_icon="💧")

st.title("💧 Goutte d'Eau - Risque de pluie à 24 h")
st.write("Choisissez une date pour connaître le risque de pluie estimé "
         "par le modèle (station Paris 20e - Porte de Vincennes).")

# Date proposée par défaut : la prochaine date que le modèle peut prévoir
try:
    date_defaut = date.fromisoformat(requests.get(f"{URL_API}/health", timeout=5).json()["derniere_date_prevue"])
except Exception:
    date_defaut = date.today()

date_choisie = st.date_input("Date de la prévision (AAAA/MM/JJ)", value=date_defaut,
                             help="L'estimation utilise les mesures de la veille.")

if st.button("Obtenir l'estimation", use_container_width=True):
    try:
        reponse = requests.get(f"{URL_API}/predict",
                               params={"date_cible": str(date_choisie)}, timeout=10)
    except requests.exceptions.ConnectionError:
        st.error("L'API est inaccessible. Vérifiez qu'elle est bien lancée.")
        st.stop()

    if reponse.status_code != 200:
        st.warning(reponse.json().get("detail", "Aucune estimation disponible."))
    else:
        resultat = reponse.json()
        pourcentage = round(resultat["probabilite_pluie"] * 100)
        texte = {"faible": "🟢 Risque faible", "modéré": "🟠 Risque modéré",
                 "élevé": "🔴 Risque élevé"}[resultat["risque"]]

        st.metric("Probabilité de pluie (≥ 1 mm)", f"{pourcentage} %")
        st.subheader(texte)
        if resultat.get("alerte"):
            st.warning("Alerte : de la pluie (au moins 1 mm) est probable ce jour-là. "
                       "Pensez à adapter vos interventions.")

        if resultat["pluie_observee_mm"] is not None:
            st.info(f"Pluie réellement mesurée ce jour-là : "
                    f"{resultat['pluie_observee_mm']} mm")

with st.expander("Qualité du modèle"):
    try:
        m = requests.get(f"{URL_API}/metrics", timeout=10).json()
        s = m["scores_modele"]
        col1, col2, col3 = st.columns(3)
        col1.metric("Bonnes prédictions (accuracy)", f"{round(s['accuracy'] * 100)} %")
        col2.metric("Jours de pluie détectés", f"{round(s['rappel'] * 100)} %")
        col3.metric("F1-score", s["f1"])
        st.caption(f"Évalué sur {m['nb_jours_test']} jours ({m['periode_test']}).")
    except requests.exceptions.ConnectionError:
        st.write("Indicateurs indisponibles : API non lancée.")
