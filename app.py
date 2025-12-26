import streamlit as st
from data_manager import DataManager
from ai_engine import AIEngine
from datetime import date
import pandas as pd

st.set_page_config(page_title="ELGarage SaaS", layout="wide", initial_sidebar_state="collapsed")
st.markdown("""<style>.stButton>button { height: 3em; width: 100%; border-radius: 10px; font-weight: bold; } .report-container { background-color: #f8f9fa; border: 2px solid #f25c05; border-radius: 10px; padding: 15px; margin-bottom: 20px; } #MainMenu {visibility: hidden;} footer {visibility: hidden;} .block-container { padding-top: 2rem; }</style>""", unsafe_allow_html=True)

if 'dm' not in st.session_state: st.session_state['dm'] = DataManager()
dm = st.session_state['dm']

# ==============================================================================
#  ZONE ADMIN / DÉVELOPPEUR (Remplissez ici pour connexion auto)
# ==============================================================================
# Copiez ces infos depuis Supabase > Project Settings > API
ADMIN_SB_URL = "https://votre-projet.supabase.co"  # << REMPLACEZ ICI
ADMIN_SB_KEY = "votre-cle-anon-public-ici"         # << REMPLACEZ ICI
# ==============================================================================

# --- TENTATIVE DE CONNEXION AUTOMATIQUE ---
if not dm.db_ready:
    # 1. On essaie avec les clés "En dur" ci-dessus (Priorité DEV)
    if "votre-projet" not in ADMIN_SB_URL and "votre-cle" not in ADMIN_SB_KEY:
        if dm.connect_system_db(ADMIN_SB_URL, ADMIN_SB_KEY):
            # Succès silencieux, on ne dit rien, ça marche juste.
            pass

    # 2. Si ça a raté, on essaie via les Secrets (Cloud)
    if not dm.db_ready:
        try:
            dm.connect_system_db(st.secrets["supabase"]["url"], st.secrets["supabase"]["key"])
        except: pass

    # 3. Si ça a raté, on essaie via le cache de session
    if not dm.db_ready and 'sys_url' in st.session_state:
        dm.connect_system_db(st.session_state['sys_url'], st.session_state['sys_key'])


# --- UI AUTHENTIFICATION ---
if 'user_logged_in' not in st.session_state: st.session_state['user_logged_in'] = False

if not st.session_state['user_logged_in']:
    col_logo, col_title = st.columns([1, 4])
    with col_logo: st.markdown("<h1>🚗</h1>", unsafe_allow_html=True)
    with col_title: st.title("ELGarage")
    
    # Indicateur de statut serveur
    if dm.db_ready:
        st.caption("🟢 Serveur connecté (Mode Admin Hardcoded)")
    else:
        st.warning("🔴 Serveur déconnecté. Veuillez configurer les clés dans l'onglet 'Créer un compte'.")

    tab_login, tab_register = st.tabs(["Connexion", "Créer un compte (Setup)"])
    
    # --- ONGLET CONNEXION ---
    with tab_login:
        email = st.text_input("Email", key="log_email")
        pwd = st.text_input("Mot de passe", type="password", key="log_pwd")
        
        if st.button("Se connecter", type="primary"):
            if not dm.db_ready:
                st.error("Serveur non connecté. Vérifiez vos variables ADMIN_SB_URL dans le code.")
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

    # --- ONGLET INSCRIPTION ---
    with tab_register:
        st.caption("Création de compte + Initialisation manuelle si besoin.")
        
        c1, c2 = st.columns(2)
        new_nom = c1.text_input("Nom complet")
        new_mail = c2.text_input("Email")
        new_pass = st.text_input("Mot de passe", type="password")
        new_groq = st.text_input("Clé API Groq (gsk_...)", type="password")
        
        st.markdown("---")
        with st.expander("Configuration Système (Si pas connecté auto)"):
            # On pré-remplit avec les valeurs hardcodées si elles existent
            val_url = ADMIN_SB_URL if "votre-projet" not in ADMIN_SB_URL else ""
            val_key = ADMIN_SB_KEY if "votre-cle" not in ADMIN_SB_KEY else ""
            
            sys_url = st.text_input("URL Supabase", value=val_url)
            sys_key = st.text_input("Key Supabase", type="password", value=val_key)

        if st.button("S'inscrire & Initialiser"):
            # 1. Connexion DB
            if not dm.db_ready:
                if dm.connect_system_db(sys_url, sys_key):
                    st.session_state['sys_url'] = sys_url
                    st.session_state['sys_key'] = sys_key
                else:
                    st.error("Impossible de connecter la base de données.")
                    st.stop()
            
            # 2. Création User
            if new_nom and new_mail and new_pass and new_groq:
                ok, msg = dm.register_user(new_nom, new_mail, new_pass, new_groq)
                if ok:
                    st.session_state['user_logged_in'] = True
                    st.session_state['ai'] = AIEngine(api_key=new_groq)
                    st.success("Compte créé !")
                    st.rerun()
                else: st.error(f"Erreur création : {msg}")
            else: st.warning("Remplissez tous les champs personnels.")
    
    st.stop()

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

# Chargement IA
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

