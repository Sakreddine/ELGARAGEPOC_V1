import streamlit as st
from data_manager import DataManager
from ai_engine import AIEngine
from datetime import date
import pandas as pd
import requests # N'oubliez pas: pip install requests
import time

# --- CONFIGURATION INITIALE ---
st.set_page_config(page_title="ELGarage Admin", layout="wide", initial_sidebar_state="expanded")

# --- CSS POUR LE STATUS SERVEUR (STYLE LED) ---
st.markdown("""
<style>
    .stButton>button { height: 3em; width: 100%; border-radius: 10px; font-weight: bold; } 
    .report-container { background-color: #f8f9fa; border: 2px solid #f25c05; border-radius: 10px; padding: 15px; margin-bottom: 20px; } 
    
    /* Styles spécifiques pour le moniteur serveur */
    .server-status-box {
        padding: 12px;
        border-radius: 8px;
        margin-bottom: 20px;
        text-align: center;
        font-family: sans-serif;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .status-online {
        background-color: #d1e7dd;
        color: #0f5132;
        border: 1px solid #badbcc;
    }
    .status-offline {
        background-color: #f8d7da;
        color: #842029;
        border: 1px solid #f5c2c7;
    }
    .status-loading {
        background-color: #fff3cd;
        color: #664d03;
        border: 1px solid #ffecb5;
    }
    .ping-text { font-size: 0.8em; opacity: 0.8; }
</style>
""", unsafe_allow_html=True)

# --- FONCTION DE MONITORING ---
API_URL = "https://elgarage-api.onrender.com"

def afficher_etat_serveur():
    with st.sidebar:
        st.header("📡 État du Serveur")
        status_placeholder = st.empty()
        
        # Bouton manuel pour rafraîchir
        if st.button("🔄 Actualiser Ping", key="refresh_ping"):
            st.rerun()

        try:
            start_time = time.time()
            # On tente de joindre la racine "/" de l'API
            # Timeout de 4s : Si ça dépasse, on considère que le serveur dort ou démarre
            response = requests.get(f"{API_URL}/", timeout=4)
            latence = round((time.time() - start_time) * 1000)

            if response.status_code == 200:
                status_placeholder.markdown(f"""
                <div class="server-status-box status-online">
                    <strong>🟢 EN LIGNE</strong><br>
                    <span class="ping-text">Latence: {latence}ms</span>
                </div>
                """, unsafe_allow_html=True)
            else:
                status_placeholder.markdown(f"""
                <div class="server-status-box status-loading">
                    <strong>🟠 BIZARRE</strong><br>
                    <span class="ping-text">Code: {response.status_code}</span>
                </div>
                """, unsafe_allow_html=True)

        except requests.exceptions.Timeout:
            status_placeholder.markdown("""
            <div class="server-status-box status-loading">
                <strong>⏳ DÉMARRAGE...</strong><br>
                <span class="ping-text">Le serveur se réveille (Cold Start)</span>
            </div>
            """, unsafe_allow_html=True)
            st.info("Le serveur gratuit Render s'endort après 15min d'inactivité. Attendez 30sec.")

        except requests.exceptions.ConnectionError:
            status_placeholder.markdown("""
            <div class="server-status-box status-offline">
                <strong>🔴 HORS LIGNE</strong><br>
                <span class="ping-text">Impossible de joindre l'API</span>
            </div>
            """, unsafe_allow_html=True)
        except Exception as e:
            st.error(f"Erreur Moniteur: {e}")
        
        st.divider() # Ligne de séparation visuelle

# --- EXECUTION IMMEDIATE DU MONITORING ---
# On l'appelle ici pour qu'il s'affiche TOUT LE TEMPS, même si pas connecté
afficher_etat_serveur()


# --- INITIALISATION DATA MANAGER ---
if 'dm' not in st.session_state: st.session_state['dm'] = DataManager()
dm = st.session_state['dm']

if not dm.db_ready:
    st.error("🔴 Erreur Critique : Base de données inaccessible. Vérifiez `.streamlit/secrets.toml`")
    st.stop()

settings = dm.get_app_settings()
IS_MAINTENANCE = settings['maintenance_mode'] if settings else True
ACTIVE_KEY = settings['groq_api_key'] if settings else None
if 'success_add_vehicle' not in st.session_state: st.session_state['success_add_vehicle'] = False

