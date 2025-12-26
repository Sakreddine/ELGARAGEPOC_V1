import streamlit as st
from data_manager import DataManager
from ai_engine import AIEngine
from datetime import date
import pandas as pd

st.set_page_config(page_title="ELGarage SaaS", layout="wide", initial_sidebar_state="collapsed")
st.markdown("""<style>.stButton>button { height: 3em; width: 100%; border-radius: 10px; font-weight: bold; } .report-container { background-color: #f8f9fa; border: 2px solid #f25c05; border-radius: 10px; padding: 15px; margin-bottom: 20px; } #MainMenu {visibility: hidden;} footer {visibility: hidden;} .block-container { padding-top: 2rem; }</style>""", unsafe_allow_html=True)

if 'dm' not in st.session_state: st.session_state['dm'] = DataManager()
dm = st.session_state['dm']

# Tentative de connexion silencieuse (si clés en cache ou secrets)
if not dm.db_ready:
    # 1. Via Secrets (Cloud)
    try:
        dm.connect_system_db(st.secrets["supabase"]["url"], st.secrets["supabase"]["key"])
    except:
        # 2. Via Session State (Si on vient de se déconnecter/recharger)
        if 'sys_url' in st.session_state:
            dm.connect_system_db(st.session_state['sys_url'], st.session_state['sys_key'])

# --- LOGIQUE D'AUTHENTIFICATION ---
if 'user_logged_in' not in st.session_state: st.session_state['user_logged_in'] = False

if not st.session_state['user_logged_in']:
    col_logo, col_title = st.columns([1, 4])
    with col_logo: st.markdown("<h1>🚗</h1>", unsafe_allow_html=True)
    with col_title: st.title("ELGarage")
    
    tab_login, tab_register = st.tabs(["Connexion", "Créer un compte (Setup)"])
    
    # --- ONGLET CONNEXION ---
    with tab_login:
        email = st.text_input("Email", key="log_email")
        pwd = st.text_input("Mot de passe", type="password", key="log_pwd")
        if st.button("Se connecter", type="primary"):
            if not dm.db_ready:
                st.error("⚠️ Le serveur n'est pas connecté. Si vous êtes le propriétaire, allez dans l'onglet 'Créer un compte' pour initialiser la connexion avec vos clés.")
            else:
                ok, msg = dm.login_user(email, pwd)
                if ok:
                    st.session_state['user_logged_in'] = True
                    keys = dm.get_user_api_keys()
                    if keys and keys.get('groq'):
                        st.session_state['ai'] = AIEngine(api_key=keys['groq'])
                    st.success("Connexion réussie !")
                    st.rerun()
                else: st.error(msg)

    # --- ONGLET INSCRIPTION (AVEC INIT SYSTEME) ---
    with tab_register:
        st.caption("C'est ici que vous initialisez l'application si c'est la première fois.")
        
        c1, c2 = st.columns(2)
        new_nom = c1.text_input("Nom complet")
        new_mail = c2.text_input("Email")
        new_pass = st.text_input("Mot de passe", type="password")
        new_groq = st.text_input("Clé API Groq (gsk_...)", type="password")
        
        st.markdown("---")
        st.subheader("🛠️ Initialisation Système")
        st.caption("Requis uniquement pour le premier lancement ou nouvel utilisateur.")
        sys_url = st.text_input("URL Supabase (Projet)", value=st.session_state.get('sys_url', ''))
        sys_key = st.text_input("Key Supabase (Anon)", type="password", value=st.session_state.get('sys_key', ''))

        if st.button("S'inscrire & Initialiser"):
            # 1. On essaie de connecter la DB avec les clés fournies
            if dm.connect_system_db(sys_url, sys_key):
                # On sauvegarde les clés en session pour ne pas les perdre au reload
                st.session_state['sys_url'] = sys_url
                st.session_state['sys_key'] = sys_key
                
                # 2. On crée le compte
                if new_nom and new_mail and new_pass and new_groq:
                    ok, msg = dm.register_user(new_nom, new_mail, new_pass, new_groq)
                    if ok:
                        st.session_state['user_logged_in'] = True
                        st.session_state['ai'] = AIEngine(api_key=new_groq)
                        st.success("Compte créé et Système connecté !")
                        st.rerun()
                    else: st.error(f"Connexion DB OK, mais erreur création compte : {msg}")
                else: st.warning("Veuillez remplir les infos personnelles.")
            else:
                st.error("Impossible de connecter Supabase. Vérifiez URL et Key.")
    
    st.stop() # Bloque le reste de l'app tant que pas connecté

