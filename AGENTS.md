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

## Python Execution (Strict)
- Always run Python and pip commands from `.venv`:
  - `\.venv\Scripts\python.exe ...`
  - `\.venv\Scripts\python.exe -m pip ...`
- Never run bare `python` / `pip` / `py`.
- Before first Python command in a turn, verify `.venv` exists.
- If `.venv` is missing or broken, stop and report; do not silently fall back to system Python.
- If this rule is violated in any step, stop immediately and rerun the command with `.venv`.

## Shell Script Execution (Windows)
- Execute `.sh` scripts with Git Bash, not PowerShell.
- Example (from PowerShell): `& 'D:\Program\Git\bin\bash.exe' -lc 'cd /d/PROJECT/agentic_learning && ./scripts/smoke_api.sh'`

## Failure Analysis (Mandatory)
Recent failures came from process gaps, not one-off typos:
- Contract drift between frontend and backend (`question_mode`, `choice_option_count`, options rendering).
- Missing preflight validation for generated choice questions (bad payload reached UI).
- Behavior changes shipped without a matching regression test.
- Logs were hard to correlate to one dialog (`dialog_id`) during triage.

Treat these as process defects. Fix code and process together.

## Contract Guardrails (Mandatory)
For any change touching question generation/evaluation:
- Keep request/response/state keys aligned across:
  `frontend/src/types.ts` -> `frontend/src/api/dialogApi.ts` -> `lib/api/schemas.py` -> `main.py` -> nodes.
- Add server-side validation before returning choice questions:
  - `current_question_type == "choice"`
  - `len(current_options) == choice_option_count`
  - `choice_option_count in [2,3,4]`
  - `current_correct_option` must be a valid label for the option count.
- On validation failure: return explicit API error (do not send fallback fake options to UI).

## Test Policy (No Exception)
- No behavior change without at least one regression test.
- Minimum test for this project when touching question flow:
  - `/dialogs/start` in `choice` mode returns a renderable question contract.
  - if contract invalid, API fails with explicit error.
- Prefer small deterministic tests over broad refactors.

## Dev Loop (Fast, Repeatable)
Use this exact loop to reduce debugging cost:
1) Restart both services with one command:
   `powershell -ExecutionPolicy Bypass -File .\scripts\restart-dev.ps1`
2) Run quick checks:
   - `frontend`: `npm run typecheck`
   - `backend`: targeted tests only
3) Run one smoke API case for `/dialogs/start` and verify contract.
4) If failed, fix one root cause only, then repeat from step 1.

## Logging Requirements
- Include `dialog_id` in error logs for start/answer paths.
- Log contract-validation failures with offending fields (option count, labels, question type).
- Avoid silent fallback behavior that masks errors.
