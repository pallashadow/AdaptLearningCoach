# Agentic Learning Coach

A small project that uses AI for **learning diagnosis**.  
It breaks down your learning goal, asks questions round by round, scores answers, gives feedback, and updates your mastery level over time.

## What This Project Does (Simple Version)

You provide a goal, for example:  
"I am preparing for an ML Algorithm Engineer interview."

Then the system automatically does this:

1. Build a concept list (the root of a soft knowledge graph)
2. Pick the concept you are least familiar with
3. Ask a diagnostic question and score your answer (0-100)
4. Save the Q&A into history and update familiarity
5. Continue to the next round until `max_round` is reached

In one sentence: this is a learning agent that continuously asks, evaluates, and tracks your understanding.

## Core Flow

- `entry_llm_node`: converts your learning goal into `knowledge_graph_root` (concepts + initial familiarity)
- `question_node`: selects a low-familiarity concept and generates one diagnostic question
- `ref_node`: evaluates the answer, returns feedback, and updates `qa_history` + `familiarity`
- `auto_answer_node` is also available in the notebook for auto-simulation

Key state fields maintained by the system:

- `concepts`: list of concepts
- `qa_history`: per-concept answer history and scores
- `familiarity`: mastery score (0-100)
- `current_round / max_round`: current round and total rounds

## File Structure

```text
agentic_learning/
├─ main.py                            # FastAPI entrypoint and route orchestration
├─ README.md
├─ requirements.txt
├─ frontend/                          # Optional web UI
│  └─ src/
├─ lib/
│  ├─ api/
│  │  ├─ schemas.py                   # Request/Response models
│  │  └─ dialog_store.py              # Firestore dialog storage
│  ├─ agentic/
│  │  ├─ config.py                    # Typed state definitions
│  │  ├─ graph.py
│  │  ├─ nodes/
│  │  │  ├─ entry_node.py             # Build initial concept graph
│  │  │  ├─ question_node.py          # Generate next diagnostic question
│  │  │  ├─ ref_node.py               # Evaluate answer and update familiarity
│  │  │  └─ auto_answer_node.py       # Auto-answer simulation
│  │  ├─ prompt_build/
│  │  └─ tools/
│  └─ llm/
│     └─ litellm_api.py               # LLM/tool-call wrapper
└─ playground/
   └─ pg1.ipynb
```

## API Quick Start

### 1) Install dependencies

```bash
pip install -r requirements.txt
```

### 2) Configure environment variables

Set at least one model key (for example, OpenAI):

```bash
# Windows PowerShell example
$env:OPENAI_API_KEY="your_key"
```

Optional: if you also configure a Gemini key, the project can fall back between models.

### 3) Start the service

```bash
uvicorn main:app --reload --port 8001
```

Default URL: `http://127.0.0.1:8001`

### 4) Call the API

#### Health check

```bash
curl http://127.0.0.1:8001/health
```

#### Start a learning dialog

```bash
curl -X POST "http://127.0.0.1:8001/dialogs/start" \
  -H "Content-Type: application/json" \
  -d "{\"question\":\"I am preparing for an ML Algorithm Engineer interview.\",\"max_round\":5,\"question_mode\":\"choice\"}"
```

`question_mode` supports:

- `choice` (default): multiple-choice questions, answer with `A/B/C/D`
- `open`: free-form text answers

Response includes:

- `dialog_id`: unique ID for this dialog
- `current_question`: first diagnostic question
- `knowledge_graph_root`: generated concept structure

#### Submit an answer

```bash
curl -X POST "http://127.0.0.1:8001/dialogs/answer" \
  -H "Content-Type: application/json" \
  -d "{\"dialog_id\":\"<your_dialog_id>\",\"user_answer\":\"your answer\"}"
```

Response includes:

- `current_score`: score for this round
- `current_feedback`: short feedback
- `last_ground_truth`: reference answer
- `finished`: whether the dialog is complete

## Storage

- Firestore is required for dialog state persistence
  - `GOOGLE_APPLICATION_CREDENTIALS`: path to service account JSON
  - `FIRESTORE_PROJECT_ID` (optional): overrides GCP project id auto-detection
  - `FIRESTORE_COLLECTION` (optional, default `agentic_dialogs`)

## Notebook Demo

`playground/pg1.ipynb` shows the full loop (including auto-answer simulation), which is useful for understanding how state updates each round.

## Current Development Status

Based on `docs/PROPOSAL.md`, the basic loop is done (build graph, ask, score, update).  
Next steps include better sampling strategy, branch learning, completion criteria, points system, and more tests.

## Frontend Deployment to GitHub Pages

The repository includes a GitHub Actions workflow at `.github/workflows/frontend-to-github-pages.yml`.

- Trigger: push to `main`/`master` when files under `frontend/**` change, or manual run
- Build: runs `npm ci` and `npm run build` in `frontend/`
- Deploy: publishes `frontend/dist` to GitHub Pages
- Base path: automatically sets `VITE_BASE_PATH` to:
  - `/` for `<owner>.github.io` repositories
  - `/<repo-name>/` for project pages repositories

One-time GitHub setup:

1. Go to **Settings -> Pages**
2. Set **Source** to **GitHub Actions**
3. Push to `main` (or run the workflow manually) to publish





