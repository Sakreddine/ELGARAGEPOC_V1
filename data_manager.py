import pandas as pd
import streamlit as st
from supabase import create_client, Client
from datetime import datetime
import hashlib
from groq import Groq

class DataManager:
    def __init__(self):
        self.supabase: Client = None
        self.db_ready = False
        self.current_user = None
        self._init_connection()

    def _init_connection(self):
        """Charge la connexion depuis les secrets Streamlit uniquement"""
        try:
            # Récupération sécurisée via .streamlit/secrets.toml
            url = st.secrets["supabase"]["url"]
            key = st.secrets["supabase"]["key"]
            self.supabase = create_client(url, key)
            # Test de connexion (Ping)
            self.supabase.table('users').select("count", count='exact').execute()
            self.db_ready = True
        except Exception as e:
            self.db_ready = False
            # On ne raise pas d'erreur ici pour gérer l'affichage UI proprement dans app.py

    def _hash_password(self, password):
        return hashlib.sha256(password.encode()).hexdigest()

    # --- CONFIGURATION & IA ---

    def get_app_settings(self):
        """Récupère la configuration globale (Mode Maintenance, Clé IA)"""
        if not self.db_ready: return None
        try:
            res = self.supabase.table('app_settings').select("*").eq('id', 1).execute()
            return res.data[0] if res.data else None
        except: return None

    def update_ai_configuration(self, new_key):
        """Admin : Teste la clé Groq et l'active si valide"""
        if not self.db_ready: return False, "DB Hors ligne"
        try:
            # 1. Test réel de la clé API
            client = Groq(api_key=new_key)
            client.chat.completions.create(messages=[{"role":"user","content":"ping"}], model="llama-3.3-70b-versatile", max_tokens=1)
            
            # 2. Sauvegarde si succès
            self.supabase.table('app_settings').update({'groq_api_key': new_key, 'maintenance_mode': False}).eq('id', 1).execute()
            self.log_action(self.current_user['id'], "CONFIG_UPDATE", "Activation IA avec nouvelle clé")
            return True, "Clé validée ! IA activée."
        except Exception as e:
            return False, f"Clé invalide ou erreur Groq : {str(e)}"

    def toggle_maintenance(self, status):
        """Admin : Force le mode maintenance"""
        if self.db_ready:
            self.supabase.table('app_settings').update({'maintenance_mode': status}).eq('id', 1).execute()

    # --- AUTHENTIFICATION ---

    def register_user(self, nom, email, password, adresse):
        if not self.db_ready: return False, "Erreur connexion DB"
        try:
            # Vérif email unique
            if self.supabase.table('users').select("*").eq('email', email).execute().data:
                return False, "Cet email est déjà utilisé."
            
            new_user = {
                'nom': nom, 'email': email, 'password_hash': self._hash_password(password),
                'adresse': adresse, 'role': 'user' # Toujours USER par défaut ici
            }
            data = self.supabase.table('users').insert(new_user).execute()
            if data.data:
                self.current_user = data.data[0]
                self.log_action(self.current_user['id'], "REGISTER", "Nouvelle inscription")
                return True, "Succès"
            return False, "Erreur inconnue"
        except Exception as e: return False, str(e)

    def login_user(self, email, password):
        if not self.db_ready: return False, "Erreur connexion DB"
        try:
            pwd_hash = self._hash_password(password)
            res = self.supabase.table('users').select("*").eq('email', email).eq('password_hash', pwd_hash).execute()
            if res.data:
                self.current_user = res.data[0]
                self.log_action(self.current_user['id'], "LOGIN", "Connexion")
                return True, "Succès"
            return False, "Identifiants incorrects"
        except Exception as e: return False, str(e)

    # --- ADMIN DASHBOARD ---

    def get_all_users(self):
        if not self.db_ready: return pd.DataFrame()
        try:
            res = self.supabase.table('users').select("id, nom, email, role, adresse, created_at").order('created_at', desc=True).execute()
            return pd.DataFrame(res.data)
        except: return pd.DataFrame()

    def get_app_stats(self):
        if not self.db_ready: return {}
        try:
            u = self.supabase.table('users').select("count", count='exact').execute().count
            v = self.supabase.table('vehicules').select("count", count='exact').execute().count
            l = self.supabase.table('system_logs').select("count", count='exact').execute().count
            stt = self.get_app_settings()
            status = "🔴 Maintenance" if stt and stt['maintenance_mode'] else "🟢 Actif"
            return {"users": u, "vehicles": v, "logs": l, "status": status}
        except: return {}

    def get_all_vehicles_admin(self):
        if not self.db_ready: return pd.DataFrame()
        try:
            res = self.supabase.table('vehicules').select("*").execute()
            return pd.DataFrame(res.data)
        except: return pd.DataFrame()

    def log_action(self, uid, action, details):
        if self.db_ready:
            try: self.supabase.table('system_logs').insert({'user_id': uid, 'action_type': action, 'details': details}).execute()
            except: pass

    # --- GESTION VEHICULES (User vs Admin) ---

    def get_vehicle_list(self):
        if not self.db_ready or not self.current_user: return []
        try:
            if self.current_user.get('role') == 'admin':
                res = self.supabase.table('vehicules').select("*").execute()
            else:
                res = self.supabase.table('vehicules').select("*").eq('user_id', self.current_user['id']).execute()
            
            df = pd.DataFrame(res.data)
            if df.empty: return []
            return [(r['id'], f"{r.get('marque')} {r.get('modele')} - {r.get('immatriculation')}") for _, r in df.iterrows()]
        except: return []

    def get_vehicle_info(self, v_id):
        if not self.db_ready: return None
        try:
            q = self.supabase.table('vehicules').select("*").eq('id', v_id)
            if self.current_user.get('role') != 'admin': q = q.eq('user_id', self.current_user['id'])
            res = q.execute()
            if res.data:
                r = res.data[0]
                return {'ID': r['id'], 'Nom': r.get('nom'), 'Marque': r.get('marque'), 'Modele': r.get('modele'), 'Immatriculation': r.get('immatriculation'), 'Annee': r.get('annee'), 'KM_Actuel': r.get('km_actuel')}
            return None
        except: return None

    def add_vehicle(self, info):
        if not self.db_ready: return
        try:
            row = {'user_id': self.current_user['id'], 'nom': info['Nom'], 'marque': info['Marque'], 'modele': info['Modele'], 'immatriculation': info['Immatriculation'], 'annee': info['Annee'], 'km_actuel': info['KM_Actuel']}
            self.supabase.table('vehicules').insert(row).execute()
            self.log_action(self.current_user['id'], "ADD_VEHICLE", f"Ajout {info['Marque']}")
        except Exception as e: st.error(str(e))

    # --- DIAGNOSTICS & NOTES ---

    def get_notes_list(self, v_id):
        if not self.get_vehicle_info(v_id): return []
        try:
            res = self.supabase.table('historique_vehicules').select("*").eq('vehicule_id', v_id).order('date', desc=True).execute()
            return [{'ID': r['id'], 'Date_Intervention': r['date'], 'Type': r['type_evenement'], 'Notes': r['notes']} for r in res.data]
        except: return []

    def add_note(self, v_id, t, n, d):
        if not self.get_vehicle_info(v_id): return
        try:
            self.supabase.table('historique_vehicules').insert({'vehicule_id': v_id, 'date': str(d), 'type_evenement': t, 'notes': n}).execute()
        except Exception as e: st.error(str(e))

    def get_diagnostic_history(self, v_id):
        if not self.get_vehicle_info(v_id): return []
        try:
            res = self.supabase.table('diagnostics_vehicules').select("*").eq('vehicule_id', v_id).order('date', desc=True).execute()
            return [{'Date_Detection': r['date'], 'Code_Defaut': r['code_defaut'], 'Resume_IA': r['resume_ia']} for r in res.data]
        except: return []

    def save_diagnostic(self, v_id, c, a, cost, sante, d, res):
        if not self.get_vehicle_info(v_id): return
        try:
            self.supabase.table('diagnostics_vehicules').insert({'vehicule_id': v_id, 'date': str(d), 'code_defaut': c, 'resume_ia': res, 'analyse_ia': a, 'cout_estime': cost, 'sante_vehicule': sante}).execute()
            self.log_action(self.current_user['id'], "ADD_DIAG", f"Diag {v_id}")
        except Exception as e: st.error(str(e))

    def save_echeance(self, v_id, analyse):
        if not self.get_vehicle_info(v_id): return
        try:
            self.supabase.table('rapports_ia').delete().eq('vehicule_id', v_id).execute()
            self.supabase.table('rapports_ia').insert({'vehicule_id': v_id, 'date_calcul': datetime.now().strftime("%Y-%m-%d"), 'analyse_ia_echo': analyse}).execute()
        except: pass

    def get_full_history_text(self, v_id):
        txt = "--- HISTORIQUE ---\n"
        for n in self.get_notes_list(v_id): txt += f"- {n['Date_Intervention']} : {n['Type']} - {n['Notes']}\n"
        return txt
