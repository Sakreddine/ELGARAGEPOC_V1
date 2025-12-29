import streamlit as st
from data_manager import DataManager
from ai_engine import AIEngine
from datetime import date
import pandas as pd

# ==============================================================================
#  CONFIGURATION GLOBALE (Mode SaaS Centralisé)
# ==============================================================================
ADMIN_SB_URL = "https://ljdzsqpzbxtrptdaftur.supabase.co" # Remplacez par votre URL
ADMIN_SB_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxqZHpzcXB6Ynh0cnB0ZGFmdHVyIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjY3NjA3NTIsImV4cCI6MjA4MjMzNjc1Mn0.Z0IaWz901FG360CrGMHAQBdDJ88md2p2mpCe-Y5yOVY"  # Remplacez par votre Clé
ADMIN_GROQ_KEY = "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"# Remplacez par votre Clé Groq

st.set_page_config(page_title="ELGarage SaaS", layout="wide", initial_sidebar_state="collapsed")
st.markdown("""<style>.stButton>button { height: 3em; width: 100%; border-radius: 10px; font-weight: bold; } .report-container { background-color: #f8f9fa; border: 2px solid #f25c05; border-radius: 10px; padding: 15px; margin-bottom: 20px; } #MainMenu {visibility: hidden;} footer {visibility: hidden;} .block-container { padding-top: 2rem; }</style>""", unsafe_allow_html=True)

if 'dm' not in st.session_state: st.session_state['dm'] = DataManager()
dm = st.session_state['dm']

# --- CONNEXION AUTOMATIQUE AU SYSTEME ---
if not dm.db_ready:
    if "votre-url" not in ADMIN_SB_URL:
        dm.connect_system_db(ADMIN_SB_URL, ADMIN_SB_KEY)
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
        st.error("❌ Erreur Serveur : Clés API Admin non configurées.")
        st.stop()

    tab_conn, tab_insc = st.tabs(["Se connecter", "S'inscrire"])

    # --- CONNEXION ---
    with tab_conn:
        # Séparation claire : Admin ou User
        is_admin_mode = st.checkbox("💻 Mode Administrateur")
        
        email = st.text_input("Email", key="log_email")
        pwd = st.text_input("Mot de passe", type="password", key="log_pwd")
        
        btn_label = "Connexion Admin" if is_admin_mode else "Connexion Utilisateur"
        
        if st.button(btn_label, type="primary"):
            ok, msg = dm.login_user(email, pwd)
            if ok:
                user_role = dm.current_user.get('role', 'user')
                
                # Vérification stricte du mode
                if is_admin_mode and user_role != 'admin':
                    st.error("⛔ Accès refusé : Ce compte n'est pas administrateur.")
                    # On déconnecte préventivement
                    dm.current_user = None
                else:
                    # Tout est bon
                    st.session_state['user_logged_in'] = True
                    # Init IA
                    if "gsk_" in ADMIN_GROQ_KEY:
                        st.session_state['ai'] = AIEngine(api_key=ADMIN_GROQ_KEY)
                    st.success(f"Bienvenue {dm.current_user['nom']} !")
                    st.rerun()
            else:
                st.error(msg)

    # --- INSCRIPTION (Utilisateur Standard UNIQUEMENT) ---
    with tab_insc:
        st.caption("Créez votre compte utilisateur.")
        st.info("ℹ️ Les administrateurs ne peuvent pas s'inscrire ici. Contactez le support.")
        
        c1, c2 = st.columns(2)
        new_nom = c1.text_input("Prénom & Nom")
        new_mail = c2.text_input("Email")
        new_pass = st.text_input("Mot de passe", type="password")
        new_addr = st.text_input("Adresse physique complète")
        
        if st.button("S'inscrire"):
            if new_nom and new_mail and new_pass and new_addr:
                ok, msg = dm.register_user(new_nom, new_mail, new_pass, new_addr)
                if ok:
                    st.session_state['user_logged_in'] = True
                    if "gsk_" in ADMIN_GROQ_KEY: st.session_state['ai'] = AIEngine(api_key=ADMIN_GROQ_KEY)
                    st.success("Compte créé avec succès !")
                    st.rerun()
                else: st.error(msg)
            else: st.warning("Tous les champs (y compris l'adresse) sont obligatoires.")
    
    st.stop()

# ==============================================================================
#  APPLICATION CONNECTEE
# ==============================================================================

user = st.session_state['dm'].current_user
role = user.get('role', 'user')

# Header
c1, c2 = st.columns([3, 1])
with c1: 
    badge = "🔴 ADMIN" if role == 'admin' else "🟢 CLIENT"
    st.title(f"Espace {user['nom']}")
    st.caption(f"Statut : {badge}")
