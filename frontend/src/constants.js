// API base URLs routed through Vite proxy.
export const LLM_URL = '/api/llm'
export const LABS_URL = '/api/labs'

export const STATUS_COLOR = {
  critical: '#ef4444',
  review: '#f59e0b',
  stable: '#10b981',
}

export const FOLDER_SECTIONS = [
  { key: 'overview', label: 'Overview', icon: '⊕' },
  { key: 'discharge', label: 'Discharge', icon: '📋' },
  { key: 'encounters', label: 'Encounters', icon: '🏥' },
  { key: 'imaging', label: 'Imaging', icon: '🔬' },
  {
    key: 'labs',
    label: 'Labs',
    icon: '🧪',
    children: [
      { key: 'chemistry', label: 'Chemistry' },
      { key: 'hematology', label: 'Hematology' },
      { key: 'microscopy', label: 'Microscopy' },
    ],
  },
  { key: 'prescriptions', label: 'Prescriptions', icon: '💊' },
]

export const QUICK_PROMPTS = [
  'Any critical values?',
  'Cholesterol summary',
  'Anemia indicators?',
  'BP guidelines',
  'Kidney function?',
]
