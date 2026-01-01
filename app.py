import streamlit as st
from data_manager import DataManager
from ai_engine import AIEngine
from datetime import date
import pandas as pd
import requests
import time

# --- CONFIGURATION INITIALE ---
st.set_page_config(page_title="ELGarage SaaS", layout="wide", initial_sidebar_state="collapsed")
st.markdown("""<style>.stButton>button { height: 3em; width: 100%; border-radius: 10px; font-weight: bold; } .report-container { background-color: #f8f9fa; border: 2px solid #f25c05; border-radius: 10px; padding: 15px; margin-bottom: 20px; } #MainMenu {visibility: hidden;} footer {visibility: hidden;} .block-container { padding-top: 2rem; }</style>""", unsafe_allow_html=True)

# --- MONITORING SERVEUR (NOUVEAU) ---
API_URL = "https://elgarage-api.onrender.com"  # Votre URL Render

def afficher_etat_serveur():
    """Vérifie l'état de l'API et l'affiche dans la sidebar"""
    st.sidebar.header("📡 État du Système")
    status_box = st.sidebar.empty()
    
    if st.sidebar.button("🔄 Vérifier connexion"):
        st.rerun()

    try:
        start_time = time.time()
        # Ping sur la racine de l'API
        response = requests.get(f"{API_URL}/", timeout=5) 
        duration = round((time.time() - start_time) * 1000)

        if response.status_code == 200:
            status_box.success(f"🟢 **EN LIGNE** ({duration}ms)")
        else:
            status_box.warning(f"🟠 **Code {response.status_code}**")
            
    except requests.exceptions.ConnectionError:
        status_box.error("🔴 **HORS LIGNE**")
        st.sidebar.info("Le serveur est peut-être éteint.")
    except requests.exceptions.Timeout:
        status_box.warning("🟠 **LENT (Réveil...)**")
        st.sidebar.caption("Le serveur sort de veille, réessayez dans 30s.")
    except Exception as e:
        status_box.error("Erreur inconnue")

# Appel immédiat pour afficher dans la sidebar
afficher_etat_serveur()

# --- INITIALISATION DATA MANAGER ---
if 'dm' not in st.session_state: st.session_state['dm'] = DataManager()
dm = st.session_state['dm']

if not dm.db_ready:
    st.error("🔴 Erreur Secrets : Configurez .streamlit/secrets.toml")
    st.stop()

settings = dm.get_app_settings()
IS_MAINTENANCE = settings['maintenance_mode'] if settings else True
ACTIVE_KEY = settings['groq_api_key'] if settings else None
if 'success_add_vehicle' not in st.session_state: st.session_state['success_add_vehicle'] = False

# --- LOGIN SYSTEM ---
if 'user_logged_in' not in st.session_state: st.session_state['user_logged_in'] = False

if not st.session_state['user_logged_in']:
    c1, c2 = st.columns([1, 4])
    with c1: st.markdown("# 🚗")
    with c2: st.title("ELGarage")

    if IS_MAINTENANCE: st.warning("🛠️ Système en Maintenance.")

    t1, t2 = st.tabs(["Se connecter", "S'inscrire"])
    with t1:
        is_admin = st.checkbox("Mode Admin")
        email = st.text_input("Email", key="le")
        pwd = st.text_input("Pass", type="password", key="lp")
        if st.button("Go", type="primary"):
            ok, msg = dm.login_user(email, pwd)
            if ok:
                role = dm.current_user.get('role', 'user')
                if is_admin and role != 'admin':
                    st.error("Pas Admin")
                    dm.current_user = None
                else:
                    st.session_state['user_logged_in'] = True
                    user_can_ai = dm.current_user.get('ai_allowed', False)
                    if role == 'admin' and ACTIVE_KEY:
                          st.session_state['ai'] = AIEngine(api_key=ACTIVE_KEY)
                    elif not IS_MAINTENANCE and ACTIVE_KEY and user_can_ai:
                        st.session_state['ai'] = AIEngine(api_key=ACTIVE_KEY)
                    st.rerun()
            else: st.error(msg)
            
    with t2:
        c1,c2=st.columns(2)
        n=c1.text_input("Nom"); m=c2.text_input("Email")
        p=st.text_input("Pass", type="password"); a=st.text_input("Adresse")
        if st.button("Créer"):
            if dm.register_user(n, m, p, a)[0]:
                st.session_state['user_logged_in'] = True
                st.success("OK"); st.rerun()
            else: st.error("Erreur")
    st.stop()

