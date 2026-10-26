# CLARA — Cardiovascular Lab Analysis and Report Assistant

A hybrid clinical AI system for Philippine tertiary hospitals.
Combines RAG (retrieval-augmented generation), ML (XGBoost), PostgreSQL-backed patient records,
and free-tier or local LLM analysis with GroqCloud, Hugging Face, or Ollama
to assist clinicians in analyzing patient laboratory records and ECG findings.

---

## Architecture

Frontend (React + Vite) → Port 3000
.NET Backend API + PostgreSQL → Port 5000 backend/Program.cs
Legacy PDF/Labs Service (FastAPI) → Port 8000 ai-services/medical_text_api.py
LLM Service (FastAPI) → Port 8001 ai-services/llm_service/llm_client.py
ML Service (FastAPI) → Port 8002 ai-services/ml_service/app.py
Ollama (local LLM) → Port 11434


---

## Requirements

- Python 3.10+
- Node.js 22.13+
- .NET 8 SDK or a newer SDK capable of targeting .NET 8
- PostgreSQL running with the `clara_db` database configured in `backend/appsettings.json`
- GroqCloud Free plan API key, Hugging Face model downloads enabled for local RAG/LLM models, or Ollama installed and running for local LLM fallback
- Virtual environment (.venv)

---

## First-Time Setup

Run these commands from **PowerShell**.

### 1. Clone the repository
```powershell
git clone https://github.com/rewreww/clara.git
cd clara-system
```

### 2. Create and activate virtual environment
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks the activation script, use this once for the current terminal, then activate again:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

### 3. Install Python dependencies
```powershell
pip install -r ai-services/requirements.txt
```

If the PyTorch wheel download is slow or interrupted, retry with a longer timeout:

```powershell
pip install --timeout 120 --retries 10 -r ai-services/requirements.txt
```

### 4. Install frontend dependencies
```powershell
cd frontend
npm install
cd ..
```

### 5. Configure the LLM and RAG models
The project target is free-first operation for a student capstone environment. The recommended setup uses
GroqCloud's Free plan for fast LLM responses and Hugging Face embeddings for RAG:

```powershell
$env:DATA_SERVICE_URL = "http://localhost:5000/api/patientdata"
$env:LLM_PROVIDER = "groq"
$env:GROQ_API_KEY = "<your-groqcloud-api-key>"
$env:GROQ_MODEL = "openai/gpt-oss-20b"
$env:GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
$env:GROQ_RETRY_ATTEMPTS = "2"
$env:RAG_EMBEDDING_PROVIDER = "huggingface"
$env:RAG_EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
```

Optional fully local Hugging Face LLM mode:

```powershell
$env:LLM_PROVIDER = "huggingface"
$env:HF_MODEL = "Qwen/Qwen2.5-0.5B-Instruct"
$env:HF_TASK = "text-generation"
$env:HF_DEVICE = "-1"
$env:HF_MAX_INPUT_TOKENS = "4096"
$env:HF_MAX_NEW_TOKENS = "180"
$env:HF_TRUNCATION_SIDE = "left"
```

Optional local Ollama mode:

```powershell
ollama pull qwen2.5:7b
$env:LLM_PROVIDER = "ollama"
$env:OLLAMA_MODEL = "qwen2.5:7b"
```

Use `LLM_PROVIDER=groq` for GroqCloud. The similarly named xAI Grok API is not configured in this project.

### 5a. Build the guideline RAG index
The default RAG embedding model is Hugging Face `sentence-transformers/all-MiniLM-L6-v2`.
It downloads on first use and stores guideline vectors in `ai-services/rag/chroma_db`.

```powershell
cd ai-services
python -m rag.ingest
cd ..
```

### 6. Train the ML model (first time only)
Copy your CSV to the ML data folder first:

```powershell
New-Item -ItemType Directory -Force ai-services\ml_service\data
Copy-Item "C:\path\to\your.csv" ai-services\ml_service\data\dataset.csv
```

Then train the model:

```powershell
cd ai-services\ml_service
python train.py data/dataset.csv
cd ..\..
```


----


## One-command startup on Windows

After completing first-time setup, start CLARA from the repository root:

```powershell
.\start-clara.ps1
```

The backend also needs its database connection string. If it is not already in
your ignored `backend/appsettings.Development.local.json`, set it in the launching
terminal (replace the placeholders with your local values):

```powershell
$env:ConnectionStrings__ClaraDatabase = "Host=localhost;Port=5432;Database=clara_db;Username=<user>;Password=<password>"
```

Keep database passwords and API keys out of tracked files. The backend's existing
local JSON override takes precedence when it contains a connection string.

Or double-click **Start CLARA.cmd** in the repository folder. You can create a
Windows desktop shortcut to that file. The command starts the backend, ML service,
LLM service, and frontend in the background, checks their readiness and the
frontend API proxies, then opens `http://localhost:3000`. You can close the startup
terminal after it reports ready.

```powershell
.\status-clara.ps1          # Check the managed services
.\stop-clara.ps1            # Stop this launcher's services and their child processes
.\start-clara.ps1 -Check    # Check setup and ports without starting services
.\start-clara.ps1 -NoBrowser
.\start-clara.ps1 -LegacyParser  # Also start the optional old parser on 8000
.\start-clara.ps1 -WithOllama    # Also make Ollama available for local fallback
```

