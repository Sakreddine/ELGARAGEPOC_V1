import pandas as pd
import streamlit as st
from supabase import create_client, Client
from datetime import datetime

class DataManager:
    def __init__(self):
        self.load_status = "En attente de connexion..."
        self.supabase: Client = None
        self.db_ready = False

    def connect_db(self, url, key):
        """Connexion à la base Supabase"""
        try:
            self.supabase = create_client(url, key)
            # Test simple : on vérifie si la table 'users' répond
            self.supabase.table('users').select("count", count='exact').execute()
            
            self.db_ready = True
            self.load_status = "✅ Connecté à Supabase"
            return True
        except Exception as e:
            self.load_status = f"❌ Erreur Connexion : {str(e)}"
            self.db_ready = False
            return False

    # --- USERS ---
    def get_current_user_id(self):
        # Pour cette version, on force l'utilisateur ID 1 (Super Client)
        # C'est lui qui possède les 3 véhicules dans le SQL.
        return 1

    # --- VEHICULES ---
    def get_vehicle_list(self):
        if not self.db_ready: return []
        try:
            # On ne récupère que les véhicules de l'utilisateur 1
            user_id = self.get_current_user_id()
            response = self.supabase.table('vehicules').select("*").eq('user_id', user_id).execute()
            
            df = pd.DataFrame(response.data)
            if df.empty: return []
            return [(r['id'], f"{r.get('marque')} {r.get('modele')} - {r.get('immatriculation')}") for _, r in df.iterrows()]
        except: return []

    def get_vehicle_info(self, v_id):
        if not self.db_ready: return None
        try:
            response = self.supabase.table('vehicules').select("*").eq('id', v_id).execute()
            if response.data:
                r = response.data[0]
                # Mapping : SQL (minuscule) -> App (Majuscule pour affichage)
                return {
                    'ID': r.get('id'),
                    'Nom': r.get('nom'),
                    'Marque': r.get('marque'),
                    'Modele': r.get('modele'),
                    'Immatriculation': r.get('immatriculation'),
                    'Annee': r.get('annee'),
                    'KM_Actuel': r.get('km_actuel')
                }
            return None
        except: return None

    def add_vehicle(self, info):
        if not self.db_ready: return
        try:
            # On insère avec user_id = 1
            db_row = {
                'user_id': self.get_current_user_id(),
                'nom': info.get('Nom'),
                'marque': info.get('Marque'),
                'modele': info.get('Modele'),
                'immatriculation': info.get('Immatriculation'),
                'annee': info.get('Annee'),
                'km_actuel': info.get('KM_Actuel')
            }
            self.supabase.table('vehicules').insert(db_row).execute()
        except Exception as e: st.error(f"Erreur Ajout Véhicule: {e}")

    # --- HISTORIQUE (Table: historique_vehicules) ---
    def get_notes_list(self, v_id):
        if not self.db_ready: return []
        try:
            response = self.supabase.table('historique_vehicules')\
                .select("*")\
                .eq('vehicule_id', v_id)\
                .order('date', desc=True)\
                .execute()
            
            mapped_data = []
            for r in response.data:
                mapped_data.append({
                    'ID': r.get('id'),
                    'Date_Intervention': r.get('date'),       # SQL: date
                    'Type': r.get('type_evenement'),          # SQL: type_evenement
                    'Notes': r.get('notes'),
                    'Kilometrage': r.get('kilometrage')
                })
            return mapped_data
        except: return []

    def add_note(self, v_id, type_n, text_n, date_interv):
        if not self.db_ready: return
        try:
            v_info = self.get_vehicle_info(v_id)
            km = v_info.get('KM_Actuel', 0) if v_info else 0
            
            new_row = {
                'vehicule_id': v_id, 
                'date': date_interv.strftime("%Y-%m-%d"), 
                'type_evenement': type_n, 
                'notes': text_n, 
                'kilometrage': km
            }
            self.supabase.table('historique_vehicules').insert(new_row).execute()
        except Exception as e: st.error(f"Erreur Ajout Note: {e}")

    # --- DIAGNOSTICS (Table: diagnostics_vehicules) ---
    def get_diagnostic_history(self, v_id):
        if not self.db_ready: return []
        try:
            response = self.supabase.table('diagnostics_vehicules')\
                .select("*")\
                .eq('vehicule_id', v_id)\
                .order('date', desc=True)\
                .execute()
            
            mapped = []
            for r in response.data:
                mapped.append({
                    'Date_Detection': r.get('date'),      # SQL: date
                    'Code_Defaut': r.get('code_defaut'),
                    'Resume_IA': r.get('resume_ia'),
                    'Sante_Vehicule': r.get('sante_vehicule'),
                    'Analyse_IA_Diag': r.get('analyse_ia'), # SQL: analyse_ia
                    'Cout_Estime': r.get('cout_estime')
                })
            return mapped
        except: return []

    def save_diagnostic(self, v_id, codes, analyse, cout, sante, date_detect, resume=""):
        if not self.db_ready: return
        try:
            new_row = {
                'vehicule_id': v_id, 
                'date': date_detect.strftime("%Y-%m-%d"), 
                'code_defaut': codes, 
                'resume_ia': resume, 
                'analyse_ia': analyse, 
                'cout_estime': cout, 
                'sante_vehicule': sante
            }
            self.supabase.table('diagnostics_vehicules').insert(new_row).execute()
        except Exception as e: st.error(f"Erreur Save Diag: {e}")

    # --- MAINTENANCE (Table: rapports_ia) ---
    def save_echeance(self, v_id, analyse):
        if not self.db_ready: return
        try:
            # On nettoie l'ancien rapport pour ce véhicule
            self.supabase.table('rapports_ia').delete().eq('vehicule_id', v_id).execute()
            
            new_row = {
                'vehicule_id': v_id, 
                'date_calcul': datetime.now().strftime("%Y-%m-%d"), 
                'analyse_ia_echo': analyse # SQL: analyse_ia_echo
            }
            self.supabase.table('rapports_ia').insert(new_row).execute()
        except Exception as e: st.error(f"Erreur Rapport IA: {e}")

    # --- HELPERS POUR L'IA ---
    def get_full_history_text(self, v_id):
        if not self.db_ready: return ""
        txt = "--- HISTORIQUE ENTRETIENS ---\n"
        for n in self.get_notes_list(v_id):
            txt += f"- {n.get('Date_Intervention')} : [{n.get('Type')}] {n.get('Notes')}\n"
        
        txt += "\n--- DIAGNOSTICS PRÉCÉDENTS ---\n"
        for d in self.get_diagnostic_history(v_id):
            txt += f"- {d.get('Date_Detection')} : {d.get('Code_Defaut')} - {d.get('Resume_IA')}\n"
        return txt
