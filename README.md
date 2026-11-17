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

### 2. Configure Python and create the demo data

```powershell
cd server
Copy-Item .env.example .env
# Add GROQ_API_KEY to .env
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
alembic upgrade head
python -m scripts.seed_dev
```

Copy the printed `DEV_USER_ID` and `DEV_POLICY_ID` UUIDs into `server/.env`.
These identify the synthetic demo policy; the client does not send them.
They apply only when `ENVIRONMENT=development` and are not authentication.

The seed creates structured policy records and sample document metadata. It
does not create searchable VPP chunks or embeddings. From `server`, index the
included, prepared document and check the result:

```powershell
python -m scripts.validate_chunking
python -m scripts.ingest_vpp_cp_2021
python -m scripts.check_demo_setup
```

Validation uses the E5 tokenizer without loading model weights or calling an LLM.
Ingestion loads embedding weights, chunks the prepared JSON, embeds it and saves
it to PostgreSQL. The JSON is already derived from the PDF; this command does
not re-parse the PDF. Ingestion replaces existing chunks for this document in a
transaction, so use a separate demo database when testing a fresh setup.

The default target is `TRAVEL_INSURANCE` version `2026.1` created by the seed.
Use `--product-version-id <UUID>` to choose a different existing product version
explicitly. First-time model/tokenizer downloads require internet access; the
chat retrieval pipeline also downloads Czech Stanza resources on first use.

### 3. Start the API

From `server`, with the environment activated and demo IDs saved:

```powershell
uvicorn app.main:app --reload
```

The API is available at `http://localhost:8000`; interactive API docs are at
`http://localhost:8000/docs`.

### 4. Run the client

In a second terminal:

```powershell
cd ui
Copy-Item .env.example .env
npm install
npm run dev
```

Open `http://localhost:5173`.

Start a new conversation and try `Jaké povinnosti mám při pojistné události?`.
The assistant should use the indexed terms, or return its safe fallback when
it cannot validate an answer. Wording depends on the configured LLM. A working
old database is not proof of a reproducible setup: repeat the steps against an
empty demo database to verify migrations, seed and indexing together.

### Retrieval evaluation

From `server`:

```powershell
python -m scripts.run_retrieval_eval
python -m scripts.test_retrieval_latency
```

These scripts resolve `VPP_CP_2021` to exactly one READY document with embeddings
and pass its product version into retrieval. If the document is indexed under
multiple versions, supply `--product-version-id <UUID>`. Evaluation credits an
article only when it comes from the dataset's document. These are retrieval
metrics, not measurements of final-answer correctness.

## Test

For final-answer and validator evaluation (beyond retrieval article scores), see
[AI evaluation](server/docs/ai-evaluation.md). Start with the offline dataset
check: `python -m scripts.run_ai_eval --check` from `server`.

With the backend virtual environment activated:

```powershell
cd server
python -m pytest tests
```

The chunking regression tests use a lightweight token counter. For the full
included document with the actual E5 tokenizer, run `python -m scripts.validate_chunking`;
add `--local-files-only` to require cached tokenizer files. Neither check writes
to the database or calls an LLM. Additional existing AI service tests are in
`app/services/test/`; its PostgreSQL integration test requires seeded, indexed data.

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
