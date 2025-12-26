import streamlit as st
import os
# On supprime tkinter qui fait planter le web
# import tkinter as tk 
from data_manager import DataManager
from ai_engine import AIEngine
import pandas as pd
from datetime import date
import tempfile

st.set_page_config(page_title="ELGarage Mobile", layout="wide", initial_sidebar_state="collapsed") # Collapsed pour mobile

# --- CSS MOBILE ---
st.markdown("""
<style>
    /* Ajustements pour écrans tactiles */
    .stButton>button { height: 3em; width: 100%; border-radius: 10px; }
    .report-container { background-color: #f8f9fa; border: 2px solid #f25c05; border-radius: 10px; padding: 15px; }
    /* Cacher le menu hamburger Streamlit pour faire plus "App" */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# --- ETATS ---
if 'dm' not in st.session_state: st.session_state['dm'] = DataManager()
dm = st.session_state['dm']

# --- MAIN ---
st.title("📱 ELGarage Mobile")

# 1. GESTION FICHIER (Remplacé par Uploader)
if not st.session_state.get('db_loaded'):
    st.info("Veuillez charger votre base Excel")
    uploaded_file = st.file_uploader("Choisissez votre fichier Excel", type=['xlsx'])
    
    if uploaded_file is not None:
        # On sauvegarde le fichier temporairement pour que DataManager puisse le lire
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp_file:
            tmp_file.write(uploaded_file.getvalue())
            tmp_path = tmp_file.name
            
        if dm.load_db(tmp_path):
            st.session_state['db_path'] = tmp_path
            st.session_state['db_loaded'] = True
            st.success("Chargé !")
            st.rerun()
    st.stop()

# --- SIDEBAR (Menu) ---
st.sidebar.title("Menu Atelier")

# Clé API
api_key_input = st.sidebar.text_input("Clé Groq", type="password")
if not api_key_input and 'cur_key' not in st.session_state:
    st.warning("Clé API manquante (Menu à gauche)")

# Modèle
mod = st.sidebar.selectbox("Modèle", ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"], index=0)

# Init IA
if api_key_input:
    st.session_state['cur_key'] = api_key_input

if 'cur_key' in st.session_state:
    if 'ai' not in st.session_state or st.session_state.get('cur_m') != mod:
        st.session_state['ai'] = AIEngine(api_key=st.session_state['cur_key'], model_name=mod)
        st.session_state['cur_m'] = mod
    ai = st.session_state['ai']

# --- NAVIGATION MOBILE ---
# Sur mobile, les onglets du haut sont mieux que la sidebar
menu = st.radio("Aller à :", ["Tableau de bord", "Nouveau Véhicule"], horizontal=True)

if menu == "Nouveau Véhicule":
    st.subheader("Nouveau Véhicule")
    with st.form("new"):
        nom=st.text_input("Nom Client")
        c1, c2 = st.columns(2)
        marq=c1.text_input("Marque"); mod_v=c2.text_input("Modèle")
        immat=c1.text_input("Immat"); annee=c2.number_input("Année",1990,2030)
        km=st.number_input("KM",0)
        if st.form_submit_button("Créer Véhicule"):
            dm.add_vehicle({"Nom":nom,"Immatriculation":immat,"Marque":marq,"Modele":mod_v,"Annee":annee,"KM_Actuel":km})
            st.success("OK"); st.rerun()

elif menu == "Tableau de bord":
    v_list = dm.get_vehicle_list()
    if v_list:
        sel = st.selectbox("Véhicule", v_list, format_func=lambda x: x[1])
        v_id = sel[0]
        v_info = dm.get_vehicle_info(v_id)

        st.markdown(f"**{v_info.get('Marque')} {v_info.get('Modele')}** ({v_info.get('Immatriculation')})")
        
        # Onglets simplifiés pour mobile
        t1, t2, t3 = st.tabs(["🔧 DIAG", "📝 NOTES", "📅 MAINT"])

        with t1:
            st.caption("Diagnostic IA")
            with st.form("diag"):
                codes = st.text_input("Codes OBD")
                symp = st.text_area("Symptômes")
                go = st.form_submit_button("Analyser ⚡")
            
            if go:
                if 'ai' not in st.session_state:
                    st.error("Entrez la clé API dans le menu >")
                else:
                    with st.spinner("Analyse..."):
                        hist_txt = dm.get_full_history_text(v_id)
                        res = ai.analyze_obd(v_info, hist_txt, f"Codes: {codes}. Symp: {symp}", date.today())
                        if "error" in res: st.error(res['error'])
                        else:
                            st.info(f"Gravité: {res.get('gravite_score')}/5")
                            st.write(res.get('resume_court'))
                            with st.expander("Voir détails"):
                                st.write(res.get('analyse_technique_detaillee'))
                                st.write(res.get('plan_action_propose'))
                            dm.save_diagnostic(v_id, codes, str(res), res.get('estimation_cout_pieces_mo'), res.get('sante_vehicule'), date.today(), res.get('resume_court'))

            st.divider()
            st.caption("Historique")
            dh = dm.get_diagnostic_history(v_id)
            if dh:
                dfh = pd.DataFrame(dh)
                # Affichage simple pour mobile
                col_res = 'Resume_IA' if 'Resume_IA' in dfh.columns else 'Code_Defaut'
                col_date = 'Date_Detection' if 'Date_Detection' in dfh.columns else 'Date'
                if col_res in dfh.columns:
                    st.dataframe(dfh[[col_date, col_res]], hide_index=True, use_container_width=True)

        with t2:
            notes = dm.get_notes_list(v_id)
            if notes: 
                dfn = pd.DataFrame(notes)
                # Logique colonne date robuste
                d_col = 'Date_Intervention' if 'Date_Intervention' in dfn.columns else ('Date' if 'Date' in dfn.columns else 'Date_Saisie')
                cols = [c for c in [d_col, 'Type', 'Notes'] if c in dfn.columns]
                st.dataframe(dfn[cols], hide_index=True)
            
            with st.expander("Ajouter Note"):
                with st.form("add_n"):
                    ty=st.selectbox("Type", ["Entretien", "Panne", "Note"])
                    tx=st.text_area("Note")
                    if st.form_submit_button("Sauvegarder"):
                        dm.add_note(v_id, ty, tx, date.today()); st.rerun()

        with t3:
            if st.button("Calculer Plan"):
                if 'ai' not in st.session_state: st.error("Clé API manquante")
                else:
                    with st.spinner("Calcul..."):
                        res = ai.check_maintenance_schedule(v_info, dm.get_full_history_text(v_id))
                        if "error" not in res: st.markdown(res.get('response'))

    else: st.warning("Ajoutez un véhicule")

# Bouton de sauvegarde explicite (pour Excel)
if st.sidebar.button("💾 Sauvegarder Excel"):
    # Sur le web, on ne peut pas écraser le fichier local de l'utilisateur.
    # On doit lui proposer de télécharger le fichier modifié.
    with open(st.session_state['db_path'], "rb") as f:
        st.download_button("Télécharger Base Modifiée", f, file_name="Garage_DB_Updated.xlsx")