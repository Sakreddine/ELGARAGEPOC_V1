import pandas as pd
import streamlit as st
from supabase import create_client, Client
from datetime import datetime
import hashlib
# On importe Groq ici mais on gère l'erreur si la librairie manque
try:
    from groq import Groq
except ImportError:
    Groq = None

class DataManager:
    def __init__(self):
        self.supabase: Client = None
        self.db_ready = False
        self.current_user = None
        self._init_connection()

    def _init_connection(self):
        try:
            url = st.secrets["supabase"]["url"]
            key = st.secrets["supabase"]["key"]
            self.supabase = create_client(url, key)
            # Petit test rapide
            self.supabase.table('users').select("count", count='exact').execute()
            self.db_ready = True
        except Exception as e: 
            print(f"DB Error: {e}")
            self.db_ready = False

    def _hash_password(self, password):
        return hashlib.sha256(password.encode()).hexdigest()

    # --- CONFIG ---
    def get_app_settings(self):
        if not self.db_ready: return None
        try:
            res = self.supabase.table('app_settings').select("*").eq('id', 1).execute()
            return res.data[0] if res.data else None
        except: return None

    def update_ai_configuration(self, new_key):
        """Active l'IA et vérifie la clé. Retourne (Succès?, Message)"""
        if not self.db_ready: return False, "Erreur connexion DB"
        if Groq is None: return False, "Module 'groq' non installé (pip install groq)"
        
        try:
            # 1. Test de la clé avec un appel très léger
            client = Groq(api_key=new_key)
            client.chat.completions.create(
                messages=[{"role":"user","content":"Hi"}], 
                model="llama-3.3-70b-versatile", 
                max_tokens=1
            )
            
            # 2. Si ça marche, on sauvegarde en DB
            self.supabase.table('app_settings').update({
                'groq_api_key': new_key, 
                'maintenance_mode': False
            }).eq('id', 1).execute()
            
            return True, "Clé valide ! IA activée."
            
        except Exception as e:
            # C'est ici qu'on capture l'erreur qui bloquait avant
            return False, f"Clé invalide ou API inaccessible : {str(e)}"

    def toggle_maintenance(self, status):
        if self.db_ready: 
            self.supabase.table('app_settings').update({'maintenance_mode': status}).eq('id', 1).execute()

    # --- USERS ---
    def register_user(self, nom, email, password, adresse):
        if not self.db_ready: return False, "Erreur DB"
        try:
            # Vérif doublon
            if self.supabase.table('users').select("*").eq('email', email).execute().data: 
                return False, "Cet email existe déjà."
            
            new_user = {
                'nom': nom, 
                'email': email, 
                'password_hash': self._hash_password(password), 
                'adresse': adresse, 
                'role': 'user', 
                'ai_allowed': False
            }
            data = self.supabase.table('users').insert(new_user).execute()
            if data.data:
                self.current_user = data.data[0]
                self.log_action(self.current_user['id'], "REGISTER", "Inscription")
                return True, "Succès"
            return False, "Erreur Inscription"
        except Exception as e: return False, str(e)

    def login_user(self, email, password):
        if not self.db_ready: return False, "Erreur DB"
        try:
            pwd_hash = self._hash_password(password)
            res = self.supabase.table('users').select("*").eq('email', email).eq('password_hash', pwd_hash).execute()
            if res.data:
                self.current_user = res.data[0]
                self.log_action(self.current_user['id'], "LOGIN", "Connexion")
                return True, "Succès"
            return False, "Email ou mot de passe incorrect."
        except Exception as e: return False, str(e)

    def toggle_user_ai(self, uid, status):
        if self.db_ready: self.supabase.table('users').update({'ai_allowed': status}).eq('id', uid).execute()

    def get_all_users(self):
        if not self.db_ready: return pd.DataFrame()
        try:
            res = self.supabase.table('users').select("*").order('created_at', desc=True).execute()
            return pd.DataFrame(res.data)
        except: return pd.DataFrame()

    # --- VEHICULES ---
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

    def get_all_vehicles_admin(self):
        if not self.db_ready: return pd.DataFrame()
        try:
            res = self.supabase.table('vehicules').select("*").execute()
            return pd.DataFrame(res.data)
        except: return pd.DataFrame()

    def get_vehicle_info(self, v_id):
        if not self.db_ready: return None
        try:
            q = self.supabase.table('vehicules').select("*").eq('id', v_id)
            if self.current_user.get('role') != 'admin': 
                q = q.eq('user_id', self.current_user['id'])
            res = q.execute()
            return res.data[0] if res.data else None
        except: return None

    def add_vehicle(self, info):
        if not self.db_ready: return False
        try:
            row = {
                'user_id': self.current_user['id'], 
                'nom': info.get('Nom'), 'marque': info.get('Marque'), 'modele': info.get('Modele'), 
                'immatriculation': info.get('Immatriculation'), 'annee': info.get('Annee'), 'km_actuel': info.get('KM_Actuel')
            }
            self.supabase.table('vehicules').insert(row).execute()
            self.log_action(self.current_user['id'], "ADD_VEHICLE", f"Ajout {info.get('Marque')}")
            return True
        except Exception as e: 
            st.error(str(e))
            return False

    def admin_update_vehicle(self, v_id, updates):
        if not self.db_ready: return
        try:
            # Protection : on ne touche pas à l'ID ou user_id
            forbidden = ['id', 'user_id', 'created_at']
            safe_updates = {k: v for k, v in updates.items() if k not in forbidden}
            self.supabase.table('vehicules').update(safe_updates).eq('id', v_id).execute()
            return True
        except Exception as e: 
            st.error(str(e))
            return False

    # --- LOGS & STATS ---
    def get_app_stats(self):
        if not self.db_ready: return {}
        try:
            # Astuce pour compter sans charger toutes les lignes (plus rapide)
            u = self.supabase.table('users').select("count", count='exact').execute().count
            v = self.supabase.table('vehicules').select("count", count='exact').execute().count
            l = self.supabase.table('system_logs').select("count", count='exact').execute().count
            
            stt = self.get_app_settings()
            status = "🔴 Maintenance" if stt and stt['maintenance_mode'] else "🟢 Actif"
            
            return {"Utilisateurs": u, "Véhicules": v, "Logs Système": l, "Statut Global": status}
        except: return {}

    def log_action(self, uid, action, details):
        if self.db_ready:
            try: self.supabase.table('system_logs').insert({'user_id': uid, 'action_type': action, 'details': details}).execute()
            except: pass

    # --- HISTORIQUE & DIAGS ---
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
        except: pass

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
        except: pass

    def save_echeance(self, v_id, analyse):
        if not self.get_vehicle_info(v_id): return
        try:
            # On remplace l'ancien rapport pour ce véhicule
            self.supabase.table('rapports_ia').delete().eq('vehicule_id', v_id).execute()
            self.supabase.table('rapports_ia').insert({'vehicule_id': v_id, 'date_calcul': datetime.now().strftime("%Y-%m-%d"), 'analyse_ia_echo': analyse}).execute()
        except: pass

    def get_full_history_text(self, v_id):
        """Récupère tout l'historique (Notes + Diags passés) pour donner du contexte à l'IA"""
        txt = "--- HISTORIQUE DES INTERVENTIONS ---\n"
        notes = self.get_notes_list(v_id)
        if not notes: txt += "Aucune intervention notée.\n"
        for n in notes: txt += f"- {n['Date_Intervention']} : [{n['Type']}] {n['Notes']}\n"
        
        txt += "\n--- HISTORIQUE DES DIAGNOSTICS IA ---\n"
        diags = self.get_diagnostic_history(v_id)
        if not diags: txt += "Aucun diagnostic précédent.\n"
        for d in diags: txt += f"- {d['Date_Detection']} : Code {d['Code_Defaut']} -> {d['Resume_IA']}\n"
        
        return txt



