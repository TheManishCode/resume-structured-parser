# AI Talent Platform

A production-ready, two-sided AI resume screening platform that matches candidates to roles using a tiered model-routing architecture — bias-aware, explainable, and built for compliance.

---

## What it does

**For Recruiters** — post jobs, automatically rank candidates by fit, and review AI-generated justifications with confidence scores.

**For Candidates** — upload a resume (PDF, DOCX, or ZIP batch), receive scored evaluations per role, and get actionable improvement tips.

**Under the hood** — every resume is scored through a three-tier model chain: a fast local model (Ollama) handles bulk first-pass screening, and cloud reasoning (ApeKey.ai / Claude / Groq) escalates only when the local model is uncertain or when a candidate reaches the top pool.

---

## Architecture

```
                        ┌──────────────┐
    Candidate  ──PDF──▶ │  Ingestion   │  pdfplumber + Tesseract OCR
                        │  Pipeline    │  → structured JSON + raw text
                        └──────┬───────┘
                               │
                        ┌──────▼───────┐
                        │  Model       │
                        │  Router      │◀── confidence threshold gate
                        └──┬───┬───┬──┘
                     Tier 0│   │1  │2
              Ollama (local)│   │   │ApeKey.ai / Claude / Groq
                            │   └───┘  (cloud escalation only)
                        ┌───▼──────────┐
                        │  Scores DB   │  disagreement flagging,
                        │  (Postgres)  │  audit log, re-score worker
                        └──────────────┘
                               │
                        ┌──────▼───────┐
               React UI │  FastAPI     │  JWT auth, CORS, rate limits,
                        │  REST API    │  security headers
                        └──────────────┘
```

### Model Routing Policy

| Tier | Provider | When used |
|------|----------|-----------|
| 0 | Ollama (local OSS) | Every resume — fast, free, deterministic |
| 1 | **ApeKey.ai** (primary) | When local confidence < 0.70 or candidate is in top-N pool |
| 1 | Claude (fallback primary) | When ApeKey.ai key is not set |
| 2 | Groq (Llama 3.3 70B) | When Tier 1 fails — result marked `provisional`, retry queued |

When local and cloud scores diverge by > 0.20, the result is flagged `needs_review: true` rather than silently averaged.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | FastAPI 0.111, Python 3.11, asyncio |
| **Database** | PostgreSQL 16, SQLAlchemy 2.x (async), Alembic |
| **Auth** | JWT (HS256), bcrypt, rate limiting via slowapi |
| **AI / LLMs** | ApeKey.ai, Anthropic Claude, Groq, Ollama |
| **PDF Parsing** | pdfplumber, Tesseract OCR, pdf2image |
| **Frontend** | React 18, Vite, Tailwind CSS, TanStack Query |
| **Infrastructure** | Docker Compose, PostgreSQL volumes |

---

## Quick Start

### Prerequisites

- Docker Desktop (running)
- Git

### 1. Clone & configure

```bash
git clone <repo-url>
cd ai-talent-platform
cp .env.example .env   # or edit .env directly
```

### 2. Set your API keys in `.env`

```env
# Primary cloud tier — ApeKey.ai unified AI gateway
APEKEY_AI_API_KEY=sk_live_your_key_here
APEKEY_AI_MODEL=gpt-4o          # or any model ApeKey routes

# Optional: Claude as alternative primary
ANTHROPIC_API_KEY=sk-ant-...

# Fallback tier (free tier available)
GROQ_API_KEY=gsk_...
```

### 3. Launch

```bash
docker compose up --build
```

| Service | URL |
|---------|-----|
| Frontend UI | http://localhost:5173 |
| API (FastAPI) | http://localhost:8000 |
| API Docs (Swagger) | http://localhost:8000/docs |
| API Docs (ReDoc) | http://localhost:8000/redoc |

---

## Running Locally (without Docker)

### Backend

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux

# 2. Install dependencies
pip install -r requirements.txt

# 3. Start Postgres (Docker only for DB)
docker run -d --name pg \
  -e POSTGRES_PASSWORD=rixs.cx_73 \
  -e POSTGRES_DB=talent_platform \
  -p 5432:5432 postgres:16-alpine

# 4. Run migrations
alembic upgrade head

# 5. Start API
uvicorn packages.api.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev          # → http://localhost:5173
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | (required) | PostgreSQL async DSN |
| `JWT_SECRET` | `change-me-in-production` | Token signing secret — **change for production** |
| `APEKEY_AI_API_KEY` | — | ApeKey.ai API key (primary cloud tier) |
| `APEKEY_AI_BASE_URL` | `https://api.apekey.ai/v1` | ApeKey.ai endpoint |
| `APEKEY_AI_MODEL` | `gpt-4o` | Model to use via ApeKey gateway |
| `ANTHROPIC_API_KEY` | — | Claude API key (used if ApeKey not set) |
| `GROQ_API_KEY` | — | Groq API key (fallback tier) |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Local Ollama instance |
| `OLLAMA_MODEL` | `llama3.2` | Local model name |
| `LOCAL_CONFIDENCE_THRESHOLD` | `0.70` | Below this → cloud escalation |
| `DISAGREEMENT_THRESHOLD` | `0.20` | Delta that triggers `needs_review` flag |
| `CLOUD_TIMEOUT_SECONDS` | `15` | Cloud tier timeout |
| `TOP_N_ESCALATE` | `20` | Always run cloud on top-N candidates |
| `CORS_ORIGINS` | `http://localhost:5173` | Allowed CORS origins (comma-separated) |

---

## API Reference

### Auth

