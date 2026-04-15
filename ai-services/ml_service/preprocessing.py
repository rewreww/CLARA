# Data preprocessing utilities for CLARA ML service
# TODO: Implement actual preprocessing pipeline

import pandas as pd
from typing import Dict, Any

def preprocess_patient_data(patient_data: Dict[str, Any]) -> pd.DataFrame:
    """
    Preprocess raw patient data into model-ready format.
    """
    # Convert to DataFrame
    df = pd.DataFrame([patient_data])

    # Basic preprocessing
    df['sex_encoded'] = df['sex'].map({'M': 1, 'F': 0})
    df['symptom_count'] = df['symptoms'].apply(len)

    # Select features
    features = [
        'age', 'sex_encoded', 'symptom_count',
        'bloodPressureSystolic', 'bloodPressureDiastolic',
        'heartRate', 'temperature', 'oxygenSaturation'
    ]

    return df[features]

def validate_patient_data(patient_data: Dict[str, Any]) -> bool:
    """
    Validate patient data structure.
    """
    required_fields = [
        'age', 'sex', 'symptoms',
        'bloodPressureSystolic', 'bloodPressureDiastolic',
        'heartRate', 'temperature', 'oxygenSaturation'
    ]

    for field in required_fields:
        if field not in patient_data:
            return False

    return True