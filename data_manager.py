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
            # Petit test de connexion pour vérifier si ça marche (compte les véhicules)
            self.supabase.table('VEHICULES').select("count", count='exact').execute()
            
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
            response = self.supabase.table('VEHICULES').select("*").execute()
            df = pd.DataFrame(response.data)
            if df.empty: return []
            return [(r['id'], f"{r.get('Nom')} - {r.get('Immatriculation')}") for _, r in df.iterrows()]
        except: return []

    def get_vehicle_info(self, v_id):
        if not self.db_ready: return None
        try:
            response = self.supabase.table('VEHICULES').select("*").eq('id', v_id).execute()
            return response.data[0] if response.data else None
        except: return None

    def add_vehicle(self, info):
        if not self.db_ready: return
        try:
            if 'ID' in info: del info['ID']
            self.supabase.table('VEHICULES').insert(info).execute()
        except Exception as e: st.error(f"Erreur Ajout: {e}")

    # --- NOTES ---
    def get_notes_list(self, v_id):
        if not self.db_ready: return []
        try:
            response = self.supabase.table('ENTRETIENS').select("*").eq('Vehicule_ID', v_id).order('Date_Intervention', desc=True).execute()
            return response.data
        except: return []

    def add_note(self, v_id, type_n, text_n, date_interv):
        if not self.db_ready: return
        try:
            v_info = self.get_vehicle_info(v_id)
            km = v_info.get('KM_Actuel', 0) if v_info else 0
            new_row = {'Vehicule_ID': v_id, 'Date_Intervention': date_interv.strftime("%Y-%m-%d"), 'Type': type_n, 'Notes': text_n, 'Kilometrage': km}
            self.supabase.table('ENTRETIENS').insert(new_row).execute()
        except Exception as e: st.error(f"Erreur Note: {e}")

    # --- DIAGNOSTICS ---
    def get_diagnostic_history(self, v_id):
        if not self.db_ready: return []
        try:
            response = self.supabase.table('DIAGNOSTICS').select("*").eq('Vehicule_ID', v_id).order('Date_Detection', desc=True).execute()
            return response.data
        except: return []

    def save_diagnostic(self, v_id, codes, analyse, cout, sante, date_detect, resume=""):
        if not self.db_ready: return
        try:
            new_row = {'Vehicule_ID': v_id, 'Date_Detection': date_detect.strftime("%Y-%m-%d"), 'Code_Defaut': codes, 'Resume_IA': resume, 'Analyse_IA_Diag': analyse, 'Cout_Estime': cout, 'Sante_Vehicule': sante}
            self.supabase.table('DIAGNOSTICS').insert(new_row).execute()
        except Exception as e: st.error(f"Erreur Save Diag: {e}")

    # --- MAINTENANCE ---
    def save_echeance(self, v_id, analyse):
        if not self.db_ready: return
        try:
            self.supabase.table('ECHEANCE').delete().eq('Vehicule_ID', v_id).execute()
            new_row = {'Vehicule_ID': v_id, 'Date_Calcul': datetime.now().strftime("%Y-%m-%d"), 'Analyse_IA_Echeance': analyse}
            self.supabase.table('ECHEANCE').insert(new_row).execute()
        except Exception as e: st.error(f"Erreur Echeance: {e}")

    # --- HELPERS ---
    def get_full_history_text(self, v_id):
        if not self.db_ready: return ""
        txt = "--- ENTRETIENS ---\n"
        for n in self.get_notes_list(v_id):
            txt += f"- {n.get('Date_Intervention')} : [{n.get('Type')}] {n.get('Notes')}\n"
        txt += "\n--- DIAGNOSTICS ---\n"
        for d in self.get_diagnostic_history(v_id):
            txt += f"- {d.get('Date_Detection')} : {d.get('Code_Defaut')} - {d.get('Resume_IA')}\n"
        return txt
