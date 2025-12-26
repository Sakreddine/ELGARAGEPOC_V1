import pandas as pd
import os
from datetime import datetime

class DataManager:
    def __init__(self):
        self.db_path = None
        self.data = {}
        self.load_status = "En attente de fichier..."

    def load_db(self, path):
        self.db_path = path
        if os.path.exists(self.db_path):
            try:
                self.data = pd.read_excel(self.db_path, sheet_name=None)
                
                # --- NETTOYAGE VEHICULES ---
                if 'VEHICULES' in self.data:
                    df_v = self.data['VEHICULES']
                    corrections = {'Immatricultion': 'Immatriculation', 'KM_actuel': 'KM_Actuel', 'Vehicule': 'Vehicule_ID', 'id': 'ID'}
                    df_v = df_v.rename(columns=corrections)
                    if 'ID' not in df_v.columns: df_v.rename(columns={df_v.columns[0]: 'ID'}, inplace=True)
                    
                    date_cols = ['Date_Dernier_CT', 'Date_Achat']
                    for col in date_cols:
                        if col in df_v.columns: df_v[col] = pd.to_datetime(df_v[col], errors='coerce')

                    self.data['VEHICULES'] = df_v
                    
                    # --- INIT ONGLETS MANQUANTS ---
                    if 'ENTRETIENS' not in self.data:
                        self.data['ENTRETIENS'] = pd.DataFrame(columns=['ID', 'Vehicule_ID', 'Date_Saisie', 'Date_Intervention', 'Type', 'Kilometrage', 'Cout', 'Notes'])
                    
                    if 'DIAGNOSTICS' not in self.data:
                        self.data['DIAGNOSTICS'] = pd.DataFrame(columns=['ID', 'Vehicule_ID', 'Date_Saisie', 'Date_Detection', 'Code_Defaut', 'Resume_IA', 'Analyse_IA_Diag', 'Cout_Estime', 'Sante_Vehicule'])
                    else:
                        if 'Resume_IA' not in self.data['DIAGNOSTICS'].columns:
                            self.data['DIAGNOSTICS']['Resume_IA'] = ""

                    self.load_status = f"✅ Succès : {len(df_v)} véhicule(s)."
                    return True
                else:
                    self.load_status = "⚠️ Erreur : Onglet VEHICULES manquant."
                    return False
            except Exception as e:
                self.load_status = f"❌ Erreur structure : {str(e)}"
                return False
        return False

    def save_db(self):
        if not self.db_path: return
        try:
            with pd.ExcelWriter(self.db_path, engine='openpyxl') as writer:
                for sheet, df in self.data.items():
                    df_save = df.copy()
                    for col in df_save.columns:
                        if pd.api.types.is_datetime64_any_dtype(df_save[col]) or 'Date' in col:
                             df_save[col] = pd.to_datetime(df_save[col], errors='coerce').dt.strftime('%Y-%m-%d')
                    df_save.to_excel(writer, sheet_name=sheet, index=False)
        except Exception as e: print(f"Erreur Sauvegarde: {e}")

    # --- VEHICULES ---
    def get_vehicle_list(self):
        df = self.data.get('VEHICULES', pd.DataFrame())
        if df.empty: return []
        return [(r['ID'], f"{r.get('Nom')} - {r.get('Immatriculation')}") for _, r in df.iterrows()]

    def get_vehicle_info(self, v_id):
        df = self.data['VEHICULES']
        row = df[df['ID'] == v_id]
        return row.iloc[0].to_dict() if not row.empty else None

    def add_vehicle(self, info):
        df = self.data['VEHICULES']
        info['ID'] = 1 if df.empty else df['ID'].max() + 1
        self.data['VEHICULES'] = pd.concat([df, pd.DataFrame([info])], ignore_index=True)
        self.save_db()
        return info['ID']

    # --- NOTES CRUD ---
    def get_notes_list(self, v_id):
        if 'ENTRETIENS' not in self.data: return []
        df = self.data['ENTRETIENS']
        col_link = 'Vehicule' if 'Vehicule' in df.columns else 'Vehicule_ID'
        if col_link not in df.columns: return []
        
        notes_df = df[df[col_link] == v_id].copy()
        sort_col = 'Date_Intervention' if 'Date_Intervention' in notes_df.columns else ('Date' if 'Date' in notes_df.columns else 'Date_Saisie')

        if not notes_df.empty and sort_col in notes_df.columns:
            notes_df[sort_col] = pd.to_datetime(notes_df[sort_col], errors='coerce')
            notes_df = notes_df.sort_values(by=sort_col, ascending=False)
            
        return notes_df.to_dict('records')

    def add_note(self, v_id, type_n, text_n, date_interv):
        df = self.data['ENTRETIENS']
        new_id = 1 if df.empty else df[df.columns[0]].max() + 1 
        col_link = 'Vehicule' if 'Vehicule' in df.columns else 'Vehicule_ID'
        v_info = self.get_vehicle_info(v_id)
        km = v_info.get('KM_Actuel', 0) if v_info else 0

        new_row = {
            'ID': new_id, col_link: v_id, 
            'Date_Saisie': datetime.now().strftime("%Y-%m-%d"),
            'Date_Intervention': date_interv.strftime("%Y-%m-%d"), 
            'Type': type_n, 'Notes': text_n, 'Kilometrage': km, 'Cout': 0
        }
        if 'Date_Intervention' not in df.columns and 'Date' in df.columns:
             new_row.pop('Date_Intervention')
             new_row['Date'] = date_interv.strftime("%Y-%m-%d")

        self.data['ENTRETIENS'] = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        self.save_db()

    def update_note(self, note_id, type_n, text_n, date_interv):
        df = self.data['ENTRETIENS']
        col_id = df.columns[0]
        mask = df[col_id] == note_id
        if mask.any():
            df.loc[mask, 'Type'] = type_n
            df.loc[mask, 'Notes'] = text_n
            date_col = 'Date_Intervention' if 'Date_Intervention' in df.columns else 'Date'
            df.loc[mask, date_col] = date_interv.strftime("%Y-%m-%d")
            self.save_db()
            return True
        return False

    def delete_note(self, note_id):
        df = self.data['ENTRETIENS']
        col_id = df.columns[0]
        self.data['ENTRETIENS'] = df[df[col_id] != note_id]
        self.save_db()

    # --- DIAGNOSTICS ---
    def get_diagnostic_history(self, v_id):
        if 'DIAGNOSTICS' not in self.data: return []
        df = self.data['DIAGNOSTICS']
        col_link = 'Vehicule' if 'Vehicule' in df.columns else 'Vehicule_ID'
        if col_link not in df.columns: return []

        diag_df = df[df[col_link] == v_id].copy()
        
        date_col = 'Date_Detection' if 'Date_Detection' in diag_df.columns else 'Date'
        if not diag_df.empty and date_col in diag_df.columns:
             diag_df[date_col] = pd.to_datetime(diag_df[date_col], errors='coerce')
             diag_df = diag_df.sort_values(by=date_col, ascending=False)

        return diag_df.to_dict('records')

    def save_diagnostic(self, v_id, codes, analyse, cout, sante, date_detect, resume=""):
        df = self.data.get('DIAGNOSTICS', pd.DataFrame())
        col_link = 'Vehicule' if 'Vehicule' in df.columns else 'Vehicule_ID'
        new_id = 1 if df.empty else (df.iloc[:, 0].max() + 1 if len(df) > 0 else 1)
        
        new_row = {
            'ID': new_id, col_link: v_id, 
            'Date_Saisie': datetime.now().strftime("%Y-%m-%d"),
            'Date_Detection': date_detect.strftime("%Y-%m-%d"),
            'Code_Defaut': codes, 
            'Resume_IA': resume, 
            'Analyse_IA_Diag': analyse, 
            'Cout_Estime': cout, 'Sante_Vehicule': sante
        }
        
        if 'Date_Detection' not in df.columns and 'Date' in df.columns:
             new_row.pop('Date_Detection')
             new_row.pop('Date_Saisie')
             new_row['Date'] = date_detect.strftime("%Y-%m-%d")

        self.data['DIAGNOSTICS'] = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True) if not df.empty else pd.DataFrame([new_row])
        self.save_db()

    # --- HELPERS IA ---
    def get_full_history_text(self, v_id):
        notes = self.get_notes_list(v_id)
        txt = "--- HISTORIQUE ENTRETIENS ---\n"
        if notes:
            for n in notes: 
                date_str = n.get('Date_Intervention', n.get('Date', n.get('Date_Saisie', '?')))
                if pd.api.types.is_datetime64_any_dtype(date_str): date_str = date_str.strftime('%Y-%m-%d')
                else: date_str = str(date_str).split(' ')[0]
                txt += f"- Le {date_str} : [{n.get('Type')}] {n.get('Notes')}\n"
        else:
            txt += "Aucun historique d'entretien.\n"
            
        diags = self.get_diagnostic_history(v_id)
        txt += "\n--- HISTORIQUE DÉFAUTS ---\n"
        if diags:
             for d in diags:
                  date_str = d.get('Date_Detection', d.get('Date', '?'))
                  if pd.api.types.is_datetime64_any_dtype(date_str): date_str = date_str.strftime('%Y-%m-%d')
                  else: date_str = str(date_str).split(' ')[0]
                  resume = d.get('Resume_IA', '')
                  txt += f"- Le {date_str} : Codes [{d.get('Code_Defaut')}]. Résumé: {resume} (Santé: {d.get('Sante_Vehicule')})\n"
        else:
             txt += "Aucun diagnostic précédent.\n"

        return txt

    def save_echeance(self, v_id, analyse):
        df = self.data.get('ECHEANCE', pd.DataFrame())
        col_link = 'Vehicule' if 'Vehicule' in df.columns else 'Vehicule_ID'
        if not df.empty: df = df[df[col_link] != v_id] 
        new_id = 1 if df.empty else (df.iloc[:, 0].max() + 1 if len(df) > 0 else 1)
        new_row = {'ID': new_id, col_link: v_id, 'Date_Calcul': datetime.now().strftime("%Y-%m-%d"), 'Analyse_IA_Echeance': analyse}
        self.data['ECHEANCE'] = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True) if not df.empty else pd.DataFrame([new_row])
        self.save_db()