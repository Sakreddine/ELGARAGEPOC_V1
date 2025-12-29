import streamlit as st
from data_manager import DataManager
from ai_engine import AIEngine
from datetime import date
import pandas as pd

# ==============================================================================
#  CONFIGURATION GLOBALE (Mode SaaS Centralisé)
# ==============================================================================
# Ces clés permettent à l'application de fonctionner pour TOUS les utilisateurs.
# L'utilisateur final n'a PAS besoin de fournir ses propres clés.
ADMIN_SB_URL = "https://ljdzsqpzbxtrptdaftur.supabase.co" # Votre URL Supabase
ADMIN_SB_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."  # Votre Clé Supabase (Anon)
ADMIN_GROQ_KEY = "gsk_..."                                # Votre Clé API Groq

st.set_page_config(page_title="ELGarage SaaS", layout="wide", initial_sidebar_state="collapsed")
st.markdown("""<style>.stButton>button { height: 3em; width: 100%; border-radius: 10px; font-weight: bold; } .report-container { background-color: #f8f9fa; border: 2px solid #f25c05; border-radius: 10px; padding: 15px; margin-bottom: 20px; } #MainMenu {visibility: hidden;} footer {visibility: hidden;} .block-container { padding-top: 2rem; }</style>""", unsafe_allow_html=True)

if 'dm' not in st.session_state: st.session_state['dm'] = DataManager()
dm = st.session_state['dm']

# --- CONNEXION AUTOMATIQUE AU SYSTEME ---
# L'app se connecte avec les clés de l'Admin au démarrage
if not dm.db_ready:
    # 1. Clés Hardcoded (Priorité)
    if "votre-url" not in ADMIN_SB_URL:
        dm.connect_system_db(ADMIN_SB_URL, ADMIN_SB_KEY)
    # 2. Clés Secrets (Fallback)
    if not dm.db_ready:
        try: dm.connect_system_db(st.secrets["supabase"]["url"], st.secrets["supabase"]["key"])
        except: pass

# ==============================================================================
#  ECRAN D'AUTHENTIFICATION
# ==============================================================================
if 'user_logged_in' not in st.session_state: st.session_state['user_logged_in'] = False

if not st.session_state['user_logged_in']:
    c1, c2 = st.columns([1, 4])
    with c1: st.markdown("# 🚗")
    with c2: st.title("ELGarage Login")
    
    if not dm.db_ready:
        st.error("❌ Erreur Serveur : Clés API Admin non configurées dans le code.")
        st.stop()

    tab_conn, tab_insc = st.tabs(["Connexion", "Inscription (Nouveau)"])

    # --- CONNEXION ---
    with tab_conn:
        email = st.text_input("Email", key="log_email")
        pwd = st.text_input("Mot de passe", type="password", key="log_pwd")
        if st.button("Se connecter", type="primary"):
            ok, msg = dm.login_user(email, pwd)
            if ok:
                st.session_state['user_logged_in'] = True
                # Initialisation IA avec la clé ADMIN globale
                if "gsk_" in ADMIN_GROQ_KEY:
                    st.session_state['ai'] = AIEngine(api_key=ADMIN_GROQ_KEY)
                else:
                    st.warning("⚠️ Clé IA (Groq) non configurée dans le code. L'IA ne fonctionnera pas.")
                st.success("Bienvenue !")
                st.rerun()
            else:
                st.error(msg)

    # --- INSCRIPTION (Utilisateur Standard) ---
    with tab_insc:
        st.caption("Créez votre compte pour gérer vos véhicules.")
        new_nom = st.text_input("Nom complet")
        new_mail = st.text_input("Email")
        new_pass = st.text_input("Mot de passe", type="password")
        st.info("ℹ️ Vous n'avez pas besoin de clé API. Le service est entièrement géré.")
        
        if st.button("S'inscrire"):
            if new_nom and new_mail and new_pass:
                ok, msg = dm.register_user(new_nom, new_mail, new_pass)
                if ok:
                    st.session_state['user_logged_in'] = True
                    # Init IA
                    if "gsk_" in ADMIN_GROQ_KEY: st.session_state['ai'] = AIEngine(api_key=ADMIN_GROQ_KEY)
                    st.success("Compte créé avec succès !")
                    st.rerun()
                else: st.error(msg)
            else: st.warning("Veuillez remplir tous les champs.")
    
    st.stop()

# ==============================================================================
#  APPLICATION CONNECTEE (Routeur Admin vs User)
# ==============================================================================

user = st.session_state['dm'].current_user
role = user.get('role', 'user')

# Header Commun
c1, c2 = st.columns([3, 1])
with c1: 
    badge = "🔴 ADMIN" if role == 'admin' else "🟢 CLIENT"
    st.title(f"Espace {user['nom']}")
    st.caption(f"Statut : {badge}")
with c2: 
    if st.button("Déconnexion"):
        st.session_state['user_logged_in'] = False
        st.rerun()

# Vérification IA
if 'ai' not in st.session_state:
    if "gsk_" in ADMIN_GROQ_KEY:
         st.session_state['ai'] = AIEngine(api_key=ADMIN_GROQ_KEY)
    else:
        st.error("Service IA indisponible (Clé non configurée).")

ai = st.session_state.get('ai')