# --- APP PRINCIPALE ---
user = st.session_state['dm'].current_user
role = user.get('role', 'user')
ai_allowed = user.get('ai_allowed', False)
ai = st.session_state.get('ai')

if ai and role != 'admin':
    if (not ai_allowed) or IS_MAINTENANCE: ai = None

c1, c2 = st.columns([3, 1])
with c1: 
    bdg = "🔴 ADMIN" if role == 'admin' else "🟢 CLIENT"
    ia_stat = "✅ IA Active" if ai else ("⛔ IA Non Autorisée" if not ai_allowed else "🛠️ Maintenance")
    st.title(f"Espace {user['nom']}")
    st.caption(f"{bdg} | {ia_stat}")
with c2: 
    if st.button("Déconnexion"):
        st.session_state['user_logged_in'] = False
        st.rerun()

# --- INTERFACE ADMIN ---
if role == 'admin':
    st.divider()
    t1, t2, t3, t4 = st.tabs(["⚙️ Config", "👥 Users", "🚗 Flotte Complète", "📊 Stats"])
    
    with t1:
        st.subheader("Global Settings")
        if IS_MAINTENANCE:
            k = st.text_input("Groq Key", type="password")
            if st.button("Activer"):
                if dm.update_ai_configuration(k)[0]: st.rerun()
        else:
            if st.button("Passer en Maintenance"):
                dm.toggle_maintenance(True); st.rerun()

    with t2:
        st.subheader("Droits IA")
        df_u = dm.get_all_users()
        if not df_u.empty:
            for i, row in df_u.iterrows():
                c1, c2, c3, c4 = st.columns([1, 2, 2, 1])
                c1.write(f"ID: {row['id']}")
                c2.write(f"**{row['nom']}**")
                c3.write(row['email'])
                is_on = row['ai_allowed']
                if c4.toggle("IA", value=is_on, key=f"tg_{row['id']}"):
                    if not is_on: dm.toggle_user_ai(row['id'], True)
                else:
                    if is_on: dm.toggle_user_ai(row['id'], False)

    with t3:
        st.subheader("Flotte Complète")
        vl = dm.get_vehicle_list()
        full_data = dm.get_all_vehicles_admin()
        if not full_data.empty: st.dataframe(full_data, use_container_width=True)
        st.divider()

        if vl:
            st.subheader("✏️ Éditer les Détails Techniques")
            sel = st.selectbox("Sélectionner véhicule", vl, format_func=lambda x: x[1])
            vid = sel[0]
            v = dm.get_vehicle_info(vid)
            
            if v:
                st.info(f"Édition : {v.get('marque')} {v.get('modele')} ({v.get('immatriculation')})")
                with st.form("edit_v_full"):
                    with st.expander("📝 Général", expanded=True):
                        c1, c2, c3 = st.columns(3)
                        vin = c1.text_input("VIN", value=v.get('vin') or "")
                        km = c2.number_input("KM Actuel", value=v.get('km_actuel', 0))
                        coul = c3.text_input("Couleur", value=v.get('couleur') or "")
                        carr = c1.text_input("Carrosserie", value=v.get('carrosserie') or "")
                        genr = c2.text_input("Genre", value=v.get('genre_v') or "")
                    
                    with st.expander("⚙️ Moteur"):
                        c1, c2, c3 = st.columns(3)
                        p_ch = c1.number_input("Puissance (ch)", value=v.get('puissance_ch', 0))
                        p_fi = c2.number_input("Puissance Fisc", value=v.get('puissance_fiscale', 0))
                        cyl = c3.number_input("Cylindrée", value=v.get('cylindree', 0))
                        mot_c = c1.text_input("Code Moteur", value=v.get('code_moteur') or "")
                        soup = c2.number_input("Soupapes", value=v.get('soupapes', 0))
                        co2 = c3.number_input("CO2", value=v.get('co2', 0))
                        carb = c1.text_input("Carburant", value=v.get('carburant') or "")
                        turbo = c2.checkbox("Turbo", value=v.get('turbo', False))

                    with st.expander("🕹️ Transmission & Autres"):
                        c1, c2, c3 = st.columns(3)
                        bv = c1.text_input("Boite Vitesse", value=v.get('boite_vitesse') or "")
                        nb_v = c2.number_input("Nb Rapports", value=v.get('nb_vitesses', 0))
                        roue = c3.text_input("Roues Motrices", value=v.get('roues_motrices') or "")
                        pds = c1.number_input("Poids (kg)", value=v.get('poids_kg', 0))
                        hui = c2.text_input("Viscosité Huile", value=v.get('viscosite_huile') or "")
                        vol_h = c3.number_input("Capacité Huile (L)", value=float(v.get('capacite_huile_l') or 0.0))

                    if st.form_submit_button("Sauvegarder"):
                        updates = {
                            'vin': vin, 'km_actuel': km, 'couleur': coul, 'carrosserie': carr, 'genre_v': genr,
                            'puissance_ch': p_ch, 'puissance_fiscale': p_fi, 'cylindree': cyl, 'code_moteur': mot_c,
                            'soupapes': soup, 'co2': co2, 'carburant': carb, 'turbo': turbo,
                            'boite_vitesse': bv, 'nb_vitesses': nb_v, 'roues_motrices': roue,
                            'poids_kg': pds, 'viscosite_huile': hui, 'capacite_huile_l': vol_h
                        }
                        if dm.admin_update_vehicle(vid, updates):
                            st.success("Mise à jour effectuée !"); st.rerun()

    with t4: st.json(dm.get_app_stats())

