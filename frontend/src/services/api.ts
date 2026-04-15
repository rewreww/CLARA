import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:5000';

export interface PatientData {
  age: number;
  sex: string;
  symptoms: string[];
  bloodPressureSystolic: number;
  bloodPressureDiastolic: number;
  heartRate: number;
  temperature: number;
  oxygenSaturation: number;
}

export interface ChatResponse {
  response: string;
  reasoning: string;
  safetyNote: string;
  timestamp: string;
}

export interface PredictionResponse {
  diagnosis: string;
  confidence: number;
  recommendations: string[];
}

export const sendChatMessage = async (message: string, patientData: PatientData): Promise<ChatResponse> => {
  const response = await axios.post<ChatResponse>(`${API_BASE_URL}/api/chat`, {
    message,
    patientData
  });
  return response.data;
};

export const getPrediction = async (patientData: PatientData): Promise<PredictionResponse> => {
  const response = await axios.post<PredictionResponse>(`${API_BASE_URL}/api/predict`, patientData);
  return response.data;
};

export const evaluateRules = async (patientData: PatientData): Promise<any> => {
  const response = await axios.post(`${API_BASE_URL}/api/rules/evaluate`, patientData);
  return response.data;
};