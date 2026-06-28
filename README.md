# Engineering Service Desk Chatbot

A REST API chatbot backend that collects engineering requests through a guided conversation, detects duplicates without storing personal data, and persists results in MongoDB.

Built with **FastAPI**, **LangGraph**, **MongoDB**, and **OpenAI / Azure OpenAI**.

---

## Table of Contents

1. [How It Works](#how-it-works)
2. [Project Structure](#project-structure)
3. [Quick Start](#quick-start)
4. [Using the API](#using-the-api)
5. [Configuration](#configuration)
6. [Running Tests](#running-tests)
7. [LLM Providers](#llm-providers)
8. [Privacy & Duplicate Detection](#privacy--duplicate-detection)
9. [Design Decisions](#design-decisions)

---

## How It Works

The chatbot guides a user through a fixed conversation to collect an engineering request. There is no free-form chat — each message advances a step in the workflow.

```
User says anything
        │
        ▼
┌─────────────────────────────┐
│  Collect request details    │  ← asks for: request type, environment, justification
└─────────────────────────────┘
        │ all collected
        ▼
┌─────────────────────────────┐
│  Collect identity details   │  ← asks for: full name, employee ID (stored redacted)
└─────────────────────────────┘
        │ all collected
        ▼
┌─────────────────────────────┐
│  Duplicate check            │  ← HMAC hash lookup — no raw identity ever stored
└─────────────────────────────┘
     │                  │
  duplicate          no duplicate
     │                  │
     ▼                  ▼
 Ask user:          Save request
 update or new?     → session closed
```

**The LLM is used for:**
- Extracting structured data from natural language ("I need access to prod" → `request_type: access-grant`)
- Phrasing assistant responses warmly
- Detecting off-topic messages

**The LLM is NOT used for:**
- Deciding what step comes next
- Validating values
- Storing or retrieving data

The backend controls all of that. The LLM only handles language.

---

## Project Structure

```
.
├── app/
│   ├── api/
│   │   ├── routes.py          # FastAPI endpoints
│   │   └── schemas.py         # Request/response Pydantic models
│   ├── core/
│   │   ├── config.py          # Settings (env vars) + PromptConfig (YAML)
│   │   ├── errors.py          # Custom exceptions
│   │   └── security.py        # HMAC duplicate key generation
│   ├── db/
│   │   └── mongo.py           # MongoDB connection + in-memory test collection
│   ├── graph/
│   │   ├── nodes.py           # Each step of the conversation as a function
│   │   ├── state.py           # LangGraph state schema
│   │   └── workflow.py        # Wires nodes into a LangGraph graph
│   ├── models/
│   │   ├── session.py         # Session status and step enums
│   │   └── request.py         # Request status enum
│   ├── services/
│   │   ├── container.py       # Dependency injection (holds all services)
│   │   ├── duplicate_service.py
│   │   ├── llm_service.py     # FakeLLMClient, OpenAILLMClient, AzureOpenAILLMClient
│   │   ├── request_service.py
│   │   ├── session_service.py
│   │   └── validators.py      # Validates LLM output — authoritative
│   └── main.py                # FastAPI app entry point
│
├── config/
│   └── prompts.yaml           # All prompts, allowed values, required fields
│
├── tests/
│   ├── conftest.py            # Shared fixtures (in-memory DB, test client)
│   ├── e2e/
│   │   └── test_chat_flow.py  # Full conversation tests
│   └── unit/
│       ├── test_duplicate_service.py
│       ├── test_security.py
│       ├── test_session_transitions.py
│       └── test_validation.py
│
├── .env.template               # Template — copy to .env and fill in values
├── docker-compose.yml         # Starts the app + MongoDB together
├── Dockerfile
├── build.sh                   # One-command build + test + Docker image
└── requirements.txt
```

**Key relationships:**
- `routes.py` receives HTTP requests → calls `container.workflow.run()`
- `workflow.py` runs the LangGraph graph → calls nodes in `nodes.py`
- `nodes.py` calls `llm_service`, `session_service`, `validators`, `duplicate_service`
- `config/prompts.yaml` controls what the LLM is asked and what values are allowed

---

## Quick Start

### Option A — Docker Compose (recommended)

No Python setup needed. Just Docker.

```bash
# 1. Clone and enter the project
cd ai_bot_assessment

# 2. Copy the env template
cp .env.template .env

# 3. Start the app and MongoDB
docker compose up --build
```

The API is now running at **http://localhost:8001**
Swagger UI (interactive docs) at **http://localhost:8001/docs**

> The default provider is `azure`. Fill in the Azure credentials in `.env` before starting — see [LLM Providers](#llm-providers).
> Use `LLM_PROVIDER=fake` only if you want to run without an API key (the test suite always uses `fake` regardless).

---

### Option B — Run locally (without Docker)

Requires Python 3.12+ and a running MongoDB instance.

```bash
# 1. Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set required environment variables
export LLM_PROVIDER=fake
export MONGO_URI=mongodb://localhost:27017
export DUPLICATE_SECRET=local-dev-secret

# 4. Start the server
uvicorn app.main:app --reload
```

The API is now running at **http://localhost:8000**

---

## Using the API

The easiest way to try the API is through **Swagger UI** at `/docs`.

### Step 1 — Create a session

Every conversation starts by creating a session. Do this once.

```
POST /sessions
```

Response:
```json
{
  "session_id": "3f2a1b4c-...",
  "status": "active"
}
```

Copy the `session_id`. You will paste it into the URL for every chat message.

---

### Step 2 — Send messages

```
POST /chat/{session_id}
```

Body (just the message — session ID stays in the URL):
```json
{
  "message": "your message here"
}
```

Response:
```json
{
  "session_id": "3f2a1b4c-...",
  "assistant_response": "...",
  "status": "active",
  "current_step": "collect_request_details"
}
```

---

### Full example conversation (curl)

Replace `SESSION_ID` with the value from Step 1.

```bash
# Step 1 — create session
curl -s -X POST http://localhost:8001/sessions

# Step 2 — start the conversation
curl -s -X POST http://localhost:8001/chat/SESSION_ID \
  -H "Content-Type: application/json" \
  -d '{"message": "hi"}'
# → "Hello! I'm the Engineering Service Desk assistant..."

# Step 3 — provide request type
curl -s -X POST http://localhost:8001/chat/SESSION_ID \
  -H "Content-Type: application/json" \
  -d '{"message": "access-grant"}'
# → "Which target environment is this for?"

# Step 4 — provide environment
curl -s -X POST http://localhost:8001/chat/SESSION_ID \
  -H "Content-Type: application/json" \
  -d '{"message": "production"}'
# → "What is the business justification?"

# Step 5 — provide justification
curl -s -X POST http://localhost:8001/chat/SESSION_ID \
  -H "Content-Type: application/json" \
  -d '{"message": "urgent incident support"}'
# → "What is your full name?"

# Step 6 — provide name (stored redacted)
curl -s -X POST http://localhost:8001/chat/SESSION_ID \
  -H "Content-Type: application/json" \
  -d '{"message": "My name is Jane Smith"}'
# → "Please provide your employee ID (letters and numbers only)"

# Step 7 — provide employee ID (stored redacted)
curl -s -X POST http://localhost:8001/chat/SESSION_ID \
  -H "Content-Type: application/json" \
  -d '{"message": "EMP456"}'
# → "Your engineering request has been submitted successfully. Thank you!"
```

You can send all request details in one message too:
```bash
curl -s -X POST http://localhost:8001/chat/SESSION_ID \
  -H "Content-Type: application/json" \
  -d '{"message": "I need access-grant to production for urgent incident support"}'
# → skips straight to asking for your name
```

---

### Valid values

| Field | Allowed values |
|---|---|
| `request_type` | `access-grant`, `infrastructure-provisioning`, `service-deployment`, `pipeline-change`, `incident-fix` |
| `target_environment` | `development`, `staging`, `production` |
| `employee_id` | Letters and numbers only, no spaces (e.g. `EMP123`, `AB99`) |

These are defined in `config/prompts.yaml` and can be changed without touching code.

---

### Other endpoints

**Check session state (sanitized — no personal data)**
```bash
curl -s http://localhost:8001/sessions/SESSION_ID
```

**Health check**
```bash
curl -s http://localhost:8001/health
# → {"status": "ok", "database": "ok", "app": "Engineering Service Desk Chatbot"}
```

---

## Configuration

Copy `.env.template` to `.env` and fill in the values you need.

```bash
cp .env.template .env
```

| Variable | Description | Default |
|---|---|---|
| `LLM_PROVIDER` | `fake`, `openai`, or `azure` | `fake` |
| `MONGO_URI` | MongoDB connection string | `mongodb://localhost:27017` |
| `MONGO_DATABASE` | Database name | `engineering_service_desk` |
| `DUPLICATE_SECRET` | Secret for HMAC hashing — change this in production | — |
| `OPENAI_API_KEY` | Required when `LLM_PROVIDER=openai` | — |
| `OPENAI_MODEL` | OpenAI model name | `gpt-4o-mini` |
| `AZURE_OPENAI_API_KEY` | Required when `LLM_PROVIDER=azure` | — |
| `AZURE_OPENAI_ENDPOINT` | Your Azure resource URL | — |
| `AZURE_OPENAI_DEPLOYMENT` | Deployment name in Azure portal | `gpt-4o-mini` |
| `AZURE_OPENAI_API_VERSION` | Azure API version | `2024-12-01-preview` |

**To change prompts or allowed values**, edit `config/prompts.yaml`. No code changes needed.

---

## Running Tests

Tests use an in-memory database and `FakeLLMClient` — no MongoDB or API key required.

```bash
source .venv/bin/activate
python -m pytest
```

Expected output:
```
11 passed, 1 warning in 0.08s
```

**Test coverage:**
- `test_validation.py` — request and identity field validation
- `test_security.py` — HMAC duplicate key generation and normalization
- `test_duplicate_service.py` — duplicate detection logic
- `test_session_transitions.py` — conversation step progression
- `test_chat_flow.py` (E2E) — full conversation including duplicate detection

---

## LLM Providers

### fake (default — no API key needed)

Uses regex-based extraction. Good for local development and all tests.

```env
LLM_PROVIDER=fake
```

### openai

```env
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
```

### azure (Azure OpenAI)

```env
LLM_PROVIDER=azure
AZURE_OPENAI_API_KEY=your-key
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT=your-deployment-name
AZURE_OPENAI_API_VERSION=2024-12-01-preview
```

Find your deployment name in the Azure portal under your OpenAI resource → **Model deployments**.

After updating `.env`, restart Docker Compose:
```bash
docker compose down && docker compose up --build
```

---

## Privacy & Duplicate Detection

**Personal data (name + employee ID) is never stored in plain text.**

When identity details are collected:
1. The raw name and employee ID are used only in memory during that request
2. An HMAC-SHA256 hash is computed: `HMAC(secret, "jane smith:emp456")`
3. Only the hash is stored — the original values are discarded
4. User messages sent during the identity step are stored as `[redacted user message]`

**Duplicate detection** works by computing the same hash for each new request and looking it up in MongoDB. If found, the user is asked:

```
A possible existing request was found. Do you want to update the existing request instead of creating a new one?
```

No names, IDs, or request details are mentioned. The user answers `yes` or `no`.

---

## Design Decisions

**Why LangGraph?**
The conversation is stateful and step-based. LangGraph makes each step an explicit node with clear inputs and outputs, rather than hiding state transitions in conditional route handler logic.

**Why is the LLM not trusted for decisions?**
LLM output is not deterministic. All allowed values, required fields, state transitions, and persistence are enforced by the application code. The LLM only handles natural language — it does not decide what happens next.

**Why MongoDB?**
Session state and request data are document-shaped and may evolve as prompts change. Storing `request_data` as a flexible document (with `prompt_version`) means old records remain queryable even after the prompt schema changes.

**Why HMAC for duplicate detection?**
A cryptographic hash is deterministic (same input = same hash) but irreversible. Two requests from the same person will produce the same hash, enabling duplicate detection, without ever storing the person's identity.

**Why is `session_id` in the URL, not the request body?**
It follows REST conventions — the resource being acted on belongs in the URL. In a real client application, the session ID would be stored once (e.g. in localStorage) and attached automatically. In Swagger, it means you only type the ID once in the URL field, then just type the message body each time.