with c2: 
    if st.button("Déconnexion"):
        st.session_state['user_logged_in'] = False
        st.rerun()

ai = st.session_state.get('ai')
if not ai: st.warning("IA non active (Clé manquante)")

# ------------------------------------------------------------------------------
#  DASHBOARD ADMIN
# ------------------------------------------------------------------------------
if role == 'admin':
    st.divider()
    tabs_admin = st.tabs(["📊 Analytics", "👥 Utilisateurs", "🚗 Flotte Globale", "⚙️ Config"])

    with tabs_admin[0]:
        st.subheader("Vue d'ensemble")
        stats = dm.get_app_stats()
        k1, k2, k3 = st.columns(3)
        k1.metric("Utilisateurs", stats.get('users', 0))
        k2.metric("Véhicules", stats.get('vehicles', 0))
        k3.metric("Logs", stats.get('logs', 0))

    with tabs_admin[1]:
        st.subheader("Base Clients")
        df_users = dm.get_all_users()
        if not df_users.empty: st.dataframe(df_users, use_container_width=True)
        else: st.write("Vide.")

    with tabs_admin[2]:
        st.subheader("Parc Automobile")
        df_cars = dm.get_all_vehicles_admin()
        if not df_cars.empty: st.dataframe(df_cars, use_container_width=True)
        else: st.write("Vide.")

    with tabs_admin[3]:
        st.subheader("Paramètres")
        st.text_input("Nom App", value="ELGarage")
        st.toggle("Maintenance Mode", value=False)
        st.info(f"Clé IA active : {ADMIN_GROQ_KEY[:5]}...")

# ------------------------------------------------------------------------------
#  DASHBOARD USER
# ------------------------------------------------------------------------------
else:
    nav = st.radio("Menu :", ["Mes Véhicules", "Ajouter un véhicule"], horizontal=True)

    if nav == "Ajouter un véhicule":
        st.subheader("Nouveau véhicule")
        with st.form("add_v"):
            nom = st.text_input("Nom (ex: Ma voiture)"); c1,c2=st.columns(2)
            marq=c1.text_input("Marque"); mod=c2.text_input("Modèle")
            immat=c1.text_input("Plaque"); km=c2.number_input("KM",0); an=st.number_input("Année",2000)
            if st.form_submit_button("Ajouter", type="primary"):
                dm.add_vehicle({"Nom":nom, "Marque":marq, "Modele":mod, "Immatriculation":immat, "Annee":an, "KM_Actuel":km})
                st.success("Ajouté !"); st.rerun()

    elif nav == "Mes Véhicules":
        v_list = dm.get_vehicle_list()
        if not v_list: st.info("Aucun véhicule.")
        else:
            sel = st.selectbox("Véhicule :", v_list, format_func=lambda x: x[1])
            v_id = sel[0]
            v_info = dm.get_vehicle_info(v_id)

            if v_info:
                st.markdown(f"### 🚘 {v_info['Marque']} {v_info['Modele']}")
                t1, t2, t3 = st.tabs(["Diagnostic", "Carnet", "Maintenance"])

                with t1:
                    with st.form("d"):
                        c=st.text_input("Code OBD"); s=st.text_area("Symptômes"); d_occ=st.date_input("Date", date.today())
                        if st.form_submit_button("Analyser"):
                            if not ai: st.error("IA HS"); st.stop()
                            with st.spinner("Analyse..."):
                                h=dm.get_full_history_text(v_id)
                                r=ai.analyze_obd(v_info, h, f"{c} {s}", d_occ)
                                if "error" in r: st.error(r['error'])
                                else:
                                    st.markdown(r['resume_court'])
                                    dm.save_diagnostic(v_id, c, str(r), r.get('estimation_cout_pieces_mo'), r.get('sante_vehicule'), d_occ, r.get('resume_court'))
                    dh = dm.get_diagnostic_history(v_id)
                    if dh: st.dataframe(pd.DataFrame(dh)[['Date_Detection', 'Code_Defaut', 'Resume_IA']], hide_index=True)

                with t2:
                    n = dm.get_notes_list(v_id)
                    if n: st.dataframe(pd.DataFrame(n)[['Date_Intervention', 'Type', 'Notes']], hide_index=True)
                    with st.expander("Ajouter note"):
                        with st.form("nt"):
                            d=st.date_input("D"); t=st.selectbox("T", ["Entretien", "Réparation", "Autre"]); tx=st.text_area("Desc")
                            if st.form_submit_button("Ok"): dm.add_note(v_id, t, tx, d); st.rerun()

                with t3:
                    if st.button("Générer Plan"):
                        if ai:
                            r = ai.check_maintenance_schedule(v_info, dm.get_full_history_text(v_id))
                            if "error" not in r: st.markdown(r['response']); dm.save_echeance(v_id, r['response'])