# --- LOGIQUE DE CONNEXION ---
if 'user_logged_in' not in st.session_state: st.session_state['user_logged_in'] = False

if not st.session_state['user_logged_in']:
    col_logo, col_title = st.columns([1, 4])
    with col_logo: st.markdown("# 🚗")
    with col_title: st.title("ELGarage Admin")

    if IS_MAINTENANCE: st.warning("🛠️ Le système est actuellement en mode Maintenance.")

    tab_login, tab_signup = st.tabs(["Se connecter", "S'inscrire"])
    
    with tab_login:
        is_admin_check = st.checkbox("Mode Admin")
        email_input = st.text_input("Email", key="login_email")
        pass_input = st.text_input("Mot de passe", type="password", key="login_pass")
        
        if st.button("Se connecter", type="primary"):
            success, msg = dm.login_user(email_input, pass_input)
            if success:
                role = dm.current_user.get('role', 'user')
                # Vérification sécurité Admin
                if is_admin_check and role != 'admin':
                    st.error("⛔ Accès Refusé : Ce compte n'a pas les droits Administrateur.")
                    dm.current_user = None
                else:
                    st.session_state['user_logged_in'] = True
                    # Init IA si autorisé
                    user_can_ai = dm.current_user.get('ai_allowed', False)
                    if role == 'admin' and ACTIVE_KEY:
                          st.session_state['ai'] = AIEngine(api_key=ACTIVE_KEY)
                    elif not IS_MAINTENANCE and ACTIVE_KEY and user_can_ai:
                        st.session_state['ai'] = AIEngine(api_key=ACTIVE_KEY)
                    st.rerun()
            else:
                st.error(f"❌ {msg}")
            
    with tab_signup:
        c1, c2 = st.columns(2)
        new_nom = c1.text_input("Nom Complet")
        new_email = c2.text_input("Email")
        new_pass = st.text_input("Mot de passe", type="password")
        new_addr = st.text_input("Adresse physique")
        
        if st.button("Créer un compte"):
            success, msg = dm.register_user(new_nom, new_email, new_pass, new_addr)
            if success:
                st.session_state['user_logged_in'] = True
                st.success("✅ Compte créé avec succès !"); st.rerun()
            else:
                st.error(f"Erreur : {msg}")
    st.stop() # Arrête le script ici si pas connecté

# --- APPLICATION PRINCIPALE (Une fois connecté) ---
user = st.session_state['dm'].current_user
role = user.get('role', 'user')
ai_allowed = user.get('ai_allowed', False)
ai = st.session_state.get('ai')

# Vérification forcée maintenance pour les users non-admin
if ai and role != 'admin':
    if (not ai_allowed) or IS_MAINTENANCE: ai = None

# Header Utilisateur
c1, c2 = st.columns([3, 1])
with c1: 
    badge = "🔴 ADMIN" if role == 'admin' else "🟢 CLIENT"
    ia_status = "✅ IA Active" if ai else ("⛔ IA Interdite" if not ai_allowed else "🛠️ Maintenance")
    st.title(f"Bonjour, {user['nom']}")
    st.caption(f"{badge} | {ia_status}")
with c2: 
    if st.button("Déconnexion"):
        st.session_state['user_logged_in'] = False
        st.session_state['dm'].current_user = None
        st.rerun()

