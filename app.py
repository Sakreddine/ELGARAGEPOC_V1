import streamlit as st
from data_manager import DataManager
from ai_engine import AIEngine
from datetime import date
import pandas as pd

# CONFIGURATION PAGE
st.set_page_config(page_title="ELGarage SaaS", layout="wide", initial_sidebar_state="collapsed")
st.markdown("""<style>.stButton>button { height: 3em; width: 100%; border-radius: 10px; font-weight: bold; } .report-container { background-color: #f8f9fa; border: 2px solid #f25c05; border-radius: 10px; padding: 15px; margin-bottom: 20px; } #MainMenu {visibility: hidden;} footer {visibility: hidden;} .block-container { padding-top: 2rem; }</style>""", unsafe_allow_html=True)

# INIT DATA MANAGER
if 'dm' not in st.session_state: st.session_state['dm'] = DataManager()
dm = st.session_state['dm']

# VÉRIFICATION CONNEXION DB (Critique)
if not dm.db_ready:
    st.error("🔴 Erreur Critique : Impossible de se connecter à la base de données. Veuillez vérifier que les secrets (SUPABASE URL/KEY) sont configurés dans .streamlit/secrets.toml")
    st.stop()

# RECUPERATION ETAT MAINTENANCE & CLE
settings = dm.get_app_settings()
IS_MAINTENANCE = settings['maintenance_mode'] if settings else True
ACTIVE_KEY = settings['groq_api_key'] if settings else None

# ==============================================================================
#  AUTHENTIFICATION (LOGIN / SIGNUP)
# ==============================================================================
if 'user_logged_in' not in st.session_state: st.session_state['user_logged_in'] = False

if not st.session_state['user_logged_in']:
    c1, c2 = st.columns([1, 4])
    with c1: st.markdown("# 🚗")
    with c2: st.title("ELGarage")

    if IS_MAINTENANCE:
        st.warning("🛠️ Maintenance : L'IA est désactivée pour le moment.")

    tab_login, tab_signup = st.tabs(["Se connecter", "S'inscrire"])

    # --- CONNEXION ---
    with tab_login:
        is_admin = st.checkbox("Mode Administrateur")
        email = st.text_input("Email", key="le")
        pwd = st.text_input("Mot de passe", type="password", key="lp")
        
        btn_txt = "Connexion Admin" if is_admin else "Connexion Utilisateur"
        
        if st.button(btn_txt, type="primary"):
            ok, msg = dm.login_user(email, pwd)
            if ok:
                role = dm.current_user.get('role', 'user')
                if is_admin and role != 'admin':
                    st.error("⛔ Ce compte n'a pas les droits Administrateur.")
                    dm.current_user = None # Déco forcée
                else:
                    st.session_state['user_logged_in'] = True
                    # Activation IA si dispo
                    if not IS_MAINTENANCE and ACTIVE_KEY:
                        st.session_state['ai'] = AIEngine(api_key=ACTIVE_KEY)
                    st.success(f"Bienvenue {dm.current_user['nom']} !")
                    st.rerun()
            else: st.error(msg)

    # --- INSCRIPTION (USER SEULEMENT) ---
    with tab_signup:
        st.caption("Création de compte client")
        c1,c2=st.columns(2)
        n=c1.text_input("Nom complet"); m=c2.text_input("Email")
        p=st.text_input("Mot de passe", type="password")
        a=st.text_input("Adresse physique")
        
        if st.button("Créer mon compte"):
            if n and m and p and a:
                ok, msg = dm.register_user(n, m, p, a)
                if ok:
                    st.session_state['user_logged_in'] = True
                    if not IS_MAINTENANCE and ACTIVE_KEY:
                        st.session_state['ai'] = AIEngine(api_key=ACTIVE_KEY)
                    st.success("Compte créé avec succès !")
                    st.rerun()
                else: st.error(msg)
            else: st.warning("Tous les champs sont requis.")
    
    st.stop()

# ==============================================================================
#  APPLICATION CONNECTÉE
# ==============================================================================
user = st.session_state['dm'].current_user
role = user.get('role', 'user')
ai = st.session_state.get('ai')

c1, c2 = st.columns([3, 1])
with c1: 
    badge = "🔴 ADMIN" if role == 'admin' else "🟢 CLIENT"
    st.title(f"Espace {user['nom']}")
    st.caption(f"Statut : {badge} | {'✅ IA Active' if ai else '⚠️ IA Inactive'}")
with c2: 
    if st.button("Déconnexion"):
        st.session_state['user_logged_in'] = False
        st.rerun()

