# Clinical rule engine for CLARA
# Simple rule-based system for safety checks

from typing import Dict, Any, List

class RuleEngine:
    """
    Rule-based engine for clinical decision support.
    """

    def __init__(self):
        self.rules = [
            self._rule_emergency_cardiac,
            self._rule_hypertensive_crisis,
            self._rule_hypoxemia,
            self._rule_fever_infection
        ]

    def evaluate(self, patient_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluate all rules against patient data.
        """
        flags = []
        is_emergency = False

        for rule in self.rules:
            result = rule(patient_data)
            if result['flag']:
                flags.append(result['message'])
                if result.get('emergency', False):
                    is_emergency = True

        return {
            'flags': flags,
            'is_emergency': is_emergency
        }

    def _rule_emergency_cardiac(self, patient: Dict[str, Any]) -> Dict[str, Any]:
        """Rule: Chest pain + shortness of breath → Emergency"""
        has_chest_pain = 'chest pain' in patient['symptoms']
        has_shortness_breath = 'shortness of breath' in patient['symptoms']

        if has_chest_pain and has_shortness_breath:
            return {
                'flag': True,
                'message': 'Emergency: Possible myocardial infarction - seek immediate medical attention',
                'emergency': True
            }
        return {'flag': False}

    def _rule_hypertensive_crisis(self, patient: Dict[str, Any]) -> Dict[str, Any]:
        """Rule: High blood pressure → Hypertensive crisis"""
        systolic = patient['bloodPressureSystolic']
        diastolic = patient['bloodPressureDiastolic']

        if systolic > 180 or diastolic > 120:
            return {
                'flag': True,
                'message': 'Hypertensive crisis detected - immediate intervention required',
                'emergency': True
            }
        return {'flag': False}

    def _rule_hypoxemia(self, patient: Dict[str, Any]) -> Dict[str, Any]:
        """Rule: Low oxygen saturation"""
        if patient['oxygenSaturation'] < 95:
            return {
                'flag': True,
                'message': 'Hypoxemia detected - oxygen supplementation may be needed'
            }
        return {'flag': False}

    def _rule_fever_infection(self, patient: Dict[str, Any]) -> Dict[str, Any]:
        """Rule: Fever with symptoms"""
        has_fever = patient['temperature'] > 100.4
        has_symptoms = len(patient['symptoms']) > 0

        if has_fever and has_symptoms:
            return {
                'flag': True,
                'message': 'Possible infection - monitor closely and consider diagnostic tests'
            }
        return {'flag': False}

# Instantiate rule engine
rule_engine = RuleEngine()