# =========================================================
#  APPLICATION PRINCIPALE (Une fois connecté)
# =========================================================

user = st.session_state['dm'].current_user
role = "ADMIN 🔴" if user['id'] == 1 else "User 🟢"

c1, c2 = st.columns([3, 1])
with c1: st.title(f"Atelier de {user['nom']}")
with c2: 
    st.caption(f"Statut : {role}")
    if st.button("Déconnexion"):
        st.session_state['user_logged_in'] = False
        st.rerun()

# Chargement IA de secours
if 'ai' not in st.session_state:
    k = dm.get_user_api_keys()
    if k and k.get('groq'): st.session_state['ai'] = AIEngine(k['groq'])
    else: st.error("Clé IA manquante. Reconnectez-vous."); st.stop()
ai = st.session_state['ai']

menu = st.radio("Navigation", ["Tableau de bord", "Nouveau Véhicule"], horizontal=True)

if menu == "Nouveau Véhicule":
    st.subheader("Nouveau Véhicule")
    with st.form("addv"):
        nom=st.text_input("Propriétaire"); c1,c2=st.columns(2)
        marq=c1.text_input("Marque"); mod=c2.text_input("Modèle")
        immat=c1.text_input("Immat"); km=c2.number_input("KM",0); an=st.number_input("Année",1990,2030,2015)
        if st.form_submit_button("Ajouter", type="primary"):
            dm.add_vehicle({"Nom":nom,"Marque":marq,"Modele":mod,"Immatriculation":immat,"Annee":an,"KM_Actuel":km})
            st.success("OK"); st.rerun()

elif menu == "Tableau de bord":
    v_list = dm.get_vehicle_list()
    if not v_list: st.info("Aucun véhicule.")
    else:
        sel = st.selectbox("Véhicule", v_list, format_func=lambda x: x[1])
        v_id = sel[0]
        v_info = dm.get_vehicle_info(v_id)
        if v_info:
            st.markdown(f"### {v_info['Marque']} {v_info['Modele']} ({v_info['Immatriculation']})")
            t1, t2, t3 = st.tabs(["Diag", "Notes", "Maint"])
            with t1:
                with st.form("d"):
                    c=st.text_input("Codes"); s=st.text_area("Symp")
                    if st.form_submit_button("Analys"):
                        with st.spinner("..."):
                            h=dm.get_full_history_text(v_id)
                            r=ai.analyze_obd(v_info, h, f"{c} {s}", date.today())
                            if "error" in r: st.error(r['error'])
                            else: 
                                st.write(r['resume_court'])
                                dm.save_diagnostic(v_id, c, str(r), r.get('estimation_cout_pieces_mo'), r.get('sante_vehicule'), date.today(), r.get('resume_court'))
                                st.success("Saved")
                dh=dm.get_diagnostic_history(v_id)
                if dh: st.dataframe(pd.DataFrame(dh)[['Date_Detection','Resume_IA']], hide_index=True)
            with t2:
                n=dm.get_notes_list(v_id)
                if n: st.dataframe(pd.DataFrame(n)[['Date_Intervention','Type','Notes']], hide_index=True)
                with st.expander("Add"):
                    with st.form("an"):
                        d=st.date_input("D"); t=st.selectbox("T",["Entretien","Panne"]); tx=st.text_area("Txt")
                        if st.form_submit_button("Ok"): dm.add_note(v_id,t,tx,d); st.rerun()
            with t3:
                if st.button("Plan"):
                    r=ai.check_maintenance_schedule(v_info, dm.get_full_history_text(v_id))
                    if "error" not in r: st.markdown(r['response']); dm.save_echeance(v_id, r['response'])
