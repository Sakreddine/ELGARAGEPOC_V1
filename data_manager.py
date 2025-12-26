import pandas as pd
import streamlit as st
from supabase import create_client, Client
from datetime import datetime

class DataManager:
    def __init__(self):
        self.load_status = "Connexion Cloud..."
        self.supabase: Client = None
        self.db_ready = False
        
        # Tentative de connexion via les Secrets Streamlit
        try:
            url = st.secrets["supabase"]["url"]
            key = st.secrets["supabase"]["key"]
            self.supabase = create_client(url, key)
            self.db_ready = True
            self.load_status = "✅ Connecté au Cloud (Supabase)"
        except Exception as e:
            self.load_status = f"❌ Erreur Config Secrets: {str(e)}"

    # Cette fonction ne sert plus à charger un Excel, mais vérifie la connexion
    def load_db(self, path=None):
        return self.db_ready

    # --- VEHICULES ---
    def get_vehicle_list(self):
        if not self.db_ready: return []
        try:
            # Récupération SQL : SELECT * FROM VEHICULES
            response = self.supabase.table('VEHICULES').select("*").execute()
            df = pd.DataFrame(response.data)
            if df.empty: return []
            return [(r['id'], f"{r.get('Nom')} - {r.get('Immatriculation')}") for _, r in df.iterrows()]
        except Exception as e:
            print(f"Erreur Get Vehicules: {e}")
            return []

    def get_vehicle_info(self, v_id):
        if not self.db_ready: return None
        try:
            response = self.supabase.table('VEHICULES').select("*").eq('id', v_id).execute()
            if response.data:
                return response.data[0] # Renvoie le dictionnaire directement
            return None
        except: return None

    def add_vehicle(self, info):
        if not self.db_ready: return
        try:
            # On retire l'ID s'il est présent pour laisser Supabase le gérer
            if 'ID' in info: del info['ID']
            # INSERT INTO VEHICULES ...
            self.supabase.table('VEHICULES').insert(info).execute()
        except Exception as e:
            st.error(f"Erreur Ajout: {e}")

    # --- NOTES CRUD ---
    def get_notes_list(self, v_id):
        if not self.db_ready: return []
        try:
            # SELECT * FROM ENTRETIENS WHERE Vehicule_ID = v_id ORDER BY Date_Intervention DESC
            response = self.supabase.table('ENTRETIENS')\
                .select("*")\
                .eq('Vehicule_ID', v_id)\
                .order('Date_Intervention', desc=True)\
                .execute()
            return response.data
        except Exception as e:
            st.error(f"Erreur Lecture Notes: {e}")
            return []

    def add_note(self, v_id, type_n, text_n, date_interv):
        if not self.db_ready: return
        try:
            v_info = self.get_vehicle_info(v_id)
            km = v_info.get('KM_Actuel', 0) if v_info else 0
            
            new_row = {
                'Vehicule_ID': v_id,
                'Date_Intervention': date_interv.strftime("%Y-%m-%d"),
                'Type': type_n,
                'Notes': text_n,
                'Kilometrage': km
            }
            self.supabase.table('ENTRETIENS').insert(new_row).execute()
        except Exception as e: st.error(f"Erreur Ajout Note: {e}")

    def update_note(self, note_id, type_n, text_n, date_interv):
        # Cette fonction n'est pas utilisée dans la version mobile simplifiée, 
        # mais on la garde pour compatibilité future
        pass 

    def delete_note(self, note_id):
        pass

    # --- DIAGNOSTICS ---
    def get_diagnostic_history(self, v_id):
        if not self.db_ready: return []
        try:
            response = self.supabase.table('DIAGNOSTICS')\
                .select("*")\
                .eq('Vehicule_ID', v_id)\
                .order('Date_Detection', desc=True)\
                .execute()
            return response.data
        except: return []

    def save_diagnostic(self, v_id, codes, analyse, cout, sante, date_detect, resume=""):
        if not self.db_ready: return
        try:
            new_row = {
                'Vehicule_ID': v_id,
                'Date_Detection': date_detect.strftime("%Y-%m-%d"),
                'Code_Defaut': codes,
                'Resume_IA': resume,
                'Analyse_IA_Diag': analyse,
                'Cout_Estime': cout,
                'Sante_Vehicule': sante
            }
            self.supabase.table('DIAGNOSTICS').insert(new_row).execute()
        except Exception as e: st.error(f"Erreur Save Diag: {e}")

    # --- MAINTENANCE / ECHEANCE ---
    def save_echeance(self, v_id, analyse):
        if not self.db_ready: return
        try:
            # On supprime l'ancien plan pour ce véhicule pour ne garder que le dernier
            self.supabase.table('ECHEANCE').delete().eq('Vehicule_ID', v_id).execute()
            
            new_row = {
                'Vehicule_ID': v_id,
                'Date_Calcul': datetime.now().strftime("%Y-%m-%d"),
                'Analyse_IA_Echeance': analyse
            }
            self.supabase.table('ECHEANCE').insert(new_row).execute()
        except Exception as e: st.error(f"Erreur Save Echeance: {e}")

    # --- HELPERS IA (Formatage Texte pour le Prompt) ---
    def get_full_history_text(self, v_id):
        if not self.db_ready: return "Pas de connexion base de données."
        
        txt = "--- HISTORIQUE ENTRETIENS ---\n"
        notes = self.get_notes_list(v_id)
        if notes:
            for n in notes:
                d = n.get('Date_Intervention', '?')
                t = n.get('Type', '?')
                c = n.get('Notes', '')
                txt += f"- Le {d} : [{t}] {c}\n"
        else: txt += "Aucun entretien.\n"

        txt += "\n--- HISTORIQUE DÉFAUTS ---\n"
        diags = self.get_diagnostic_history(v_id)
        if diags:
            for d in diags:
                date_d = d.get('Date_Detection', '?')
                code = d.get('Code_Defaut', '?')
                res = d.get('Resume_IA', '')
                txt += f"- Le {date_d} : Codes [{code}] - {res}\n"
        else: txt += "Aucun défaut précédent.\n"
        
        return txt
