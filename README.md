# Good AI Advisor

An AI-powered travel-insurance advisor that answers policy questions using
retrieved policy evidence, a controlled LLM workflow, and response-safety
checks. It is a portfolio project focused on building a reliable RAG-backed
assistant rather than a generic chat interface.

> This is a technical demonstration, not a source of insurance advice.

## Highlights

- Grounds answers in indexed travel-insurance policy documents.
- Combines semantic retrieval, lexical search, reciprocal-rank fusion, and a
  cross-encoder reranker.
- Uses a controlled execution flow: safety classification, task planning,
  deterministic routing, context assembly, and answer validation.
- Stores policies, conversations, messages, source references, and AI-run
  metadata in PostgreSQL with pgvector.
- Provides a FastAPI API and a small React + TypeScript client.

## Architecture

<img width="1536" height="1024" alt="Good AI Advisor ERD" src="https://github.com/user-attachments/assets/37e5dd9c-b6b9-4778-9c85-8be8970846b9" />

# Runtime Flow

```text
                           USER QUESTION
                                │
                                ▼
                           ChatService
                                │
                                ▼
                        Runtime execution
                                │
                                ▼
                     STRUCTURED TaskResult[]
                       ┌────────┴─────────┐
                       │                  │
                       ▼                  ▼
               PolicyTaskContent   RetrievalTaskContent
                       │                  │
                       └────────┬─────────┘
                                │
                ┌───────────────┴────────────────┐
                │                                │
                ▼                                ▼
         ContextBuilder                 GroundingFactBuilder
                │                                │
                ▼                                ▼
      LLM-friendly context               GroundingFact[]
                │                                │
                ▼                                │
             Model A                             │
            Generator                            │
                │                                │
                ▼                                │
          Draft Answer ──────────────────────────┘
                                │
                                ▼
                       ResponseValidator
                                │
               ┌────────────────┴────────────────┐
               │                                 │
               ▼                                 ▼
       Deterministic Guards              GroundingValidator
              Python                         Model B
               │                                 │
               │                          claim ↔ evidence
               │                                 │
               └────────────────┬────────────────┘
                                ▼
                     ValidationDecisionPolicy
                                │
                ┌───────────────┼────────────────┐
                │               │                │
                ▼               ▼                ▼
               OK          REGENERATE         HANDOFF
                                │
                                ▼
                         maximum one retry
```

The key property of this runtime is that **Model A and Model B are derived from the same trusted structured `TaskResult[]`**.

`ContextBuilder` changes representation for generation.

`GroundingFactBuilder` changes representation for validation.

Neither component re-queries the database or reconstructs data from generated natural language.

---




```text
React client
    |
    v
FastAPI API -> Chat service -> safety gate -> task planner/router
                                            |             |
                                            |             +-> policy data
                                            +-> RAG retrieval pipeline
                                                    |
                                                    v
                                           validated LLM response

PostgreSQL + pgvector <---- policies, conversations, document chunks
```

The full design notes are available in
[runtime flow](server/docs/architecture/ai_insurance_advisor_runtime_flow.md),
[retrieval pipeline](server/docs/retrieval-pipeline.md), and
[response validation](server/docs/architecture/response-validator-architecture-current.md).

## Tech Stack

- **Backend:** Python, FastAPI, SQLAlchemy, Alembic
- **AI/RAG:** Groq, Sentence Transformers, pgvector, PostgreSQL full-text and
  lexical search
- **Frontend:** React, TypeScript, Vite
- **Testing:** pytest
- **Local infrastructure:** Docker Compose and PostgreSQL 16 + pgvector

## Repository Layout

```text
good-ai-advisor/
├── server/
│   ├── app/                 # API, domain models, services, repositories
│   ├── data/                # Evaluation fixtures and source policy material
│   ├── docs/                # Architecture and retrieval design notes
│   ├── migrations/          # Alembic database migrations
│   ├── scripts/             # Ingestion, seeding, and evaluation utilities
│   ├── tests/               # Backend unit tests
│   ├── requirements.txt     # Runtime dependencies
│   └── requirements-dev.txt # Test dependencies
├── ui/                      # React client
├── docker-compose.yml       # Local PostgreSQL + pgvector
└── README.md
```

## Run Locally

### Prerequisites

- Python 3.11+
- Node.js 20+
- Docker Desktop
- A Groq API key

### 1. Start PostgreSQL

```powershell
docker compose up -d
```

### 2. Configure and run the API

```powershell
cd server
Copy-Item .env.example .env
# Add GROQ_API_KEY to .env
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
alembic upgrade head
python scripts/seed_dev.py
uvicorn app.main:app --reload
```

The API is available at `http://localhost:8000`; interactive API docs are at
`http://localhost:8000/docs`.

### 3. Run the client

In a second terminal:

```powershell
cd ui
Copy-Item .env.example .env
npm install
npm run dev
```

Open `http://localhost:5173`.

## Test

With the backend virtual environment activated:

```powershell
cd server
pytest tests
```

## Notes

- The included policy document and derived chunks are sample development data.
- Model weights and runtime caches are intentionally excluded from Git.
- The first run may download embedding and reranking models.
- Authentication is intentionally not implemented yet; the request schema marks
  user identity as a temporary development concern.

## Next Improvements

- Add authentication and associate UI requests with the authenticated user.
- Add API integration tests with an isolated PostgreSQL database.
- Add CI for backend tests, UI linting, and the production build.
- Deploy a hosted demo and add a short walkthrough video or screenshots.
