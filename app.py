import streamlit as st
import os
from data_manager import DataManager
from ai_engine import AIEngine
import pandas as pd
from datetime import date

# Configuration de la page (Mode Mobile)
st.set_page_config(page_title="ELGarage Cloud", layout="wide", initial_sidebar_state="collapsed")

# --- CSS POUR MOBILE ---
st.markdown("""
<style>
    /* Boutons plus gros pour le tactile */
    .stButton>button { height: 3em; width: 100%; border-radius: 10px; font-weight: bold; }
    /* Conteneurs de rapport stylisés */
    .report-container { background-color: #f8f9fa; border: 2px solid #f25c05; border-radius: 10px; padding: 15px; margin-bottom: 20px; }
    /* Cacher les éléments inutiles de Streamlit */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .block-container { padding-top: 1rem; padding-bottom: 5rem; }
</style>
""", unsafe_allow_html=True)

# --- INITIALISATION ---
if 'dm' not in st.session_state: st.session_state['dm'] = DataManager()
dm = st.session_state['dm']

# --- TITRE & CONNEXION DB ---
st.title("📱 ELGarage Pro")

# Vérification de la connexion Supabase au démarrage
if not dm.load_db():
    st.error("❌ Erreur de connexion à la Base de Données (Supabase).")
    st.info("⚠️ Vérifiez que vous avez bien configuré les 'Secrets' dans Streamlit Cloud (URL et KEY).")
    st.stop() # On arrête tout si pas de DB
else:
    st.caption(f"{dm.load_status}") # Affiche "Connecté" en petit

# --- SIDEBAR (CONFIGURATION) ---
st.sidebar.title("⚙️ Configuration")

# 1. Clé API Groq
api_key_input = st.sidebar.text_input("Clé API Groq", type="password", help="Nécessaire pour l'IA")
if not api_key_input:
    st.sidebar.warning("⚠️ Clé IA manquante")

# 2. Modèle IA
mod = st.sidebar.selectbox("Modèle IA", ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "gemma2-9b-it"], index=0)

# 3. Initialisation du moteur IA
if api_key_input:
    # On met à jour l'IA si la clé ou le modèle change
    if 'ai' not in st.session_state or st.session_state.get('cur_key') != api_key_input or st.session_state.get('cur_m') != mod:
        st.session_state['ai'] = AIEngine(api_key=api_key_input, model_name=mod)
        st.session_state['cur_key'] = api_key_input
        st.session_state['cur_m'] = mod
        st.toast("Moteur IA prêt !", icon="🤖")

# --- NAVIGATION PRINCIPALE ---
menu = st.radio("Navigation :", ["Tableau de bord", "Nouveau Véhicule"], horizontal=True)

# --- PAGE 1 : NOUVEAU VÉHICULE ---
if menu == "Nouveau Véhicule":
    st.subheader("Ajouter un véhicule")
    with st.form("new_vehicle_form"):
        nom = st.text_input("Nom Client / Réf")
        c1, c2 = st.columns(2)
        marq = c1.text_input("Marque")
        mod_v = c2.text_input("Modèle")
        immat = c1.text_input("Immatriculation")
        annee = c2.number_input("Année", 1990, 2030, 2015)
        km = st.number_input("Kilométrage Actuel", 0, step=100)
        
        if st.form_submit_button("Créer la fiche", type="primary"):
            if nom and marq and immat:
                dm.add_vehicle({
                    "Nom": nom, "Immatriculation": immat, "Marque": marq, 
                    "Modele": mod_v, "Annee": annee, "KM_Actuel": km
                })
                st.success(f"Véhicule {immat} ajouté avec succès !")
                st.rerun()
            else:
                st.error("Merci de remplir au moins le Nom, la Marque et l'Immatriculation.")

