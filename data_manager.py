import pandas as pd
import streamlit as st
from supabase import create_client, Client
from datetime import datetime
import hashlib

class DataManager:
    def __init__(self):
        self.load_status = "En attente..."
        self.supabase: Client = None
        self.db_ready = False
        self.current_user = None # Stocke les infos de l'utilisateur connecté

    # --- CONNEXION SYSTÈME (Pour vérifier le login) ---
    def connect_system_db(self, url, key):
        try:
            self.supabase = create_client(url, key)
            # Petit test ping
            self.supabase.table('users').select("count", count='exact').execute()
            self.db_ready = True
            return True
        except Exception as e:
            self.load_status = f"Erreur Système: {e}"
            return False

    def _hash_password(self, password):
        """Hachage simple pour ne pas stocker le mot de passe en clair"""
        return hashlib.sha256(password.encode()).hexdigest()

    # --- GESTION UTILISATEURS ---

    def register_user(self, nom, email, password, groq_key, sb_url=None, sb_key=None):
        if not self.db_ready: return False, "Pas de connexion DB Système"
        try:
            # Vérif doublon email
            res = self.supabase.table('users').select("*").eq('email', email).execute()
            if res.data: return False, "Cet email existe déjà."

            new_user = {
                'nom': nom,
                'email': email,
                'password_hash': self._hash_password(password),
                'groq_key': groq_key,
                'user_supabase_url': sb_url if sb_url else None,
                'user_supabase_key': sb_key if sb_key else None
            }
            # Insertion
            data = self.supabase.table('users').insert(new_user).execute()
            if data.data:
                self.current_user = data.data[0]
                return True, f"Bienvenue {self.current_user['nom']} (ID: {self.current_user['id']})"
            return False, "Erreur inconnue lors de la création."
        except Exception as e: return False, str(e)

    def login_user(self, email, password):
        if not self.db_ready: return False, "Système non connecté"
        try:
            pwd_hash = self._hash_password(password)
            # On cherche l'user qui correspond au mail ET au hash du mot de passe
            response = self.supabase.table('users').select("*").eq('email', email).eq('password_hash', pwd_hash).execute()
            
            if response.data:
                self.current_user = response.data[0]
                return True, f"Ravi de vous revoir, {self.current_user.get('nom')}."
            else:
                return False, "Email ou mot de passe incorrect."
        except Exception as e: return False, str(e)

    def get_user_api_keys(self):
        """Renvoie les clés stockées pour configurer l'IA sans les redemander"""
        if self.current_user:
            return {
                'groq': self.current_user.get('groq_key'),
                'sb_url': self.current_user.get('user_supabase_url'),
                'sb_key': self.current_user.get('user_supabase_key')
            }
        return None

    # --- VEHICULES (LOGIQUE ADMIN ICI) ---
    
    def get_vehicle_list(self):
        if not self.db_ready or not self.current_user: return []
        try:
            # >>> MODE DÉVELOPPEUR <<<
            # Si l'utilisateur est le n°1, il voit TOUT. Sinon, filtre par user_id.
            if self.current_user['id'] == 1:
                response = self.supabase.table('vehicules').select("*").execute()
            else:
                uid = self.current_user['id']
                response = self.supabase.table('vehicules').select("*").eq('user_id', uid).execute()
            
            df = pd.DataFrame(response.data)
            if df.empty: return []
            
            # Affichage légèrement différent pour l'admin (on affiche le nom du proprio si dispo, sinon juste marque/modèle)
            return [(r['id'], f"{r.get('marque')} {r.get('modele')} - {r.get('immatriculation')}") for _, r in df.iterrows()]
        except: return []

    def get_vehicle_info(self, v_id):
        if not self.db_ready: return None
        try:
            query = self.supabase.table('vehicules').select("*").eq('id', v_id)
            
            # Si PAS Admin (ID != 1), on vérifie que le véhicule lui appartient
            if self.current_user['id'] != 1:
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
            # L'Admin ou le User ajoute un véhicule à SON nom
            db_row = {
                'user_id': self.current_user['id'], 
                'nom': info.get('Nom'), 'marque': info.get('Marque'), 'modele': info.get('Modele'), 
                'immatriculation': info.get('Immatriculation'), 'annee': info.get('Annee'), 'km_actuel': info.get('KM_Actuel')
            }
            self.supabase.table('vehicules').insert(db_row).execute()
        except Exception as e: st.error(f"Erreur Ajout: {e}")

    # --- LE RESTE EST STANDARD (Accès par vehicule_id, donc sécurisé de fait) ---

    def get_notes_list(self, v_id):
        if not self.db_ready: return []
        try:
            # On vérifie l'accès au véhicule avant de charger les notes (via get_vehicle_info)
            if not self.get_vehicle_info(v_id): return []
            
            response = self.supabase.table('historique_vehicules').select("*").eq('vehicule_id', v_id).order('date', desc=True).execute()
            mapped = []
            for r in response.data:
                mapped.append({'ID': r['id'], 'Date_Intervention': r['date'], 'Type': r['type_evenement'], 'Notes': r['notes'], 'Kilometrage': r['kilometrage']})
            return mapped
        except: return []

    def add_note(self, v_id, type_n, text_n, date_interv):
        if not self.db_ready: return
        try:
            v_info = self.get_vehicle_info(v_id) # Vérif droits
            if not v_info: return 
            km = v_info.get('KM_Actuel', 0)
            self.supabase.table('historique_vehicules').insert({'vehicule_id': v_id, 'date': date_interv.strftime("%Y-%m-%d"), 'type_evenement': type_n, 'notes': text_n, 'kilometrage': km}).execute()
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