# ------------------------------------------------------------------------------
#  VUE ADMINISTRATEUR
# ------------------------------------------------------------------------------
if role == 'admin':
    st.divider()
    tabs_admin = st.tabs(["📊 Analytics", "👥 Gestion Utilisateurs", "🚗 Flotte Globale", "⚙️ Paramètres & IA"])

    # 1. Analytics
    with tabs_admin[0]:
        st.subheader("Vue d'ensemble de l'application")
        stats = dm.get_app_stats()
        k1, k2, k3 = st.columns(3)
        k1.metric("Utilisateurs", stats.get('users', 0))
        k2.metric("Véhicules enregistrés", stats.get('vehicles', 0))
        k3.metric("Logs Activité", stats.get('logs', 0))
        st.info("Graphiques détaillés à venir dans la version Prod.")

    # 2. Utilisateurs
    with tabs_admin[1]:
        st.subheader("Base de données Clients")
        df_users = dm.get_all_users()
        if not df_users.empty:
            st.dataframe(df_users, use_container_width=True)
        else: st.write("Aucun utilisateur.")

    # 3. Tous les véhicules
    with tabs_admin[2]:
        st.subheader("Tous les véhicules du système")
        df_cars = dm.get_all_vehicles_admin()
        if not df_cars.empty:
            st.dataframe(df_cars, use_container_width=True)
        else: st.write("Aucun véhicule.")

    # 4. Paramètres
    with tabs_admin[3]:
        st.subheader("Configuration de l'App")
        st.text_input("Nom de l'application", value="ELGarage")
        st.toggle("Mode Maintenance (Bloquer l'accès public)", value=False)
        st.divider()
        st.subheader("Gestion IA (Groq)")
        st.selectbox("Modèle IA Déployé", ["llama-3.3-70b-versatile", "mixtral-8x7b"], index=0)
        st.caption(f"Clé API active : {ADMIN_GROQ_KEY[:5]}...********")

# ------------------------------------------------------------------------------
#  VUE UTILISATEUR STANDARD
# ------------------------------------------------------------------------------
else:
    nav = st.radio("Navigation :", ["Mes Véhicules", "Ajouter un véhicule"], horizontal=True)

    if nav == "Ajouter un véhicule":
        st.subheader("Ajouter un nouveau véhicule")
        with st.form("add_v_form"):
            nom = st.text_input("Nom (ex: Ma voiture pro)")
            c1, c2 = st.columns(2)
            marq = c1.text_input("Marque"); mod = c2.text_input("Modèle")
            immat = c1.text_input("Immatriculation"); km = c2.number_input("Kilométrage", 0); an = st.number_input("Année", 2000)
            
            if st.form_submit_button("Ajouter à mon garage", type="primary"):
                dm.add_vehicle({"Nom":nom, "Marque":marq, "Modele":mod, "Immatriculation":immat, "Annee":an, "KM_Actuel":km})
                st.success("Véhicule ajouté avec succès !"); st.rerun()

    elif nav == "Mes Véhicules":
        v_list = dm.get_vehicle_list()
        if not v_list:
            st.info("Votre garage est vide. Ajoutez votre premier véhicule !")
        else:
            sel = st.selectbox("Choisir un véhicule :", v_list, format_func=lambda x: x[1])
            v_id = sel[0]
            v_info = dm.get_vehicle_info(v_id)

            if v_info:
                st.markdown(f"### 🚘 {v_info['Marque']} {v_info['Modele']}")
                
                t_diag, t_notes, t_maint = st.tabs(["⚡ Diagnostic & IA", "📝 Carnet d'entretien", "📅 Maintenance Prédictive"])

                # --- ONGLET DIAGNOSTIC ---
                with t_diag:
                    st.write("**Analyseur de pannes (IA)**")
                    with st.form("diag_form"):
                        codes = st.text_input("Code(s) défaut OBD2 (ex: P0300)")
                        symp = st.text_area("Symptômes observés / Conditions")
                        d_occ = st.date_input("Date d'apparition", date.today())
                        
                        if st.form_submit_button("Lancer l'analyse Expert", type="primary"):
                            if not ai: st.error("IA non disponible"); st.stop()
                            with st.spinner("Analyse en cours..."):
                                hist = dm.get_full_history_text(v_id)
                                res = ai.analyze_obd(v_info, hist, f"{codes} - {symp}", d_occ)
                                if "error" in res: st.error(res['error'])
                                else:
                                    st.success("Rapport généré")
                                    st.markdown(res['resume_court'])
                                    dm.save_diagnostic(v_id, codes, str(res), res.get('estimation_cout_pieces_mo'), res.get('sante_vehicule'), d_occ, res.get('resume_court'))
                    
                    st.write("---")
                    st.caption("Historique des analyses")
                    dh = dm.get_diagnostic_history(v_id)
                    if dh: st.dataframe(pd.DataFrame(dh)[['Date_Detection', 'Code_Defaut', 'Resume_IA']], hide_index=True, use_container_width=True)

                # --- ONGLET NOTES ---
                with t_notes:
                    st.write("**Historique des interventions**")
                    notes = dm.get_notes_list(v_id)
                    if notes: st.dataframe(pd.DataFrame(notes)[['Date_Intervention', 'Type', 'Notes']], hide_index=True, use_container_width=True)
                    
                    with st.expander("Ajouter une intervention"):
                        with st.form("note_form"):
                            d = st.date_input("Date"); t = st.selectbox("Type", ["Entretien", "Réparation", "CT", "Pneu", "Autre"])
                            desc = st.text_area("Description")
                            if st.form_submit_button("Sauvegarder"):
                                dm.add_note(v_id, t, desc, d); st.rerun()

                # --- ONGLET MAINTENANCE ---
                with t_maint:
                    st.write("**Plan de maintenance généré par IA**")
                    if st.button("Générer le rapport PDF (Simulation)"):
                        with st.spinner("Génération..."):
                            if ai:
                                r = ai.check_maintenance_schedule(v_info, dm.get_full_history_text(v_id))
                                if "error" not in r:
                                    st.markdown(r['response'])
                                    dm.save_echeance(v_id, r['response'])
                                    st.balloons()
