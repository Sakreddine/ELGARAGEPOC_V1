import os
from groq import Groq
import json
from datetime import date

class AIEngine:
    def __init__(self, api_key, model_name="llama-3.3-70b-versatile"):
        self.client = Groq(api_key=api_key)
        self.model = model_name

    def analyze_obd(self, car_info, history_text, problem_desc, current_date):
        prompt = f"""
        Rôle : Expert Mécanicien Senior.
        Véhicule : {car_info.get('Marque')} {car_info.get('Modele')} {car_info.get('Annee')} ({car_info.get('KM_Actuel')} km).
        Problème : {problem_desc}
        Historique : {history_text}
        Date : {current_date}

        Tâche : Analyse les codes défauts et symptômes.
        Format de réponse attendu (JSON strict) :
        {{
            "titre_rapport": "Titre court",
            "resume_court": "Synthèse pour le client (2 phrases max)",
            "analyse_technique_detaillee": "Explication complète des causes possibles",
            "gravite_score": 1-5 (int),
            "sante_vehicule": "ROUGE" ou "ORANGE" ou "VERT",
            "plan_action_propose": "Liste des étapes de réparation",
            "estimation_cout_pieces_mo": "Fourchette de prix estimée (Euros)"
        }}
        """
        try:
            completion = self.client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model=self.model,
                temperature=0.3,
                response_format={"type": "json_object"}
            )
            return json.loads(completion.choices[0].message.content)
        except Exception as e:
            return {"error": str(e)}

    def check_maintenance_schedule(self, car_info, history_text):
        prompt = f"""
        Analyse le plan de maintenance pour : {car_info.get('Marque')} {car_info.get('Modele')} ({car_info.get('KM_Actuel')} km).
        Historique connu : {history_text}
        
        Génère un rapport textuel Markdown clair avec :
        1. Les entretiens urgents (cette année).
        2. Les entretiens prévisionnels (année prochaine).
        3. Points de vigilance spécifiques à ce moteur.
        """
        try:
            completion = self.client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model=self.model,
                temperature=0.3
            )
            return {"response": completion.choices[0].message.content}
        except Exception as e:
            return {"error": str(e)}
