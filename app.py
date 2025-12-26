import streamlit as st
import os
from data_manager import DataManager
from ai_engine import AIEngine
import pandas as pd
from datetime import date

st.set_page_config(page_title="ELGarage Pro", layout="wide", initial_sidebar_state="collapsed")

# --- CSS MOBILE ---
st.markdown("""
<style>
    .stButton>button { height: 3em; width: 100%; border-radius: 10px; font-weight: bold; }
    .report-container { background-color: #f8f9fa; border: 2px solid #f25c05; border-radius: 10px; padding: 15px; margin-bottom: 20px; }
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .block-container { padding-top: 2rem; }
</style>
""", unsafe_allow_html=True)

# --- ETATS GLOBAUX ---
if 'dm' not in st.session_state: st.session_state['dm'] = DataManager()
dm = st.session_state['dm']

if 'supabase_url' not in st.session_state: st.session_state['supabase_url'] = ''
if 'supabase_key' not in st.session_state: st.session_state['supabase_key'] = ''
if 'groq_key' not in st.session_state: st.session_state['groq_key'] = ''
if 'app_unlocked' not in st.session_state: st.session_state['app_unlocked'] = False

# --- ECRAN DE CONNEXION ---
if not st.session_state['app_unlocked']:
    st.title("🔐 Connexion Atelier")
    st.info("Configuration initiale requise pour accéder aux données.")
    
    with st.form("login_form"):
        st.subheader("1. Base de Données (Supabase)")
        url_in = st.text_input("Project URL", value=st.session_state['supabase_url'], placeholder="https://xyz.supabase.co")
        key_in = st.text_input("API Key (anon/public)", type="password", value=st.session_state['supabase_key'])
        
        st.subheader("2. Intelligence Artificielle (Groq)")
        groq_in = st.text_input("GroqCloud API Key", type="password", value=st.session_state['groq_key'], placeholder="gsk_...")
        
        if st.form_submit_button("🚀 Accéder à l'Atelier", type="primary"):
            if url_in and key_in and groq_in:
                with st.spinner("Connexion à la base..."):
                    if dm.connect_db(url_in, key_in):
                        st.session_state['supabase_url'] = url_in
                        st.session_state['supabase_key'] = key_in
                        st.session_state['groq_key'] = groq_in
                        st.session_state['app_unlocked'] = True
                        st.success("Connexion réussie !")
                        st.rerun()
                    else:
                        st.error(f"Impossible de connecter Supabase : {dm.load_status}")
            else:
                st.warning("Tous les champs sont obligatoires.")
    st.stop()

# =========================================================
#  APPLICATION PRINCIPALE
# =========================================================

# Init IA
if 'ai' not in st.session_state:
    st.session_state['ai'] = AIEngine(api_key=st.session_state['groq_key'])
ai = st.session_state['ai']

col_h1, col_h2 = st.columns([3, 1])
with col_h1: st.title("📱 ELGarage Pro")
with col_h2: 
    if st.button("🔒 Déco"):
        st.session_state['app_unlocked'] = False
        st.rerun()

st.caption("✅ Connecté à Supabase (User ID: 1)")

# Navigation
menu = st.radio("Menu :", ["Tableau de bord", "Nouveau Véhicule"], horizontal=True)

# --- 1. NOUVEAU VÉHICULE ---
if menu == "Nouveau Véhicule":
    st.subheader("Ajout Rapide")
    with st.form("new_v"):
        nom = st.text_input("Nom Client (ex: Jean)")
        c1, c2 = st.columns(2)
        marq = c1.text_input("Marque"); mod_v = c2.text_input("Modèle")
        immat = c1.text_input("Immat"); km = c2.number_input("KM", 0)
        annee = st.number_input("Année", 1990, 2030, 2015)
        
        if st.form_submit_button("Créer Fiche", type="primary"):
            dm.add_vehicle({"Nom":nom, "Marque":marq, "Modele":mod_v, "Immatriculation":immat, "Annee":annee, "KM_Actuel":km})
            st.success("Véhicule créé !"); st.rerun()

# --- 2. TABLEAU DE BORD ---
elif menu == "Tableau de bord":
    v_list = dm.get_vehicle_list()
    if not v_list:
        st.info("Aucun véhicule trouvé. Commencez par en ajouter un.")
    else:
        sel = st.selectbox("Véhicule :", v_list, format_func=lambda x: x[1])
        v_id = sel[0]
        v_info = dm.get_vehicle_info(v_id)

        if v_info:
            st.markdown(f"### {v_info.get('Marque')} {v_info.get('Modele')} ({v_info.get('Immatriculation')})")
            
            t1, t2, t3 = st.tabs(["🔧 DIAG", "📝 NOTES", "📅 MAINT"])

            # ONGLET DIAG
            with t1:
                with st.form("diag"):
                    codes = st.text_input("Codes OBD")
                    symp = st.text_area("Symptômes")
                    if st.form_submit_button("Analyser (Groq)", type="primary"):
                        with st.spinner("Analyse IA..."):
                            hist = dm.get_full_history_text(v_id)
                            res = ai.analyze_obd(v_info, hist, f"{codes} {symp}", date.today())
                            if "error" in res: st.error(res['error'])
                            else:
                                st.info(f"Gravité: {res.get('gravite_score')}/5")
                                st.write(res.get('resume_court'))
                                with st.expander("Détails"): st.write(res.get('analyse_technique_detaillee'))
                                dm.save_diagnostic(v_id, codes, str(res), res.get('estimation_cout_pieces_mo'), res.get('sante_vehicule'), date.today(), res.get('resume_court'))
                                st.success("Sauvegardé")

                st.caption("Historique Diags")
                dh = dm.get_diagnostic_history(v_id)
                if dh:
                    dfh = pd.DataFrame(dh)
                    if 'Date_Detection' in dfh.columns:
                        st.dataframe(dfh[['Date_Detection', 'Resume_IA']], hide_index=True, use_container_width=True)

            # ONGLET NOTES (HISTORIQUE)
            with t2:
                notes = dm.get_notes_list(v_id)
                if notes:
                    dfn = pd.DataFrame(notes)
                    if 'Date_Intervention' in dfn.columns:
                        st.dataframe(dfn[['Date_Intervention', 'Type', 'Notes']], hide_index=True, use_container_width=True)
                
                with st.expander("Ajouter Note"):
                    with st.form("addn"):
                        d=st.date_input("Date"); t=st.selectbox("Type",["Entretien","Panne"]); tx=st.text_area("Txt")
                        if st.form_submit_button("Ok"): dm.add_note(v_id,t,tx,d); st.rerun()

            # ONGLET MAINTENANCE
            with t3:
                if st.button("Calculer Plan"):
                    with st.spinner("Calcul..."):
                        res = ai.check_maintenance_schedule(v_info, dm.get_full_history_text(v_id))
                        if "error" not in res: 
                            st.markdown(res.get('response'))
                            dm.save_echeance(v_id, res.get('response'))
