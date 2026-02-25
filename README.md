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
uvicorn main:app --reload
```

Default URL: `http://127.0.0.1:8000`

### 4) Call the API

#### Health check

```bash
curl http://127.0.0.1:8000/health
```

#### Start a learning dialog

```bash
curl -X POST "http://127.0.0.1:8000/dialogs/start" \
  -H "Content-Type: application/json" \
  -d "{\"question\":\"I am preparing for an ML Algorithm Engineer interview.\",\"max_round\":5}"
```

Response includes:

- `dialog_id`: unique ID for this dialog
- `current_question`: first diagnostic question
- `knowledge_graph_root`: generated concept structure

#### Submit an answer

```bash
curl -X POST "http://127.0.0.1:8000/dialogs/answer" \
  -H "Content-Type: application/json" \
  -d "{\"dialog_id\":\"<your_dialog_id>\",\"user_answer\":\"your answer\"}"
```

Response includes:

- `current_score`: score for this round
- `current_feedback`: short feedback
- `last_ground_truth`: reference answer
- `finished`: whether the dialog is complete

## Storage

- Default: in-memory storage (dialogs are lost after restart)
- Optional: set `REDIS_URL` to persist dialog state in Redis

## Notebook Demo

`playground/pg1.ipynb` shows the full loop (including auto-answer simulation), which is useful for understanding how state updates each round.

## Current Development Status

Based on `PROPOSAL.md`, the basic loop is done (build graph, ask, score, update).  
Next steps include better sampling strategy, branch learning, completion criteria, points system, and more tests.

