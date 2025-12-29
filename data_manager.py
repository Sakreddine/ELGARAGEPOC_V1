import pandas as pd
import streamlit as st
from supabase import create_client, Client
from datetime import datetime
import hashlib

class DataManager:
    def __init__(self):
        self.load_status = "Non connecté"
        self.supabase: Client = None
        self.db_ready = False
        self.current_user = None

    def connect_system_db(self, url, key):
        try:
            if not url or not key: return False
            self.supabase = create_client(url, key)
            self.supabase.table('users').select("count", count='exact').execute()
            self.db_ready = True
            return True
        except Exception as e:
            self.load_status = f"Erreur: {str(e)}"
            self.db_ready = False
            return False

    def _hash_password(self, password):
        return hashlib.sha256(password.encode()).hexdigest()

    # --- AUTHENTIFICATION ---

    def register_user(self, nom, email, password, adresse):
        # Inscription réservée aux UTILISATEURS (Role = user)
        if not self.db_ready: return False, "Erreur DB"
        try:
            # Vérif doublon
            res = self.supabase.table('users').select("*").eq('email', email).execute()
            if res.data: return False, "Cet email existe déjà."

            new_user = {
                'nom': nom,
                'email': email,
                'password_hash': self._hash_password(password),
                'adresse': adresse, # Nouvelle colonne
                'role': 'user'      # Toujours user via le formulaire
            }
            data = self.supabase.table('users').insert(new_user).execute()
            if data.data:
                self.current_user = data.data[0]
                self.log_action(self.current_user['id'], "REGISTER", "Nouvelle inscription")
                return True, "Compte créé avec succès."
            return False, "Erreur création."
        except Exception as e: return False, str(e)

    def login_user(self, email, password):
        if not self.db_ready: return False, "Serveur non connecté"
        try:
            pwd_hash = self._hash_password(password)
            # On récupère l'user
            response = self.supabase.table('users').select("*").eq('email', email).eq('password_hash', pwd_hash).execute()
            
            if response.data:
                self.current_user = response.data[0]
                self.log_action(self.current_user['id'], "LOGIN", "Connexion réussie")
                return True, "Connexion réussie."
            else:
                return False, "Email ou mot de passe incorrect."
        except Exception as e: return False, str(e)

    # --- ADMIN FUNCTIONS ---

    def get_all_users(self):
        if not self.db_ready: return pd.DataFrame()
        try:
            response = self.supabase.table('users').select("id, nom, email, role, adresse, created_at").order('created_at', desc=True).execute()
            return pd.DataFrame(response.data)
        except: return pd.DataFrame()

    def get_app_stats(self):
        if not self.db_ready: return {}
        try:
            u_count = self.supabase.table('users').select("count", count='exact').execute().count
            v_count = self.supabase.table('vehicules').select("count", count='exact').execute().count
            l_count = self.supabase.table('system_logs').select("count", count='exact').execute().count
            return {"users": u_count, "vehicles": v_count, "logs": l_count}
        except: return {}
    
    def get_all_vehicles_admin(self):
        if not self.db_ready: return pd.DataFrame()
        try:
            response = self.supabase.table('vehicules').select("*").execute()
            return pd.DataFrame(response.data)
        except: return pd.DataFrame()

    def log_action(self, user_id, action, details):
        if not self.db_ready: return
        try:
            self.supabase.table('system_logs').insert({
                "user_id": user_id,
                "action_type": action,
                "details": details
            }).execute()
        except: pass

    # --- VEHICULES (User vs Admin) ---

    def get_vehicle_list(self):
        if not self.db_ready or not self.current_user: return []
        try:
            # Si Admin -> Voit tout. Si User -> Voit SES véhicules.
            if self.current_user.get('role') == 'admin':
                response = self.supabase.table('vehicules').select("*").execute()
            else:
                uid = self.current_user['id']
                response = self.supabase.table('vehicules').select("*").eq('user_id', uid).execute()
            
            df = pd.DataFrame(response.data)
            if df.empty: return []
            return [(r['id'], f"{r.get('marque')} {r.get('modele')} - {r.get('immatriculation')}") for _, r in df.iterrows()]
        except: return []

    def get_vehicle_info(self, v_id):
        if not self.db_ready: return None
        try:
            query = self.supabase.table('vehicules').select("*").eq('id', v_id)
            if self.current_user.get('role') != 'admin':
                query = query.eq('user_id', self.current_user['id'])
            
            response = query.execute()
            if response.data:
                r = response.data[0]
                return {'ID': r.get('id'), 'Nom': r.get('nom'), 'Marque': r.get('marque'), 'Modele': r.get('modele'), 'Immatriculation': r.get('immatriculation'), 'Annee': r.get('annee'), 'KM_Actuel': r.get('km_actuel')}
            return None
        except: return None

    def add_vehicle(self, info):
        if not self.db_ready or not self.current_user: return
        try:
            db_row = {
                'user_id': self.current_user['id'], 
                'nom': info.get('Nom'), 'marque': info.get('Marque'), 'modele': info.get('Modele'), 
                'immatriculation': info.get('Immatriculation'), 'annee': info.get('Annee'), 'km_actuel': info.get('KM_Actuel')
            }
            self.supabase.table('vehicules').insert(db_row).execute()
            self.log_action(self.current_user['id'], "ADD_VEHICLE", f"Ajout {info.get('Marque')}")
        except Exception as e: st.error(f"Erreur Ajout: {e}")

    # --- HISTORIQUE & DIAGS ---
    def get_notes_list(self, v_id):
        if not self.get_vehicle_info(v_id): return []
        try:
            response = self.supabase.table('historique_vehicules').select("*").eq('vehicule_id', v_id).order('date', desc=True).execute()
            mapped = []
            for r in response.data:
                mapped.append({'ID': r['id'], 'Date_Intervention': r['date'], 'Type': r['type_evenement'], 'Notes': r['notes'], 'Kilometrage': r['kilometrage']})
            return mapped
        except: return []

    def add_note(self, v_id, type_n, text_n, date_interv):
        if not self.get_vehicle_info(v_id): return
        try:
            v_info = self.get_vehicle_info(v_id)
            km = v_info.get('KM_Actuel', 0)
            self.supabase.table('historique_vehicules').insert({'vehicule_id': v_id, 'date': date_interv.strftime("%Y-%m-%d"), 'type_evenement': type_n, 'notes': text_n, 'kilometrage': km}).execute()
            self.log_action(self.current_user['id'], "ADD_NOTE", f"Note sur vehicule {v_id}")
        except Exception as e: st.error(f"Erreur: {e}")

    def get_diagnostic_history(self, v_id):
        if not self.get_vehicle_info(v_id): return []
        try:
            response = self.supabase.table('diagnostics_vehicules').select("*").eq('vehicule_id', v_id).order('date', desc=True).execute()
            mapped = []
            for r in response.data:
                mapped.append({'Date_Detection': r['date'], 'Code_Defaut': r['code_defaut'], 'Resume_IA': r['resume_ia'], 'Sante_Vehicule': r['sante_vehicule'], 'Analyse_IA_Diag': r['analyse_ia'], 'Cout_Estime': r['cout_estime']})
            return mapped
        except: return []

    def save_diagnostic(self, v_id, codes, analyse, cout, sante, date_detect, resume=""):
        if not self.get_vehicle_info(v_id): return
        try:
            self.supabase.table('diagnostics_vehicules').insert({'vehicule_id': v_id, 'date': date_detect.strftime("%Y-%m-%d"), 'code_defaut': codes, 'resume_ia': resume, 'analyse_ia': analyse, 'cout_estime': cout, 'sante_vehicule': sante}).execute()
            self.log_action(self.current_user['id'], "ADD_DIAG", f"Diag sur vehicule {v_id}")
        except Exception as e: st.error(f"Erreur: {e}")

    def save_echeance(self, v_id, analyse):
        if not self.get_vehicle_info(v_id): return
        try:
            self.supabase.table('rapports_ia').delete().eq('vehicule_id', v_id).execute()
            self.supabase.table('rapports_ia').insert({'vehicule_id': v_id, 'date_calcul': datetime.now().strftime("%Y-%m-%d"), 'analyse_ia_echo': analyse}).execute()
        except Exception as e: st.error(f"Erreur: {e}")

    def get_full_history_text(self, v_id):
        txt = "--- HISTORIQUE ---\n"
        for n in self.get_notes_list(v_id): txt += f"- {n['Date_Intervention']} : {n['Type']} - {n['Notes']}\n"
        txt += "\n--- DIAGNOSTICS ---\n"
        for d in self.get_diagnostic_history(v_id): txt += f"- {d['Date_Detection']} : {d['Code_Defaut']} ({d['Resume_IA']})\n"
        return txt
