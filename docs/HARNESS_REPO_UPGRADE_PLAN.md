# Harness-Driven Repo Upgrade Plan

Date: 2026-03-10  
Scope: `agentic_learning`  
Reference: `docs/HARNESS_ENGINEERING.md`

## 1) Goal

将本仓库从“能跑”升级为“对 agent 可读、可执行、可自校正”的工程系统。  
优先级遵循：先硬约束（contract/CI/observability），再结构化（docs/architecture），最后持续治理（drift cleanup）。

## 2) Principles

1. Repo is system of record：关键知识必须写进仓库，而不是口头约定。  
2. Guardrails over heroics：用校验、测试、CI 防止回归，而不是靠人工记忆。  
3. Minimal diffs：每次只修一个根因，并附最小回归测试。  
4. Agent legibility first：结构稳定、命名清晰、日志可检索。  

## 3) Current Gaps (as of 2026-03-10)

1. CI 偏前端：目前仅有前端 GitHub Pages workflow，后端缺少默认质量门禁。  
2. 问题契约校验入口在 `main.py`，复用性和可测试性可继续提升。  
3. `/dialogs/start` 的契约回归测试已有覆盖，但 `/dialogs/answer` 的无效契约失败路径覆盖不足。  
4. 日志目录已统一到 `logs/`，但结构化字段化（`dialog_id`、字段值）还可加强。  
5. 文档已较多，但缺少统一“升级执行视图”。

## 4) Upgrade Roadmap

### P0 (1-2 weeks): Hard Guardrails

目标：阻断 contract drift，提升故障可定位性。

1. Backend CI baseline
- Add workflow for backend checks:
  - `.venv` Python test run (targeted tests first)
  - optional lint/type checks (incremental)
- Minimum gate: question flow contract tests must pass before merge.

2. Contract validation centralization
- Extract choice-question contract validation from `main.py` to `lib/api/contract_validation.py`.
- Reuse same validator in both `/dialogs/start` and `/dialogs/answer`.
- Error contract remains explicit: `INVALID_CHOICE_QUESTION: ...`.

3. Regression tests for both start/answer paths
- Keep existing `/dialogs/start` valid/invalid tests.
- Add `/dialogs/answer` invalid contract test (when next question generation returns invalid choice payload, API must fail explicitly).

4. Structured logging for triage
- For start/answer failures, log fields should include at least:
  - `dialog_id`
  - `question_mode`
  - `current_question_type`
  - `choice_option_count`
  - `current_correct_option`
  - error message

### P1 (2-4 weeks): Architecture + Docs Legibility

目标：把“约定”升级为“可检验不变量”。

1. State contract clarification
- Reconcile AGENTS core contract with actual state representation (`knowledge_graph_root` + per-concept history).
- Document canonical mapping (legacy compatible).

2. Cross-layer contract checks
- Add a small contract consistency check for:
  - `frontend/src/types.ts`
  - `frontend/src/api/dialogApi.ts`
  - `lib/api/schemas.py`
  - `main.py`

3. Docs indexing
- Add a concise docs index (`docs/README.md`) with:
  - architecture
  - API contracts
  - local dev runbook
  - troubleshooting
  - upgrade plan

### P2 (continuous): Entropy Management

目标：持续减少漂移与“坏模式复制”。

1. Weekly docs/link freshness check.  
2. Drift scanner for key anti-patterns:
- missing `dialog_id` in error logs
- contract validation bypass
- schema mismatch risk hotspots
3. Small automated cleanup PRs (single-root-cause policy).

## 5) Execution Rules

1. No behavior change without at least one regression test.  
2. For question flow changes, always verify:
- `/dialogs/start` returns renderable choice contract in `choice` mode
- invalid contract returns explicit API error (no fake fallback options)
3. Local Dev restart command (term standardization):
- `powershell -ExecutionPolicy Bypass -File .\scripts\restart-dev.ps1`
4. Python commands must use `.venv`:
- `.\.venv\Scripts\python.exe ...`
- `.\.venv\Scripts\python.exe -m pip ...`

## 6) Definition of Done (DoD)

### P0 DoD
- Backend CI workflow exists and is required for merges.  
- Choice contract validator is shared and unit-tested/integration-tested.  
- `/dialogs/start` + `/dialogs/answer` contract regression tests pass.  
- Error logs include `dialog_id` and contract-relevant fields.  

### P1 DoD
- Canonical state contract doc published with mapping examples.  
- Cross-layer contract consistency check in CI.  
- `docs/README.md` available and linked from top-level docs.  

### P2 DoD
- Weekly drift checks running.  
- At least one automated cleanup loop established.  

## 7) Suggested First PR Batch

1. PR-1: backend CI baseline + targeted tests.  
2. PR-2: extract contract validator + wire to start/answer.  
3. PR-3: add `/dialogs/answer` invalid-contract regression test.  
4. PR-4: structured error logging fields for start/answer.