# --- INTERFACE USER ---
else:
    nav = st.radio("Menu", ["Mes Véhicules", "Ajouter"], horizontal=True)

    if nav == "Ajouter":
        st.subheader("Ajouter un véhicule")
        if st.session_state['success_add_vehicle']:
            st.success("✅ Véhicule ajouté avec succès !"); st.balloons()
            st.session_state['success_add_vehicle'] = False

        with st.form("a"):
            n=st.text_input("Nom"); c1,c2=st.columns(2); ma=c1.text_input("Marque"); mo=c2.text_input("Modèle")
            im=st.text_input("Immat"); km=st.number_input("KM",0); an=st.number_input("Année",2000)
            if st.form_submit_button("Ajouter", type="primary"):
                if dm.add_vehicle({"Nom":n,"Marque":ma,"Modele":mo,"Immatriculation":im,"Annee":an,"KM_Actuel":km}):
                    st.session_state['success_add_vehicle'] = True; st.rerun()
                else: st.error("Erreur")
    else:
        vl = dm.get_vehicle_list()
        if not vl: st.info("Vide.")
        else:
            sel = st.selectbox("Choix", vl, format_func=lambda x: x[1])
            vid = sel[0]
            inf = dm.get_vehicle_info(vid)
            if inf:
                st.markdown(f"### {inf.get('marque')} {inf.get('modele')}")
                t1,t2,t3 = st.tabs(["Diag IA", "Carnet", "Plan"])
                
                with t1:
                    if not ai: 
                        if not ai_allowed: st.error("🔒 IA non autorisée.")
                        else: st.warning("IA en maintenance.")
                    
                    with st.form("d"):
                        c=st.text_input("Code"); s=st.text_area("Symp"); d=st.date_input("Date", date.today())
                        if st.form_submit_button("Analys", disabled=(ai is None)):
                            with st.spinner("..."):
                                h = dm.get_full_history_text(vid)
                                r = ai.analyze_obd(inf, h, f"{c} {s}", d)
                                if "error" in r: st.error(r['error'])
                                else:
                                    st.markdown(r['resume_court'])
                                    dm.save_diagnostic(vid, c, str(r), r.get('estimation_cout_pieces_mo'), r.get('sante_vehicule'), d, r.get('resume_court'))
                    dh = dm.get_diagnostic_history(vid)
                    if dh: st.dataframe(pd.DataFrame(dh)[['Date_Detection','Code_Defaut','Resume_IA']], hide_index=True)

                with t2:
                    no = dm.get_notes_list(vid)
                    if no: st.dataframe(pd.DataFrame(no)[['Date_Intervention','Type','Notes']], hide_index=True)
                    with st.expander("Ajouter note"):
                        with st.form("nt"):
                            d=st.date_input("D"); t=st.selectbox("T",["Entretien","Autre"]); tx=st.text_area("Txt")
                            if st.form_submit_button("Ok"): dm.add_note(vid,t,tx,d); st.rerun()

                with t3:
                    if st.button("Plan", disabled=(ai is None)):
                        r = ai.check_maintenance_schedule(inf, dm.get_full_history_text(vid))
                        if "error" not in r: st.markdown(r['response']); dm.save_echeance(vid, r['response'])