| Method | Path | Body | Description |
|--------|------|------|-------------|
| `POST` | `/auth/register/recruiter` | `{email, password, org_name}` | Create recruiter account |
| `POST` | `/auth/register/candidate` | `{email, password}` | Create candidate account |
| `POST` | `/auth/login` | `{email, password, role}` | Returns JWT |

### Jobs (Recruiter)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/jobs` | Create a job posting |
| `GET` | `/jobs` | List all active jobs |
| `GET` | `/jobs/{id}` | Get job + ranked candidates |
| `GET` | `/jobs/{id}/rank?limit=20` | Ranked candidate list |
| `POST` | `/jobs/{id}/score` | Score a resume against this job |

### Resumes (Candidate)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/resumes/upload` | Upload PDF, DOCX, or ZIP batch |
| `GET` | `/resumes/me` | List own resumes |
| `GET` | `/resumes/{id}` | View a specific resume (recruiter) |

### Scores

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/scores/candidate/me` | Candidate's own scores + improvement tips |
| `GET` | `/scores/{id}` | Full score detail (recruiter) |

### Health

```
GET /health  →  {"status": "ok", "version": "0.2.0"}
```

Full interactive docs: **http://localhost:8000/docs**

---

## Key Features

### Bias Mitigation
- Bias-sensitive fields (name, university prestige tier, graduation year, gender markers) are stripped at ingest and never reach the scoring prompt.
- Scoring prompts explicitly instruct the model to ignore demographic proxies.

### Disagreement Detection
When the local model and cloud model scores diverge by more than `DISAGREEMENT_THRESHOLD` (default 0.20), the result is flagged `needs_review: true` with the `disagreement_delta` recorded — the system surfaces uncertainty rather than hiding it.

### DPDP Compliance (Data Minimisation)
Resumes auto-expire 6 months after upload (`expires_at` field). A background worker runs hourly to mark expired resumes, which are then excluded from all queries.

### Retry Architecture
When the primary cloud tier fails, Groq handles the request and marks the result `status: provisional`. A background retry worker later upgrades provisional results to `confirmed` or `re_scored` once the primary tier recovers.

### Audit Log
Every scoring event, model switch, and status change is written to an immutable `audit_log` table with ORM-level write protection.

### Security
- JWT authentication with role-based access control (recruiter / candidate)
- bcrypt password hashing (rounds=12)
- Rate limiting: 10/min register, 20/min login
- Security headers: `X-Content-Type-Options`, `X-Frame-Options`, `X-XSS-Protection`, `Referrer-Policy`, `Permissions-Policy`
- Per-org daily cloud call caps to prevent runaway costs

---

## Project Structure

```
ai-talent-platform/
├── packages/
│   ├── api/
│   │   ├── main.py               # FastAPI app + lifespan workers
│   │   ├── deps.py               # JWT auth dependency injection
│   │   └── routers/
│   │       ├── auth.py           # Register + login
│   │       ├── jobs.py           # Job CRUD + ranking
│   │       ├── resumes.py        # Upload + retrieval
│   │       ├── scores.py         # Score detail + candidate view
│   │       └── candidates.py     # Candidate profile
│   └── core/
│       ├── router/
│       │   ├── router.py         # ModelRouter — tiered scoring logic
│       │   └── adapters.py       # Ollama / ApeKey.ai / Claude / Groq adapters
│       ├── scoring/
│       │   ├── scoring.py        # Weighted scoring engine
│       │   ├── bias_audit.py     # Bias field detection
│       │   ├── disqualifiers.py  # Hard-fail rules
│       │   ├── reasoning.py      # Structured reasoning layer
│       │   └── schema.py         # Resume JSON schema
│       ├── ingestion/
│       │   └── pipeline.py       # PDF/DOCX parsing + OCR
│       ├── rag/
│       │   └── embedder.py       # Vector embedding utilities
│       └── db/
│           ├── models.py         # SQLAlchemy ORM models
│           └── session.py        # Async session factory
├── frontend/
│   └── src/
│       ├── pages/
│       │   ├── Login.jsx         # Auth flow (login + register)
│       │   ├── RecruiterDash.jsx # Job list + creation
│       │   ├── JobDetail.jsx     # Candidate ranking per job
│       │   └── CandidateDash.jsx # Resume upload + score view
│       └── api.js                # Axios client + API wrappers
├── tests/                        # pytest test suite (86 tests)
├── alembic/                      # Database migrations
├── docker-compose.yml
├── Dockerfile.api
└── .env
```

---

## Running Tests

```bash
# Install test dependencies
pip install -r requirements.txt

# Run the full suite
pytest

# Run a specific module
pytest tests/test_scoring.py -v

# Run CLI engine tests
pytest tests/cli/ -v
```

The test suite covers 86 tests across scoring, ingestion, auth, jobs, and the CLI engine.

---

## ApeKey.ai Integration

This platform integrates [ApeKey.ai](https://apekey.ai) as the **primary cloud scoring tier**. ApeKey provides a unified API gateway to multiple LLM providers through a single API key.

**How it works:**
1. Set `APEKEY_AI_API_KEY` in `.env`
2. The `ModelRouter` automatically selects ApeKey.ai as the primary cloud tier
3. Requests use the OpenAI-compatible `/v1/chat/completions` endpoint
4. Configure the target model with `APEKEY_AI_MODEL` (default: `gpt-4o`)

```python
# Automatically resolved by build_router()
from packages.core.router.adapters import ApeKeyAdapter

adapter = ApeKeyAdapter(
    api_key="sk_live_...",
    model="gpt-4o",           # or claude-3-5-sonnet, llama-3-70b, etc.
)
result = await adapter.score(resume_text, job_description)
# {"score": 0.87, "justification": "..."}
```

---

## License

MIT — see `LICENSE` for details.
