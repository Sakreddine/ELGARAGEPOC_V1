import os
import json
import time
from groq import Groq

class AIEngine:
    def __init__(self, api_key, model_name="llama-3.3-70b-versatile"):
        """
        Initialise le moteur Groq avec la clé fournie par l'utilisateur.
        """
        self.api_key = api_key
        self.model = model_name
        self.client = None
        
        # On ne tente la connexion que si une clé est fournie
        if self.api_key:
            try:
                self.client = Groq(api_key=self.api_key)
            except Exception as e:
                print(f"Erreur init Groq: {e}")

    def _extract_json(self, text):
        try:
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1]
            
            start = text.find('{')
            end = text.rfind('}') + 1
            return json.loads(text[start:end]) if start != -1 and end != -1 else None
        except: return None

    def _send_request(self, prompt, is_json_expected=False):
        if not self.client:
            return {"error": "Clé API Groq manquante. Veuillez l'entrer dans la barre latérale."}

        print(f"\n[Groq Cloud] Envoi vers {self.model}...")
        
        try:
            chat_completion = self.client.chat.completions.create(
                messages=[
                    {"role": "system", "content": "Tu es un assistant expert automobile qui répond strictement au format demandé."},
                    {"role": "user", "content": prompt}
                ],
                model=self.model,
                temperature=0.2 if is_json_expected else 0.5,
                max_tokens=4096,
                top_p=1,
                stop=None,
                stream=False,
                response_format={"type": "json_object"} if is_json_expected else None
            )
            
            return chat_completion.choices[0].message.content
            
        except Exception as e:
            return {"error": f"Erreur API Groq (Modèle obsolète ou clé invalide) : {str(e)}"}

    def analyze_obd(self, vehicle_info, history_text, codes_input, date_detection):
        prompt = f"""
        CONTEXTE : Expert technique automobile.
        VÉHICULE : {vehicle_info.get('Marque')} {vehicle_info.get('Modele')} ({vehicle_info.get('Annee')}) - {vehicle_info.get('KM_Actuel')} KM.
        DATE : {date_detection}
        CODES : "{codes_input}"
        HISTORIQUE : {history_text}
        
        TÂCHE : Rédiger un rapport de pré-diagnostic structuré en JSON.
        
        FORMAT JSON ATTENDU :
        {{
            "titre_rapport": "Titre explicite",
            "resume_court": "Une phrase de synthèse pour l'historique.",
            "analyse_technique_detaillee": "Analyse approfondie, corrélations des codes, hypothèses.",
            "plan_action_propose": "Étapes de diagnostic recommandées.",
            "gravite_score": "1-5",
            "sante_vehicule": "VERT ou ROUGE",
            "estimation_cout_pieces_mo": "Fourchette prix"
        }}
        """
        
        response_text = self._send_request(prompt, is_json_expected=True)
        
        if isinstance(response_text, dict) and "error" in response_text:
            response_text['debug_prompt'] = prompt
            return response_text

        data = self._extract_json(response_text)
        if data: 
            data['debug_prompt'] = prompt
            return data
        
        return {
            "titre_rapport": "ERREUR FORMAT",
            "resume_court": "Échec analyse.",
            "analyse_technique_detaillee": f"Réponse brute : {response_text}",
            "plan_action_propose": "-", "gravite_score": "?", "sante_vehicule": "Inconnu", "estimation_cout_pieces_mo": "?",
            "debug_prompt": prompt
        }

    def check_maintenance_schedule(self, vehicle_info, history_text):
        today = time.strftime('%d/%m/%Y')
        prompt = f"""
        Rédige un PLAN DE MAINTENANCE PRÉVISIONNEL professionnel (Format Markdown).
        
        VÉHICULE : {vehicle_info.get('Marque')} {vehicle_info.get('Modele')} | KM: {vehicle_info.get('KM_Actuel')}
        DATE : {today}
        HISTORIQUE : {history_text}
        
        STRUCTURE ATTENDUE :
        # RAPPORT DE MAINTENANCE
        ## 1. Synthèse État
        ## 2. Urgences (Année N)
        ## 3. Prévisionnel (N+1)
        ## 4. Conseils Atelier
        """
        
        response = self._send_request(prompt, is_json_expected=False)
        
        if isinstance(response, dict) and "error" in response:
            response['debug_prompt'] = prompt
            return response
            
        return {
            "response": response,
            "debug_prompt": prompt
        }