import os
from groq import Groq
import json
from datetime import date

class AIEngine:
    def __init__(self, api_key, model_name="llama-3.3-70b-versatile"):
        self.client = Groq(api_key=api_key)
        self.model = model_name

    def _format_technical_context(self, car):
        """Transforme le dictionnaire brut de la DB en fiche technique lisible pour l'IA"""
        # Gestion des valeurs nulles
        def val(k, unit=""):
            v = car.get(k)
            return f"{v} {unit}" if v is not None and v != "" else "N/A"

        return f"""
        [FICHE TECHNIQUE VÉHICULE]
        IDENTIFICATION :
        - Véhicule : {val('marque')} {val('modele')} (Année {val('annee')})
        - Immat : {val('immatriculation')}
        - VIN : {val('vin')}
        - KM Actuel : {val('km_actuel', 'km')}
        - Carburant : {val('carburant')}

        MOTEUR & PERFORMANCES :
        - Code Moteur : {val('code_moteur')}
        - Cylindrée : {val('cylindree', 'cc')} / Architecture : {val('architecture')}
        - Puissance : {val('puissance_ch', 'ch')} (Fiscale : {val('puissance_fiscale', 'CV')})
        - Turbo : {val('turbo')}
        - Couple : {val('couple_nm', 'Nm')}
        - Soupapes : {val('soupapes')}

        TRANSMISSION & CHÂSSIS :
        - Boîte : {val('boite_vitesse')} ({val('nb_vitesses')} rapports)
        - Roues Motrices : {val('roues_motrices')}
        - Poids : {val('poids_kg', 'kg')}

        FLUIDES & ENTRETIEN :
        - Capacité Huile : {val('capacite_huile_l', 'L')}
        - Viscosité Recommandée : {val('viscosite_huile')}
        - Réservoir : {val('capacite_reservoir', 'L')}
        - Dernière Vidange connue : {val('derniere_vidange')}
        """

    def analyze_obd(self, car_info, history_text, problem_desc, current_date):
        tech_context = self._format_technical_context(car_info)
        
        prompt = f"""
        Rôle : Expert Mécanicien Automobile Senior & Ingénieur Motoriste.
        Date du jour : {current_date}

        CONTEXTE TECHNIQUE EXHAUSTIF :
        {tech_context}

        HISTORIQUE DU VÉHICULE (Interventions & Pannes passées) :
        {history_text}

        PROBLÈME SIGNALÉ / CODE DÉFAUT :
        {problem_desc}

        TACHE :
        Analyse ce problème en prenant en compte TOUS les détails techniques ci-dessus.
        Exemple : Si le moteur est un N47, pense aux problèmes de chaîne. Si c'est un code de pression d'huile, vérifie la viscosité recommandée ci-dessus.
        
        FORMAT DE RÉPONSE ATTENDU (JSON STRICT) :
        {{
            "titre_rapport": "Titre technique précis",
            "resume_court": "Synthèse pour le client (max 30 mots)",
            "analyse_technique_detaillee": "Analyse approfondie liant le défaut aux spécificités techniques (Code moteur, Kilométrage, Historique).",
            "gravite_score": 1 (faible) à 5 (critique),
            "sante_vehicule": "ROUGE" (Stop immédiat), "ORANGE" (Garage rapide) ou "VERT" (Observation),
            "plan_action_propose": "Liste numérotée des étapes de diagnostic/réparation",
            "estimation_cout_pieces_mo": "Fourchette de prix (ex: 200-300€)"
        }}
        """
        try:
            completion = self.client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model=self.model,
                temperature=0.2, # Température basse pour plus de rigueur technique
                response_format={"type": "json_object"}
            )
            return json.loads(completion.choices[0].message.content)
        except Exception as e:
            return {"error": f"Erreur IA : {str(e)}"}

    def check_maintenance_schedule(self, car_info, history_text):
        tech_context = self._format_technical_context(car_info)
        
        prompt = f"""
        Rôle : Gestionnaire de Flotte & Expert Maintenance.
        
        CONTEXTE TECHNIQUE :
        {tech_context}

        HISTORIQUE CONNU :
        {history_text}

        TACHE :
        Établir le plan de maintenance prévisionnel pour cette année et l'année prochaine.
        1. Vérifie la cohérence de la dernière vidange par rapport au KM actuel et à la date.
        2. Vérifie si la distribution (courroie/chaîne) est à faire selon le Code Moteur et le KM.
        3. Vérifie les échéances fluides (Frein, Refroidissement).
        
        FORMAT DE SORTIE : Markdown clair.
        Structure :
        ### 🚨 Urgences / À faire immédiatement
        ### 📅 Plan Année N (Cette année)
        ### 📅 Plan Année N+1
        ### ℹ️ Note Spécifique Moteur (Basé sur le code moteur {car_info.get('code_moteur', 'inconnu')})
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
        except Exception as e:
            return {"error": str(e)}