# ------------------------------------------------------------------------------
#  DASHBOARD ADMIN
# ------------------------------------------------------------------------------
if role == 'admin':
    st.divider()
    t1, t2, t3, t4 = st.tabs(["⚙️ IA & Maintenance", "📊 Stats", "👥 Utilisateurs", "🚗 Flotte"])
    
    with t1:
        st.subheader("Pilotage IA")
        status_txt = "MAINTENANCE (IA OFF)" if IS_MAINTENANCE else "ACTIF (IA ON)"
        st.metric("État du système", status_txt)
        
        if IS_MAINTENANCE:
            st.info("Le système est verrouillé. Entrez une clé Groq valide pour activer l'IA pour tous les clients.")
            new_key = st.text_input("Clé API Groq (gsk_...)", type="password")
            if st.button("Valider et Activer"):
                ok, msg = dm.update_ai_configuration(new_key)
                if ok: 
                    st.success(msg)
                    st.session_state['ai'] = AIEngine(api_key=new_key)
                    st.balloons()
                    st.rerun()
                else: st.error(msg)
        else:
            if st.button("🔴 Désactiver l'IA (Passer en maintenance)"):
                dm.toggle_maintenance(True)
                st.warning("Système passé en maintenance.")
                st.rerun()

    with t2:
        s = dm.get_app_stats()
        c1,c2,c3 = st.columns(3)
        c1.metric("Clients", s.get('users',0)); c2.metric("Véhicules", s.get('vehicles',0)); c3.metric("Logs", s.get('logs',0))

    with t3:
        df_u = dm.get_all_users()
        if not df_u.empty: st.dataframe(df_u, use_container_width=True)
        else: st.info("Aucun utilisateur")

    with t4:
        df_v = dm.get_all_vehicles_admin()
        if not df_v.empty: st.dataframe(df_v, use_container_width=True)
        else: st.info("Aucun véhicule")

# ------------------------------------------------------------------------------
#  DASHBOARD USER
# ------------------------------------------------------------------------------
else:
    nav = st.radio("Menu", ["Mes Véhicules", "Ajouter un véhicule"], horizontal=True)

    if nav == "Ajouter un véhicule":
        st.subheader("Nouveau véhicule")
        with st.form("addv"):
            n=st.text_input("Nom (ex: Ma voiture)"); c1,c2=st.columns(2)
            ma=c1.text_input("Marque"); mo=c2.text_input("Modèle")
            im=st.text_input("Immatriculation"); km=c2.number_input("Kilométrage",0); an=st.number_input("Année",2000)
            if st.form_submit_button("Ajouter", type="primary"):
                dm.add_vehicle({"Nom":n,"Marque":ma,"Modele":mo,"Immatriculation":im,"Annee":an,"KM_Actuel":km})
                st.success("Véhicule ajouté !"); st.rerun()

    else: # Mes Véhicules
        v_list = dm.get_vehicle_list()
        if not v_list: 
            st.info("Votre garage est vide.")
        else:
            sel = st.selectbox("Sélectionner un véhicule", v_list, format_func=lambda x: x[1])
            vid = sel[0]
            v_info = dm.get_vehicle_info(vid)

            if v_info:
                st.markdown(f"### {v_info['Marque']} {v_info['Modele']}")
                t1, t2, t3 = st.tabs(["Diagnostic IA", "Carnet", "Maintenance"])

                # DIAGNOSTIC
                with t1:
                    if not ai: 
                        st.warning("⚠️ L'IA est en maintenance. Revenez plus tard.")
                    
                    with st.form("diag"):
                        c=st.text_input("Code OBD"); s=st.text_area("Symptômes"); d=st.date_input("Date", date.today())
                        # Bouton désactivé si pas d'IA
                        if st.form_submit_button("Lancer Analyse", type="primary", disabled=(ai is None)):
                            with st.spinner("Analyse..."):
                                h = dm.get_full_history_text(vid)
                                r = ai.analyze_obd(v_info, h, f"{c} {s}", d)
                                if "error" in r: st.error(r['error'])
                                else:
                                    st.markdown(r['resume_court'])
                                    dm.save_diagnostic(vid, c, str(r), r.get('estimation_cout_pieces_mo'), r.get('sante_vehicule'), d, r.get('resume_court'))
                    
                    dh = dm.get_diagnostic_history(vid)
                    if dh: st.dataframe(pd.DataFrame(dh)[['Date_Detection','Code_Defaut','Resume_IA']], hide_index=True)

                # CARNET
                with t2:
                    no = dm.get_notes_list(vid)
                    if no: st.dataframe(pd.DataFrame(no)[['Date_Intervention','Type','Notes']], hide_index=True)
                    with st.expander("Ajouter une note"):
                        with st.form("nt"):
                            d=st.date_input("D"); t=st.selectbox("T",["Entretien","Réparation","Autre"]); tx=st.text_area("Desc")
                            if st.form_submit_button("Ok"): dm.add_note(vid,t,tx,d); st.rerun()

                # MAINTENANCE
                with t3:
                    if not ai: st.warning("Maintenance indisponible")
                    else:
                        if st.button("Générer Plan"):
                            r = ai.check_maintenance_schedule(v_info, dm.get_full_history_text(vid))
                            if "error" not in r: st.markdown(r['response']); dm.save_echeance(vid, r['response'])
