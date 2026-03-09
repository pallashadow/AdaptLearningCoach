# AGENTS.md (Lean)

## Mission
Build and maintain an AI learning-diagnosis loop:
1) derive concepts from goal
2) pick weakest concept
3) ask question
4) score + feedback
5) update familiarity/history
6) repeat until `max_round`

## Read First (minimal context)
- `main.py` (API route orchestration)
- `lib/api/schemas.py` (request/response contracts)
- `lib/agentic/config.py` (state schema)
- `lib/agentic/nodes/entry_node.py`
- `lib/agentic/nodes/question_node.py`
- `lib/agentic/nodes/ref_node.py`

Do NOT scan the whole repo unless needed.

## Core State Contract
- `concepts: list[str]`
- `qa_history: dict[concept, list[qa]]`
- `familiarity: dict[concept, 0-100]`
- `current_round: int`
- `max_round: int`

Any change must keep these fields consistent.

## Node Responsibilities
- `entry_llm_node`: goal -> initial concepts + familiarity
- `question_node`: choose low-familiarity concept -> one diagnostic question
- `ref_node`: evaluate answer -> score/feedback + update history/familiarity
- `auto_answer_node`: simulation only (non-production)

## Change Rules
- Prefer minimal diffs.
- Preserve API schema compatibility unless explicitly requested.
- If schema changes, update both `schemas.py` and route handlers.
- Add/adjust tests for behavior changes.
- Avoid refactors unrelated to user request.

## Output Style for Agent
- First: concrete result
- Then: changed files + why
- Keep responses concise; avoid repeating project background.

## Python Execution
- Always run Python and pip commands from `.venv`:
  - `.\.venv\Scripts\python.exe ...`
  - `.\.venv\Scripts\python.exe -m pip ...`
- Do not use system `python` unless explicitly requested.
