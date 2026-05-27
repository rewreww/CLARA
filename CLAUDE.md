# CLARA — Project Memory

## Project Overview
CLARA (Clinical LLM-Assisted Reasoning Assistant) is a cardiovascular clinical decision support system for Philippine hospitals. Stack: React + Vite frontend, ASP.NET Core backend, Python FastAPI AI services, Ollama (local LLM), ChromaDB (RAG), RandomForest ML for ECG risk.

## Current Branch
`claude/enhance-clara-philippines-rag-KWOox`

---

## EncountersPanel — Core Concept (DO NOT CODE YET)

**Purpose:** Each patient has multiple hospital visits. EncountersPanel is a visit-by-visit timeline analyzer that lets a cardiologist navigate between past admissions and see what changed between visits.

### Navigation
- Date shown at top center: `[ Encounter 2 of 3 · Apr 28 2026 ]`
- Left/right arrows to move between visits (chronological order, oldest → newest)
- Arrows disabled at ends
- First visit shows "Baseline Visit" banner instead of diff

### Layout per Encounter Page
1. **Header** — Admission date, discharge date, attending physician, facility
2. **Diagnosis** — Primary and secondary diagnoses for that visit
3. **What Changed** — Diff panel comparing current vs previous encounter:
   - `▲` value went up, `▼` value went down
   - `+` new medication/finding added, `-` medication/finding removed
   - `≠` non-numeric change (e.g., diagnosis renamed)
   - `✓` no change (shown for critical items only)
4. **Vitals at Discharge** — BP, HR, RR, Temp, SpO2
5. **Medications** — Full list for that visit
6. **Hospital Course** — Timestamped ward notes
7. **Follow-up Orders** — Extracted from plan section, flagged if not fulfilled in subsequent visits

### Encounter Data Model
```
Encounter {
  id, admissionDate, dischargeDate,
  diagnosis: string[],
  vitals: { bp, hr, rr, temp, spo2 },
  medications: [{ name, dose, frequency }],
  labs: [{ test, value, unit, flag }],
  hospitalCourse: [{ date, note }],
  followUpOrders: string[],
  attendingPhysician, facilityName
}
```

### Relationship to DischargePanel
- **DischargePanel** = deep dive on one full discharge summary
- **EncountersPanel** = longitudinal story across all visits with diffs

### Build Order (when ready)
1. `useEncounters.js` — aggregates all discharge PDFs per patient, sorted by date
2. `EncountersPanel.jsx` — navigator UI with diff logic
3. Extend `discharge_parser.py` — ensure medications + follow-up orders are reliably extracted

### Dummy Records Requirements
Each dummy patient needs 2–3 discharge PDFs with:
- Slightly different diagnoses between visits
- Lab values that drift (creatinine up, hemoglobin recovering, K+ normalizing)
- Medication changes between visits (one added, one stopped)
- Follow-up orders in plan section
- Different admission/discharge dates

---

## Other Planned Features (lower priority)
- Quick action buttons per panel (contextual one-tap chat prompts)
- Lab trend sparklines across visits
- ECG risk trajectory graph (risk score over time)
- "Since Last Visit" AI brief (auto-generated on patient load)
- Medication reconciliation table (last discharge vs current orders)
- Outstanding follow-up checker

---

## Architecture Notes
- All data sourced from discharge PDFs in patient folders — no new data sources needed
- Encounters feature is a data aggregation + diff layer on top of existing discharge parser
- Using Ollama locally (intentional — no internet dependency, HIPAA-safe for PH hospital context)
- ML service on port 8002, LLM on 8001, medical text API on 8000, ASP.NET backend default port
