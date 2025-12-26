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
        """Tente de se connecter à Supabase avec les identifiants fournis."""
        try:
            self.supabase = create_client(url, key)
            # Test sur la table 'vehicules' (en minuscules)
            self.supabase.table('vehicules').select("count", count='exact').execute()
            
            self.db_ready = True
            self.load_status = "✅ Connecté à Supabase"
            return True
        except Exception as e:
            self.load_status = f"❌ Erreur Connexion : {str(e)}"
            self.db_ready = False
            return False

    # --- VEHICULES ---
    def get_vehicle_list(self):
        if not self.db_ready: return []
        try:
            # Table 'vehicules' en minuscules
            response = self.supabase.table('vehicules').select("*").execute()
            df = pd.DataFrame(response.data)
            if df.empty: return []
            # Les colonnes sont aussi en minuscules (nom, immatriculation)
            return [(r['id'], f"{r.get('nom')} - {r.get('immatriculation')}") for _, r in df.iterrows()]
        except: return []

    def get_vehicle_info(self, v_id):
        if not self.db_ready: return None
        try:
            response = self.supabase.table('vehicules').select("*").eq('id', v_id).execute()
            if response.data:
                # On convertit les clés minuscules de la DB en Majuscules pour l'App
                # Cela évite de devoir modifier tout app.py
                r = response.data[0]
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
            # Conversion des clés Python (Maj) vers DB (Min)
            db_row = {
                'nom': info.get('Nom'),
                'marque': info.get('Marque'),
                'modele': info.get('Modele'),
                'immatriculation': info.get('Immatriculation'),
                'annee': info.get('Annee'),
                'km_actuel': info.get('KM_Actuel')
            }
            self.supabase.table('vehicules').insert(db_row).execute()
        except Exception as e: st.error(f"Erreur Ajout: {e}")

    # --- NOTES ---
    def get_notes_list(self, v_id):
        if not self.db_ready: return []
        try:
            # Table 'entretiens', colonne 'vehicule_id' (minuscules)
            response = self.supabase.table('entretiens')\
                .select("*")\
                .eq('vehicule_id', v_id)\
                .order('date_intervention', desc=True)\
                .execute()
            
            # Mapping pour l'affichage dans app.py
            mapped_data = []
            for r in response.data:
                mapped_data.append({
                    'ID': r.get('id'),
                    'Vehicule_ID': r.get('vehicule_id'),
                    'Date_Intervention': r.get('date_intervention'),
                    'Type': r.get('type'),
                    'Notes': r.get('notes'),
                    'Kilometrage': r.get('kilometrage')
                })
            return mapped_data
        except: return []

    def add_note(self, v_id, type_n, text_n, date_interv):
        if not self.db_ready: return
        try:
            # Récup KM actuel via notre fonction interne qui gère déjà la casse
            v_info = self.get_vehicle_info(v_id)
            km = v_info.get('KM_Actuel', 0) if v_info else 0
            
            new_row = {
                'vehicule_id': v_id, 
                'date_intervention': date_interv.strftime("%Y-%m-%d"), 
                'type': type_n, 
                'notes': text_n, 
                'kilometrage': km
            }
            self.supabase.table('entretiens').insert(new_row).execute()
        except Exception as e: st.error(f"Erreur Note: {e}")

    # --- DIAGNOSTICS ---
    def get_diagnostic_history(self, v_id):
        if not self.db_ready: return []
        try:
            response = self.supabase.table('diagnostics')\
                .select("*")\
                .eq('vehicule_id', v_id)\
                .order('date_detection', desc=True)\
                .execute()
            
            # Mapping
            mapped = []
            for r in response.data:
                mapped.append({
                    'Date_Detection': r.get('date_detection'),
                    'Code_Defaut': r.get('code_defaut'),
                    'Resume_IA': r.get('resume_ia'),
                    'Sante_Vehicule': r.get('sante_vehicule'),
                    'Analyse_IA_Diag': r.get('analyse_ia_diag'),
                    'Cout_Estime': r.get('cout_estime')
                })
            return mapped
        except: return []

    def save_diagnostic(self, v_id, codes, analyse, cout, sante, date_detect, resume=""):
        if not self.db_ready: return
        try:
            new_row = {
                'vehicule_id': v_id, 
                'date_detection': date_detect.strftime("%Y-%m-%d"), 
                'code_defaut': codes, 
                'resume_ia': resume, 
                'analyse_ia_diag': analyse, 
                'cout_estime': cout, 
                'sante_vehicule': sante
            }
            self.supabase.table('diagnostics').insert(new_row).execute()
        except Exception as e: st.error(f"Erreur Save Diag: {e}")

    # --- MAINTENANCE ---
    def save_echeance(self, v_id, analyse):
        if not self.db_ready: return
        try:
            self.supabase.table('echeance').delete().eq('vehicule_id', v_id).execute()
            new_row = {
                'vehicule_id': v_id, 
                'date_calcul': datetime.now().strftime("%Y-%m-%d"), 
                'analyse_ia_echeance': analyse
            }
            self.supabase.table('echeance').insert(new_row).execute()
        except Exception as e: st.error(f"Erreur Echeance: {e}")

    # --- HELPERS ---
    def get_full_history_text(self, v_id):
        if not self.db_ready: return ""
        txt = "--- ENTRETIENS ---\n"
        # On utilise nos fonctions get_ qui font déjà le mapping majuscules
        for n in self.get_notes_list(v_id):
            txt += f"- {n.get('Date_Intervention')} : [{n.get('Type')}] {n.get('Notes')}\n"
        
        txt += "\n--- DIAGNOSTICS ---\n"
        for d in self.get_diagnostic_history(v_id):
            txt += f"- {d.get('Date_Detection')} : {d.get('Code_Defaut')} - {d.get('Resume_IA')}\n"
        return txt