# --- VUE ADMINISTRATEUR ---
if role == 'admin':
    st.divider()
    tab_conf, tab_users, tab_flotte, tab_stats = st.tabs(["⚙️ Config", "👥 Utilisateurs", "🚗 Parc Véhicules", "📊 Données"])
    
    with tab_conf:
        st.subheader("Configuration Système")
        if IS_MAINTENANCE:
            st.info("Le système est verrouillé (Maintenance).")
            key_input = st.text_input("Clé API Groq (gsk_...)", type="password", value=ACTIVE_KEY if ACTIVE_KEY else "")
            
            if st.button("ACTIVER LE SYSTÈME", type="primary"):
                if not key_input:
                    st.error("Clé manquante.")
                else:
                    with st.spinner("Test de la clé Groq..."):
                        ok, msg = dm.update_ai_configuration(key_input)
                        if ok:
                            st.success(f"Système Activé ! {msg}")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error(f"Erreur activation : {msg}")
        else:
            st.success("✅ Système ACTIF. L'IA est opérationnelle.")
            if st.button("Passer en Maintenance (Urgence)"):
                dm.toggle_maintenance(True); st.rerun()

    with tab_users:
        st.subheader("Gestion des Accès")
        df_users = dm.get_all_users()
        if not df_users.empty:
            st.dataframe(df_users[['id','nom','email','role','ai_allowed','created_at']], width=None, use_container_width=True, hide_index=True)
            
            st.write("---")
            st.write("### Droits d'accès à l'IA")
            for i, row in df_users.iterrows():
                col_name, col_email, col_toggle = st.columns([2, 2, 1])
                col_name.write(f"**{row['nom']}**")
                col_email.caption(row['email'])
                
                is_allowed = row['ai_allowed']
                # Toggle unique par ID
                if col_toggle.toggle("Autoriser IA", value=is_allowed, key=f"user_toggle_{row['id']}"):
                    if not is_allowed: dm.toggle_user_ai(row['id'], True)
                else:
                    if is_allowed: dm.toggle_user_ai(row['id'], False)

    with tab_flotte:
        st.subheader("Gestion Technique Flotte")
        full_fleet = dm.get_all_vehicles_admin()
        if not full_fleet.empty:
            st.dataframe(full_fleet, use_container_width=True)
        
        st.divider()
        vehicle_list = dm.get_vehicle_list() # Format (id, "Marque Modele")

        if vehicle_list:
            st.subheader("🔧 Éditeur Technique")
            selection = st.selectbox("Choisir un véhicule à modifier", vehicle_list, format_func=lambda x: x[1])
            vid = selection[0]
            v_info = dm.get_vehicle_info(vid)
            
            if v_info:
                with st.form("admin_edit_vehicle"):
                    st.info(f"Modification de : {v_info.get('marque')} {v_info.get('modele')} - {v_info.get('immatriculation')}")
                    
                    with st.expander("📝 Données Carte Grise", expanded=True):
                        c1, c2, c3 = st.columns(3)
                        vin = c1.text_input("VIN (Numéro Série)", value=v_info.get('vin') or "")
                        km = c2.number_input("Kilométrage", value=v_info.get('km_actuel', 0))
                        coul = c3.text_input("Couleur", value=v_info.get('couleur') or "")
                        carr = c1.text_input("Carrosserie", value=v_info.get('carrosserie') or "")
                        genr = c2.text_input("Genre (VP/CTTE)", value=v_info.get('genre_v') or "")
                    
                    with st.expander("⚙️ Données Moteur"):
                        c1, c2, c3 = st.columns(3)
                        p_ch = c1.number_input("Puissance DIN (ch)", value=v_info.get('puissance_ch', 0))
                        p_fi = c2.number_input("Puissance Fisc (CV)", value=v_info.get('puissance_fiscale', 0))
                        cyl = c3.number_input("Cylindrée (cc)", value=v_info.get('cylindree', 0))
                        mot_c = c1.text_input("Code Moteur", value=v_info.get('code_moteur') or "")
                        soup = c2.number_input("Soupapes", value=v_info.get('soupapes', 0))
                        co2 = c3.number_input("CO2 (g/km)", value=v_info.get('co2', 0))
                        carb = c1.text_input("Carburant", value=v_info.get('carburant') or "")
                        turbo = c2.checkbox("Turbo", value=v_info.get('turbo', False))

                    if st.form_submit_button("Sauvegarder les modifications"):
                        updates = {
                            'vin': vin, 'km_actuel': km, 'couleur': coul, 'carrosserie': carr, 'genre_v': genr,
                            'puissance_ch': p_ch, 'puissance_fiscale': p_fi, 'cylindree': cyl, 'code_moteur': mot_c,
                            'soupapes': soup, 'co2': co2, 'carburant': carb, 'turbo': turbo
                        }
                        if dm.admin_update_vehicle(vid, updates):
                            st.success("Mise à jour enregistrée en base de données !"); st.rerun()

    with tab_stats: 
        st.subheader("Statistiques Globales")
        st.json(dm.get_app_stats())

