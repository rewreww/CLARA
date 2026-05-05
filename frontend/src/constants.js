// API base URLs — routed through Vite proxy (no CORS issues)
export const LLM_URL  = '/api/llm'
export const LABS_URL = '/api/labs'

// Status colours
export const STATUS_COLOR = {
  critical: '#ef4444',
  review:   '#f59e0b',
  stable:   '#10b981',
}

// Mock patients — replace with real API call when backend has a patients endpoint
export const PATIENTS = [
  { id:'00001', name:'Juan dela Cruz',   age:58, sex:'M', status:'review',   ward:'Cardiology' },
  { id:'00002', name:'Maria Santos',     age:44, sex:'F', status:'stable',   ward:'General'    },
  { id:'00003', name:'Roberto Reyes',    age:67, sex:'M', status:'critical', ward:'ICU'        },
  { id:'00004', name:'Anita Bautista',   age:52, sex:'F', status:'stable',   ward:'General'    },
  { id:'00005', name:'Carlos Mendoza',   age:71, sex:'M', status:'review',   ward:'Cardiology' },
]

// Folder sections shown in patient tree
export const FOLDER_SECTIONS = [
  { key:'overview',     label:'Overview',      icon:'⊕' },
  { key:'discharge',    label:'Discharge',     icon:'📋' },
  { key:'encounters',   label:'Encounters',    icon:'🏥' },
  { key:'imaging',      label:'Imaging',       icon:'🔬' },
  {
    key:'labs', label:'Labs', icon:'🧪',
    children:[
      { key:'chemistry',  label:'Chemistry'  },
      { key:'hematology', label:'Hematology' },
      { key:'microscopy', label:'Microscopy' },
    ],
  },
  { key:'prescriptions', label:'Prescriptions', icon:'💊' },
]

// Quick prompt suggestions shown above chat input
export const QUICK_PROMPTS = [
  'Any critical values?',
  'Cholesterol summary',
  'Anemia indicators?',
  'BP guidelines',
  'Kidney function?',
]
