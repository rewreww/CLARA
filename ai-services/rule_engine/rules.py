# Clinical rule engine for CLARA
# Hybrid rule system: works with both vitals and extracted lab values

from typing import Dict, Any, List, Optional


class RuleEngine:
    """
    Rule-based engine for clinical decision support.
    Two entry points:
      - evaluate(patient_data)   → for vitals-based rules (blood pressure, SpO2, temp)
      - evaluate_labs(lab_data)  → for extracted lab value rules (chemistry, hematology)
    """

    def __init__(self):
        self.vital_rules = [
            self._rule_emergency_cardiac,
            self._rule_hypertensive_crisis,
            self._rule_hypoxemia,
            self._rule_fever_infection,
            self._lab_rule_neutrophils,
        ]
        self.lab_rules = [
            self._lab_rule_creatinine,
            self._lab_rule_potassium,
            self._lab_rule_sodium,
            self._lab_rule_glucose,
            self._lab_rule_cholesterol,
            self._lab_rule_hemoglobin,
            self._lab_rule_wbc,
            self._lab_rule_platelet,
            self._lab_rule_hematocrit,
            self._lab_rule_sgpt,
            self._lab_rule_neutrophils
        ]

    # ── Public entry points ───────────────────────────────────────────────────

    def evaluate(self, patient_data: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate vital-sign rules. Keys must include bloodPressureSystolic etc."""
        flags = []
        is_emergency = False

        for rule in self.vital_rules:
            try:
                result = rule(patient_data)
                if result.get("flag"):
                    flags.append(result["message"])
                    if result.get("emergency"):
                        is_emergency = True
            except (KeyError, TypeError):
                # Skip rule if expected key is missing
                continue

        return {"flags": flags, "is_emergency": is_emergency}

    def evaluate_labs(self, lab_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Evaluate lab-based rules against extracted lab results.
        lab_results is the list returned by your extractor endpoints:
        [{"test_name": "CREATININE", "value": 1.8, "unit": "mg/dL", ...}, ...]
        """
        # Build a lookup dict: test_name → result dict (case-insensitive)
        lookup: Dict[str, Dict] = {
            r["test_name"].upper(): r
            for r in lab_results
            if isinstance(r, dict) and "test_name" in r
        }

        flags = []
        is_emergency = False

        for rule in self.lab_rules:
            try:
                result = rule(lookup)
                if result.get("flag"):
                    flags.append(result["message"])
                    if result.get("emergency"):
                        is_emergency = True
            except (KeyError, TypeError):
                continue

        return {"flags": flags, "is_emergency": is_emergency}

    def evaluate_all(
        self,
        lab_results: List[Dict[str, Any]],
        vitals: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Convenience method — run both lab and vital rules together.
        vitals is optional; if not provided only lab rules run.
        """
        lab_eval = self.evaluate_labs(lab_results)
        vital_eval = self.evaluate(vitals) if vitals else {"flags": [], "is_emergency": False}

        all_flags    = lab_eval["flags"] + vital_eval["flags"]
        is_emergency = lab_eval["is_emergency"] or vital_eval["is_emergency"]

        return {
            "flags":        all_flags,
            "is_emergency": is_emergency,
            "flag_count":   len(all_flags),
        }

    # ── Vital-sign rules ─────────────────────────────────────────────────────

    def _rule_emergency_cardiac(self, patient: Dict[str, Any]) -> Dict[str, Any]:
        """Chest pain + shortness of breath → possible MI"""
        symptoms = patient.get("symptoms", [])
        if "chest pain" in symptoms and "shortness of breath" in symptoms:
            return {
                "flag": True,
                "message": "EMERGENCY: Possible myocardial infarction — chest pain with shortness of breath.",
                "emergency": True,
            }
        return {"flag": False}

    def _rule_hypertensive_crisis(self, patient: Dict[str, Any]) -> Dict[str, Any]:
        """Systolic > 180 or diastolic > 120 → hypertensive crisis"""
        systolic  = patient.get("bloodPressureSystolic", 0)
        diastolic = patient.get("bloodPressureDiastolic", 0)
        if systolic > 180 or diastolic > 120:
            return {
                "flag": True,
                "message": f"EMERGENCY: Hypertensive crisis — BP {systolic}/{diastolic} mmHg. Immediate intervention required.",
                "emergency": True,
            }
        return {"flag": False}

    def _rule_hypoxemia(self, patient: Dict[str, Any]) -> Dict[str, Any]:
        """SpO2 < 95% → hypoxemia"""
        spo2 = patient.get("oxygenSaturation", 100)
        if spo2 < 95:
            return {
                "flag": True,
                "message": f"WARNING: Hypoxemia detected — SpO2 {spo2}%. Oxygen supplementation may be needed.",
            }
        return {"flag": False}

    def _rule_fever_infection(self, patient: Dict[str, Any]) -> Dict[str, Any]:
        """Fever > 100.4°F with symptoms → possible infection"""
        temp     = patient.get("temperature", 98.6)
        symptoms = patient.get("symptoms", [])
        if temp > 100.4 and len(symptoms) > 0:
            return {
                "flag": True,
                "message": f"WARNING: Possible infection — temperature {temp}°F with active symptoms.",
            }
        return {"flag": False}

    # ── Lab-based rules ──────────────────────────────────────────────────────
    # Each rule receives the lookup dict {TEST_NAME: result_dict}

    def _lab_rule_creatinine(self, labs: Dict) -> Dict[str, Any]:
        """Creatinine > 1.4 mg/dL → renal impairment warning"""
        r = labs.get("CREATININE")
        if r and isinstance(r.get("value"), (int, float)):
            val = r["value"]
            if val > 2.0:
                return {
                    "flag": True,
                    "message": f"EMERGENCY: Creatinine critically elevated at {val} mg/dL — possible acute kidney injury.",
                    "emergency": True,
                }
            if val > 1.4:
                return {
                    "flag": True,
                    "message": f"WARNING: Creatinine elevated at {val} mg/dL — monitor renal function.",
                }
        return {"flag": False}

    def _lab_rule_potassium(self, labs: Dict) -> Dict[str, Any]:
        """Potassium out of 3.5–5.0 mmol/L → cardiac arrhythmia risk"""
        r = labs.get("POTASSIUM")
        if r and isinstance(r.get("value"), (int, float)):
            val = r["value"]
            if val < 3.0 or val > 6.0:
                return {
                    "flag": True,
                    "message": f"EMERGENCY: Potassium critically abnormal at {val} mmol/L — high risk of cardiac arrhythmia.",
                    "emergency": True,
                }
            if val < 3.5 or val > 5.0:
                return {
                    "flag": True,
                    "message": f"WARNING: Potassium {val} mmol/L is outside normal range (3.5–5.0). Monitor for arrhythmia.",
                }
        return {"flag": False}

    def _lab_rule_sodium(self, labs: Dict) -> Dict[str, Any]:
        """Sodium out of 135–145 mmol/L"""
        r = labs.get("SODIUM")
        if r and isinstance(r.get("value"), (int, float)):
            val = r["value"]
            if val < 125 or val > 155:
                return {
                    "flag": True,
                    "message": f"EMERGENCY: Sodium critically abnormal at {val} mmol/L — risk of seizure or cardiac event.",
                    "emergency": True,
                }
            if val < 135 or val > 145:
                return {
                    "flag": True,
                    "message": f"WARNING: Sodium {val} mmol/L is outside normal range (135–145 mmol/L).",
                }
        return {"flag": False}

    def _lab_rule_glucose(self, labs: Dict) -> Dict[str, Any]:
        """FBS < 70 or > 126 mg/dL"""
        r = labs.get("FBS")
        if r and isinstance(r.get("value"), (int, float)):
            val = r["value"]
            if val < 50:
                return {
                    "flag": True,
                    "message": f"EMERGENCY: Critically low blood glucose at {val} mg/dL — risk of hypoglycemic coma.",
                    "emergency": True,
                }
            if val < 70:
                return {
                    "flag": True,
                    "message": f"WARNING: Hypoglycemia — FBS {val} mg/dL is below normal (70–110 mg/dL).",
                }
            if val > 200:
                return {
                    "flag": True,
                    "message": f"WARNING: Significantly elevated FBS at {val} mg/dL — evaluate for uncontrolled diabetes.",
                }
            if val > 126:
                return {
                    "flag": True,
                    "message": f"WARNING: FBS {val} mg/dL exceeds normal threshold — possible diabetes mellitus.",
                }
        return {"flag": False}

    def _lab_rule_cholesterol(self, labs: Dict) -> Dict[str, Any]:
        """Total cholesterol > 200 mg/dL → cardiovascular risk"""
        r = labs.get("TOTAL CHOLESTEROL")
        if r and isinstance(r.get("value"), (int, float)):
            val = r["value"]
            if val > 240:
                return {
                    "flag": True,
                    "message": f"WARNING: Total cholesterol critically high at {val} mg/dL — high cardiovascular risk.",
                }
            if val > 200:
                return {
                    "flag": True,
                    "message": f"WARNING: Total cholesterol borderline high at {val} mg/dL — lifestyle modification advised.",
                }
        return {"flag": False}

    def _lab_rule_hemoglobin(self, labs: Dict) -> Dict[str, Any]:
        """Hemoglobin low → anemia"""
        r = labs.get("HEMOGLOBIN")
        if r and isinstance(r.get("value"), (int, float)):
            val = r["value"]
            if val < 80:
                return {
                    "flag": True,
                    "message": f"EMERGENCY: Severe anemia — hemoglobin critically low at {val} g/L.",
                    "emergency": True,
                }
            if val < 120:
                return {
                    "flag": True,
                    "message": f"WARNING: Anemia detected — hemoglobin {val} g/L is below normal range.",
                }
        return {"flag": False}

    def _lab_rule_wbc(self, labs: Dict) -> Dict[str, Any]:
        """WBC out of 4.5–11.0 x10^9/L"""
        r = labs.get("WBC")
        if r and isinstance(r.get("value"), (int, float)):
            val = r["value"]
            if val > 30 or val < 2:
                return {
                    "flag": True,
                    "message": f"EMERGENCY: WBC critically abnormal at {val} x10^9/L — possible sepsis or hematologic emergency.",
                    "emergency": True,
                }
            if val > 11 or val < 4.5:
                return {
                    "flag": True,
                    "message": f"WARNING: WBC {val} x10^9/L is outside normal range (4.5–11.0) — evaluate for infection or immune disorder.",
                }
        return {"flag": False}

    def _lab_rule_platelet(self, labs: Dict) -> Dict[str, Any]:
        """Platelet count low → bleeding risk"""
        r = labs.get("PLATELET COUNT")
        if r and isinstance(r.get("value"), (int, float)):
            val = r["value"]
            if val < 50:
                return {
                    "flag": True,
                    "message": f"EMERGENCY: Severe thrombocytopenia — platelet count critically low at {val} x10^9/L.",
                    "emergency": True,
                }
            if val < 150:
                return {
                    "flag": True,
                    "message": f"WARNING: Thrombocytopenia — platelet count {val} x10^9/L is below normal (150–400).",
                }
        return {"flag": False}

    def _lab_rule_hematocrit(self, labs: Dict) -> Dict[str, Any]:
        """Hematocrit low → anemia indicator"""
        r = labs.get("HEMATOCRIT")
        if r and isinstance(r.get("value"), (int, float)):
            val = r["value"]
            if val < 30:
                return {
                    "flag": True,
                    "message": f"EMERGENCY: Hematocrit critically low at {val}% — severe anemia.",
                    "emergency": True,
                }
            if val < 37:
                return {
                    "flag": True,
                    "message": f"WARNING: Hematocrit low at {val}% — consistent with anemia.",
                }
        return {"flag": False}

    def _lab_rule_neutrophils(self, labs: Dict) -> Dict[str, Any]:
        """Neutrophils > 70% → possible bacterial infection or stress response"""
        r = labs.get("NEUTROPHILS")
        if r and isinstance(r.get("value"), (int, float)):
            val = r["value"]
            if val > 70:
                return {
                    "flag": True,
                    "message": f"WARNING: Neutrophilia at {val}% — consider bacterial infection or physiologic stress.",
                }
        return {"flag": False}

    def _lab_rule_sgpt(self, labs: Dict) -> Dict[str, Any]:
        """SGPT/ALT elevated → liver stress"""
        r = labs.get("SGPT/ALT")
        if r and isinstance(r.get("value"), (int, float)):
            val = r["value"]
            if val > 200:
                return {
                    "flag": True,
                    "message": f"WARNING: SGPT/ALT significantly elevated at {val} U/L — evaluate for hepatotoxicity or liver disease.",
                }
            if val > 56:
                return {
                    "flag": True,
                    "message": f"WARNING: SGPT/ALT mildly elevated at {val} U/L — monitor liver function.",
                }
        return {"flag": False}


# Singleton instance used across the app
rule_engine = RuleEngine()