# --- VUE UTILISATEUR (Client) ---
else:
    nav_user = st.radio("Menu", ["Mes Véhicules", "Ajouter un véhicule"], horizontal=True)

    if nav_user == "Ajouter un véhicule":
        st.subheader("Nouveau Véhicule")
        if st.session_state['success_add_vehicle']:
            st.success("✅ Véhicule ajouté avec succès !"); st.balloons()
            st.session_state['success_add_vehicle'] = False

        with st.form("user_add_vehicle"):
            v_nom = st.text_input("Petit nom (ex: La Clio)")
            c1, c2 = st.columns(2)
            v_marq = c1.text_input("Marque")
            v_mod = c2.text_input("Modèle")
            v_imm = st.text_input("Plaque Immatriculation")
            v_km = st.number_input("Kilométrage Actuel", 0)
            v_an = st.number_input("Année", 2000)
            
            if st.form_submit_button("Ajouter à mon garage", type="primary"):
                payload = {"Nom":v_nom,"Marque":v_marq,"Modele":v_mod,"Immatriculation":v_imm,"Annee":v_an,"KM_Actuel":v_km}
                if dm.add_vehicle(payload):
                    st.session_state['success_add_vehicle'] = True; st.rerun()
                else: st.error("Erreur lors de l'ajout.")
    else:
        # Liste
        v_list = dm.get_vehicle_list()
        if not v_list: st.info("Votre garage est vide.")
        else:
            sel_v = st.selectbox("Sélectionner un véhicule", v_list, format_func=lambda x: x[1])
            v_id = sel_v[0]
            v_data = dm.get_vehicle_info(v_id)
            
            if v_data:
                st.markdown(f"## 🚘 {v_data.get('marque')} {v_data.get('modele')}")
                t_diag, t_carnet, t_plan = st.tabs(["🩺 Diagnostic IA", "📒 Carnet & Notes", "📅 Plan Entretien"])
                
                with t_diag:
                    st.info("Décrivez les symptômes, l'IA analysera les causes probables.")
                    
                    if not ai: 
                        if not ai_allowed: st.error("🔒 Option IA non incluse dans votre offre.")
                        else: st.warning("⚠️ IA temporairement indisponible (Maintenance).")
                    
                    with st.form("user_diag_form"):
                        code_def = st.text_input("Code Défaut (OBD) - Optionnel")
                        symptomes = st.text_area("Description du problème (Bruit, fumée, voyant...)", height=120)
                        date_panne = st.date_input("Date apparition", date.today())
                        
                        btn_diag = st.form_submit_button("Lancer l'Analyse", disabled=(ai is None), type="primary")
                        
                        if btn_diag:
                            with st.spinner("Analyse mécanique en cours..."):
                                history_txt = dm.get_full_history_text(v_id)
                                result = ai.analyze_obd(v_data, history_txt, f"{code_def} {symptomes}", date_panne)
                                
                                if "error" in result: st.error(result['error'])
                                else:
                                    st.success("Diagnostic Terminé !")
                                    st.markdown(result['resume_court'])
                                    with st.expander("Voir le rapport technique complet"):
                                        st.json(result)
                                    # Save
                                    dm.save_diagnostic(v_id, code_def, str(result), result.get('estimation_cout_pieces_mo'), result.get('sante_vehicule'), date_panne, result.get('resume_court'))

                    st.write("#### Historique Diagnostics")
                    hist_diag = dm.get_diagnostic_history(v_id)
                    if hist_diag: st.dataframe(pd.DataFrame(hist_diag)[['Date_Detection','Code_Defaut','Resume_IA']], hide_index=True, use_container_width=True)

                with t_carnet:
                    hist_notes = dm.get_notes_list(v_id)
                    if hist_notes: 
                        st.dataframe(pd.DataFrame(hist_notes)[['Date_Intervention','Type','Notes']], hide_index=True, use_container_width=True)
                    
                    with st.expander("Ajouter une note manuelle"):
                        with st.form("add_note_form"):
                            n_date = st.date_input("Date")
                            n_type = st.selectbox("Type", ["Entretien Courant", "Réparation", "Contrôle Technique", "Autre"])
                            n_txt = st.text_area("Détails")
                            if st.form_submit_button("Enregistrer"): dm.add_note(v_id, n_type, n_txt, n_date); st.rerun()

                with t_plan:
                    st.write("Plan de maintenance généré par l'IA en fonction du kilométrage et de l'historique.")
                    if st.button("Calculer le plan d'entretien", disabled=(ai is None)):
                        with st.spinner("Consultation des préconisations constructeur..."):
                            plan_res = ai.check_maintenance_schedule(v_data, dm.get_full_history_text(v_id))
                            if "error" not in plan_res: 
                                st.markdown(plan_res['response'])
                                dm.save_echeance(v_id, plan_res['response'])
                            else: st.error(plan_res['error'])
