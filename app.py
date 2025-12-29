import streamlit as st
from data_manager import DataManager
from ai_engine import AIEngine
from datetime import date
import pandas as pd

st.set_page_config(page_title="ELGarage SaaS", layout="wide", initial_sidebar_state="collapsed")
st.markdown("""<style>.stButton>button { height: 3em; width: 100%; border-radius: 10px; font-weight: bold; } .report-container { background-color: #f8f9fa; border: 2px solid #f25c05; border-radius: 10px; padding: 15px; margin-bottom: 20px; } #MainMenu {visibility: hidden;} footer {visibility: hidden;} .block-container { padding-top: 2rem; }</style>""", unsafe_allow_html=True)

if 'dm' not in st.session_state: st.session_state['dm'] = DataManager()
dm = st.session_state['dm']

if not dm.db_ready:
    st.error("🔴 Erreur Secrets : Configurez .streamlit/secrets.toml")
    st.stop()

# Charger Settings
settings = dm.get_app_settings()
IS_MAINTENANCE = settings['maintenance_mode'] if settings else True
ACTIVE_KEY = settings['groq_api_key'] if settings else None

# ==============================================================================
#  LOGIN
# ==============================================================================
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
                    # IA active globalement ET pour ce user ?
                    user_can_ai = dm.current_user.get('ai_allowed', False)
                    if not IS_MAINTENANCE and ACTIVE_KEY and user_can_ai:
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

# ==============================================================================
#  APP
# ==============================================================================
user = st.session_state['dm'].current_user
role = user.get('role', 'user')
ai_allowed = user.get('ai_allowed', False)
ai = st.session_state.get('ai')

# Enforce User AI Right check
if ai and (not ai_allowed) and role != 'admin':
    ai = None # Désactiver localement si l'admin a coupé l'accès

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

# --- ADMIN ---
if role == 'admin':
    st.divider()
    t1, t2, t3, t4 = st.tabs(["⚙️ Config", "👥 Gestion Users", "🚗 Flotte & Édition", "📊 Stats"])
    
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
        st.subheader("Gérer les droits IA")
        df_u = dm.get_all_users()
        if not df_u.empty:
            # Affichage liste avec Toggle
            for i, row in df_u.iterrows():
                c1, c2, c3, c4 = st.columns([1, 2, 2, 1])
                c1.write(f"ID: {row['id']}")
                c2.write(f"**{row['nom']}**")
                c3.write(row['email'])
                # Toggle pour activer/désactiver IA
                is_on = row['ai_allowed']
                if c4.toggle("IA", value=is_on, key=f"tg_{row['id']}"):
                    if not is_on: dm.toggle_user_ai(row['id'], True)
                else:
                    if is_on: dm.toggle_user_ai(row['id'], False)

    with t3:
        st.subheader("Édition Véhicules")
        vl = dm.get_vehicle_list() # Tous les vehicules
        if vl:
            sel = st.selectbox("Choisir véhicule à modifier", vl, format_func=lambda x: x[1])
            vid = sel[0]
            v_data = dm.get_vehicle_info(vid)
            
            if v_data:
                st.info(f"Véhicule : {v_data.get('marque')} {v_data.get('modele')} ({v_data.get('immatriculation')}) - {v_data.get('annee')}")
                st.caption("🔒 Les champs ci-dessus sont verrouillés (Identity). Modifiez les détails techniques ci-dessous :")
                
                with st.form("edit_v"):
                    c1, c2 = st.columns(2)
                    n_km = c1.number_input("Kilométrage", value=v_data.get('km_actuel', 0))
                    n_col = c2.text_input("Couleur", value=v_data.get('couleur', ''))
                    n_boite = c1.text_input("Boite Vitesse", value=v_data.get('boite_vitesse', ''))
                    n_carb = c2.text_input("Carburant", value=v_data.get('carburant', ''))
                    
                    if st.form_submit_button("Enregistrer modifications"):
                        changes = {'km_actuel': n_km, 'couleur': n_col, 'boite_vitesse': n_boite, 'carburant': n_carb}
                        if dm.admin_update_vehicle(vid, changes):
                            st.success("Mis à jour !"); st.rerun()

    with t4:
        st.json(dm.get_app_stats())

# --- USER ---
else:
    nav = st.radio("Menu", ["Mes Véhicules", "Ajouter"], horizontal=True)

    if nav == "Ajouter":
        with st.form("a"):
            n=st.text_input("Nom"); c1,c2=st.columns(2); ma=c1.text_input("Marque"); mo=c2.text_input("Modèle")
            im=st.text_input("Immat"); km=st.number_input("KM",0); an=st.number_input("Année",2000)
            if st.form_submit_button("Ajouter"):
                dm.add_vehicle({"Nom":n,"Marque":ma,"Modele":mo,"Immatriculation":im,"Annee":an,"KM_Actuel":km})
                st.success("OK"); st.rerun()
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
                        if not ai_allowed: st.error("🔒 Votre abonnement ne permet pas l'utilisation de l'IA. Contactez l'admin.")
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
                            if "error" not in r: st.markdown(r['response']); dm.save_echeance(vid, r['response'])

