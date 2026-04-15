# CLARA - Clinical LLM-Assisted Reasoning Assistant

A production-ready scaffold for a hybrid AI-powered clinical decision support system.

## Architecture Overview

CLARA implements a three-layer AI approach:

1. **LLM Layer**: Natural language processing and explanation generation
2. **Machine Learning Layer**: Structured prediction models for diagnosis
3. **Rule-Based Layer**: Clinical safety logic and emergency detection

## System Architecture

```
Frontend (React/TypeScript)
    ↓ HTTP
Backend (ASP.NET Core Web API)
    ↓ gRPC/HTTP
AI Services (Python/FastAPI)
    ↓
ML Models & Rule Engine
```

## Project Structure

```
clara-system/
├── backend/                 # ASP.NET Core Web API
│   ├── Controllers/         # API endpoints
│   ├── Application/         # Business logic & DTOs
│   ├── Domain/             # Domain entities
│   └── Infrastructure/     # External services
├── ai-services/            # Python ML & LLM services
│   ├── ml_service/         # FastAPI ML prediction service
│   ├── llm_service/        # LLM client placeholder
│   └── rule_engine/        # Clinical rules
├── frontend/               # React TypeScript dashboard
│   ├── src/
│   │   ├── components/     # UI components
│   │   ├── pages/         # Dashboard pages
│   │   └── services/      # API client
└── docs/                  # Documentation
```

## Getting Started

### Prerequisites

- .NET 8.0 SDK
- Node.js 18+
- Python 3.9+
- Docker (optional)

### Backend Setup

```bash
cd backend
dotnet restore
dotnet run
```

### AI Services Setup

```bash
cd ai-services
pip install -r requirements.txt
# Start ML service
cd ml_service
python app.py
```

### Frontend Setup

```bash
cd frontend
npm install
npm start
```

## API Endpoints

- `POST /api/chat` - Send chat message with patient data
- `POST /api/predict` - Get ML prediction
- `POST /api/rules/evaluate` - Evaluate clinical rules

## Development Notes

- All AI components are currently placeholders with mock responses
- TODO comments indicate where actual AI integration should occur
- System includes comprehensive validation and error handling
- Medical safety notes are included in all responses

## Safety & Compliance

This system is designed for clinical decision support only and does not replace licensed medical professionals. All responses include appropriate safety disclaimers.

## Future Integration Points

1. **LLM Service**: Integrate with OpenAI, Azure OpenAI, or local LLMs
2. **ML Models**: Train and deploy actual medical prediction models
3. **Database**: Add patient data persistence
4. **Authentication**: Implement HIPAA-compliant user management
5. **Monitoring**: Add logging and performance monitoring

## Contributing

This is a scaffold for thesis/research purposes. Ensure all medical implementations follow ethical guidelines and regulatory requirements.