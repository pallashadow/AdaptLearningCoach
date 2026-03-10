# Frontend Modernization Plan (Priority + Execution)

## Goal
Upgrade `frontend/` to a maintainable team-ready stack:
- Runtime: Node.js LTS (22 preferred, 20 acceptable)
- UI: React + TypeScript + Vite
- Data/Form: TanStack Query + react-hook-form + zod
- Quality: ESLint + Prettier + Vitest + Playwright + Husky/lint-staged

## Priority

### P0 (Do Now)
1. Lock runtime and scripts
- Add Node version hint (`.nvmrc`) and `engines` in `package.json`.
- Standardize scripts for dev/build/lint/format/test/e2e.

2. Migrate UI shell to React + TypeScript
- Replace string-template DOM rendering with component-based React app.
- Keep current learning dialog features and backend interaction behavior.

3. Add core developer quality checks
- ESLint + Prettier baseline config.
- Vitest unit test baseline.

4. Add API state and form validation foundations
- Use TanStack Query for async state/mutations.
- Use react-hook-form + zod for start/answer form validation.

### P1 (Do Next)
1. Add Playwright smoke E2E and CI-friendly command
- Verify app boot and essential UI visibility.

2. Add pre-commit guardrails
- Husky + lint-staged for staged-file lint/format before commit.

3. Improve module boundaries
- Split `api/`, `components/`, `utils/`, `types/` with lightweight tests.

### P2 (Enhance)
1. Add component-level tests (React Testing Library)
2. Add typed API client generation (from OpenAPI schema)
3. Add Storybook for UI states
4. Add CI matrix for Node 20/22

## Execution Scope for This Change
This implementation executes P0 fully and P1 baseline:
- React migration complete
- TanStack Query + form validation wired
- ESLint/Prettier/Vitest/Playwright configured
- Husky/lint-staged configured
- User identity field (`user_id`) and reset-state action wired with backend API (`POST /users/{user_id}/reset`)

## Acceptance Criteria
- `npm run build` succeeds.
- `npm run lint` succeeds.
- `npm run test` runs unit tests.
- `npm run test:e2e` can run Playwright smoke test (requires browser install once).
- Existing learning flow still works in browser:
  - Start dialog
  - Submit answer
  - See feedback and state snapshot

## Notes
- Backend URL remains user-editable in UI.
- Default backend remains `http://127.0.0.1:8001`.
- Local debugging of frontend + backend together should use `scripts/restart-dev.ps1` from repo root.