Double-click **Stop CLARA.cmd** to stop without typing. If PowerShell execution
policy blocks a `.ps1` file, use the `.cmd` entry point; it sets policy only for that
one PowerShell process and does not change your system policy.

The launcher:

- Uses `.venv\Scripts\python.exe` directly; activation is unnecessary.
- Checks Node (22.13+), .NET, required Python modules, frontend dependencies,
  saved model files, the configured PostgreSQL connection's host/port, and provider
  configuration. It never prints API keys or database passwords.
- Loads `ai-services/llm_service/.env`, respecting environment variables already
  set in the launching terminal. It preserves your selected LLM provider.
- Builds the backend before starting it. Existing restore assets are reused;
  a first build without them may need NuGet access.
- Starts Ollama when the selected LLM or embedding provider requires it, or when
  `-WithOllama` is passed. A healthy existing Ollama server is reused and left
  running on stop. Startup does not download models or test external LLM generation.
- Leaves PostgreSQL under your normal Windows service management. A TCP check is
  followed by the backend's actual database-read readiness check.
- Refuses occupied application ports instead of killing or adopting manually
  launched services. Running start again on an already healthy managed instance
  opens that instance without duplicating it.
- Keeps timestamped per-service stdout/stderr logs and supervisor state under
  `.clara/`, which is Git-ignored. Logs may contain application/patient information.
- Stops the managed process tree on request, partial-start failure, or if one of
  the main managed services exits. It does not automatically restart a failed run.
  Check `status-clara.ps1` and the logs, resolve the error, then start again.

For a slow machine, use `-TimeoutSeconds 300` (the readiness/build timeout per
step defaults to 180 seconds). Switching optional services on an existing run
requires stop followed by start.

This runs the regular backend: its existing startup migrations and patient-folder
sync still operate. Stopping terminates the owned processes; it does not wait for
an in-progress ingestion job to finish. The frontend uses Vite's development
server; backend/Python source and environment configuration changes require a
stop/start to take effect. Terminal-only environment variables are not available
when double-clicking from Explorer; use the ignored local configuration files for
that workflow.

The launcher provides local startup automation, not CI/CD or production hosting.
The checked-in Docker setup is not used by it.

### Launcher verification

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s scripts/tests -v
```

These tests include a Windows process-tree ownership check that confirms stopping
owned child processes leaves an unrelated process running.

## Running the System Manually

Open a separate PowerShell terminal for each service below.

Important notes:

- Start commands from `C:\clara-system`.
- Activate `.venv` in every terminal that runs a Python service.
- Run Uvicorn with `python -m uvicorn ...` so it uses the active virtual environment.
- The ML service folder is `ml_service` with an underscore. Do not type `ml\_service`; that backslash only appears when Markdown escapes the underscore.

### Terminal 1 — Backend API and patient database access

```powershell
cd C:\clara-system\backend
dotnet run
```


The backend is the source of truth for the UI. It reads/writes PostgreSQL and exposes patient data at
`http://localhost:5000/api/patientdata`. New PDFs under the Desktop `Patients` folder can be parsed with:

```bash
POST http://localhost:5000/api/pdfingestion/sync
GET  http://localhost:5000/api/pdfingestion/sync/status
```

### Patient Data Retrieval For The LLM

The LLM service uses a local MCP-style tool layer in `ai-services/llm_service/mcp_tools.py`.
These tools retrieve structured patient facts from PostgreSQL through the backend API:

```text
get_patient_context
get_abnormal_labs
get_recent_labs
get_diagnoses
get_medications
get_latest_discharge_summary
get_chemistry
get_hematology
get_microscopy
get_all_labs
get_trends
```

Use `get_patient_context` for broad clinical questions. Use the lab-specific tools when exact lab values
and reference ranges are needed. Guideline RAG remains separate and uses the Hugging Face embedding index
under `ai-services/rag`.

### Terminal 2 — LLM Service

```powershell
cd C:\clara-system
.\.venv\Scripts\Activate.ps1
cd .\ai-services\llm_service
python -m uvicorn llm_client:app --host 0.0.0.0 --port 8001 --reload
```

### Terminal 3 — ML Service

```powershell
cd C:\clara-system
.\.venv\Scripts\Activate.ps1
cd .\ai-services\ml_service
python -m uvicorn app:app --host 0.0.0.0 --port 8002
```

### Terminal 4 — Legacy parser service, only if you still need it

```powershell
cd C:\clara-system
.\.venv\Scripts\Activate.ps1
cd .\ai-services
python -m uvicorn medical_text_api:app --host 0.0.0.0 --port 8000 --reload
```

### Terminal 5 — Ollama (optional fallback)

```powershell
ollama serve
```

### Terminal 6 — Frontend

```powershell
cd C:\clara-system\frontend
npm run dev
```

Open your browser at: http://localhost:3000

### Quick Python Service Check

Use these if a Python service fails to start:

```powershell
C:\clara-system\.venv\Scripts\python.exe --version
C:\clara-system\.venv\Scripts\python.exe -m pip show uvicorn
```

If `uvicorn` is missing, reinstall the Python dependencies:

```powershell
cd C:\clara-system
C:\clara-system\.venv\Scripts\python.exe -m pip install -r ai-services\requirements.txt
```

----


### ML Model Evaluation (Jupyter)

```powershell
cd ai-services\ml_service
python -m jupyter notebook
```

### Open evaluate.ipynb and run all cells.
Outputs: confusion matrices (inline) + AUROC summary table.
Saves: confusion_matrices.png

----