# --- PAGE 2 : TABLEAU DE BORD ---
elif menu == "Tableau de bord":
    v_list = dm.get_vehicle_list()
    
    if not v_list:
        st.info("Aucun véhicule dans la base. Commencez par en ajouter un !")
    else:
        # Sélecteur de véhicule
        sel = st.selectbox("Sélectionner Véhicule :", v_list, format_func=lambda x: x[1])
        v_id = sel[0]
        v_info = dm.get_vehicle_info(v_id)

        if v_info:
            # En-tête véhicule
            st.markdown(f"### 🚘 {v_info.get('Marque')} {v_info.get('Modele')}")
            st.caption(f"Immat: {v_info.get('Immatriculation')} | {v_info.get('KM_Actuel')} KM | Année: {v_info.get('Annee')}")
            
            # Onglets de travail
            t1, t2, t3, t4 = st.tabs(["🔧 DIAG", "📝 NOTES", "📅 MAINT", "ℹ️ INFO"])

            # --- ONGLET DIAGNOSTIC ---
            with t1:
                st.write("**Nouveau Diagnostic IA**")
                with st.form("diag_form"):
                    codes = st.text_input("Codes Défaut (OBD)", placeholder="P0300, P0172...")
                    symp = st.text_area("Symptômes / Observations", placeholder="Bruits, voyants, fumée...")
                    go_diag = st.form_submit_button("Lancer Analyse ⚡", type="primary")
                
                if go_diag:
                    if 'ai' not in st.session_state:
                        st.error("Veuillez entrer une Clé API dans le menu (⚙️) à gauche.")
                    else:
                        ai = st.session_state['ai']
                        with st.spinner("L'IA analyse les données..."):
                            hist_txt = dm.get_full_history_text(v_id)
                            res = ai.analyze_obd(v_info, hist_txt, f"Codes: {codes}. Symp: {symp}", date.today())
                            
                            if "error" in res:
                                st.error(res['error'])
                            else:
                                # Affichage du résultat
                                st.markdown(f"""
                                <div class="report-container">
                                    <h3 style="color:#f25c05; text-align:center">{res.get('titre_rapport')}</h3>
                                    <p><strong>Synthèse :</strong> {res.get('resume_court')}</p>
                                    <hr>
                                    <p><strong>Gravité :</strong> {res.get('gravite_score')}/5 &nbsp;|&nbsp; <strong>Santé :</strong> {res.get('sante_vehicule')}</p>
                                    <p><strong>Coût Est. :</strong> {res.get('estimation_cout_pieces_mo')}</p>
                                </div>
                                """, unsafe_allow_html=True)
                                
                                with st.expander("Voir Analyse Détaillée"):
                                    st.write(res.get('analyse_technique_detaillee'))
                                    st.write("---")
                                    st.write("**Plan d'action :**")
                                    st.write(res.get('plan_action_propose'))

                                # Sauvegarde automatique dans Supabase
                                dm.save_diagnostic(
                                    v_id, codes, str(res), 
                                    res.get('estimation_cout_pieces_mo'), 
                                    res.get('sante_vehicule'), 
                                    date.today(), 
                                    res.get('resume_court')
                                )
                                st.toast("Rapport sauvegardé !", icon="✅")

                st.divider()
                st.write("**Historique Diagnostics**")
                dh = dm.get_diagnostic_history(v_id)
                if dh:
                    dfh = pd.DataFrame(dh)
                    # Affichage simplifié pour mobile
                    if 'Date_Detection' in dfh.columns and 'Resume_IA' in dfh.columns:
                        st.dataframe(dfh[['Date_Detection', 'Resume_IA']], hide_index=True, use_container_width=True)
                    else:
                        st.write("Données disponibles mais format incomplet.")
                else:
                    st.caption("Aucun diagnostic précédent.")

            # --- ONGLET NOTES / ENTRETIENS ---
            with t2:
                # Liste des notes
                notes = dm.get_notes_list(v_id)
                if notes:
                    dfn = pd.DataFrame(notes)
                    if 'Date_Intervention' in dfn.columns:
                        st.dataframe(dfn[['Date_Intervention', 'Type', 'Notes']], hide_index=True, use_container_width=True)
                else:
                    st.caption("Aucune intervention enregistrée.")
                
                st.divider()
                # Ajout de note
                with st.expander("➕ Ajouter une intervention"):
                    with st.form("add_note"):
                        d_int = st.date_input("Date", date.today())
                        typ = st.selectbox("Type", ["Entretien", "Réparation Méca", "Diag Élec", "Carrosserie", "Note"])
                        txt = st.text_area("Détails")
                        if st.form_submit_button("Enregistrer"):
                            dm.add_note(v_id, typ, txt, d_int)
                            st.success("Note ajoutée !")
                            st.rerun()

            # --- ONGLET MAINTENANCE ---
            with t3:
                st.write("**Plan de Maintenance Prévisionnel**")
                if st.button("Calculer Plan (IA) 📅", type="primary"):
                    if 'ai' not in st.session_state:
                        st.error("Clé API manquante.")
                    else:
                        with st.spinner("Génération du plan..."):
                            ai = st.session_state['ai']
                            res = ai.check_maintenance_schedule(v_info, dm.get_full_history_text(v_id))
                            if "error" in res:
                                st.error(res['error'])
                            else:
                                st.markdown(res.get('response'))
                                dm.save_echeance(v_id, res.get('response'))

            # --- ONGLET INFOS ---
            with t4:
                st.json(v_info)
