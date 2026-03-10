# Frontend Local Development Guide

## Scope
This document is dedicated to frontend development under `frontend/`.
It covers local startup, debugging, quality checks, and common troubleshooting.
In this project, running frontend + backend together for debugging is called `Local Dev` / `本地联调` (not deploy).

## Stack
- Node.js: 22 LTS preferred (20 LTS also supported)
- Build tool: Vite
- UI: React + TypeScript
- Data fetching/state: TanStack Query
- Form + validation: react-hook-form + zod
- Quality: ESLint + Prettier + Vitest + Playwright + Husky/lint-staged

## Directory
- Frontend root: `frontend/`
- Main entry: `frontend/src/main.tsx`
- Main app: `frontend/src/App.tsx`
- API layer: `frontend/src/api/dialogApi.ts`
- Unit tests: `frontend/src/**/*.test.ts`
- E2E tests: `frontend/e2e/`

## Prerequisites
1. Install Node.js 22 LTS (recommended).
2. In project root, ensure backend can run (FastAPI with `.venv`).
3. Install frontend dependencies:

```bash
cd frontend
npm install
```

## One-Command Local Dev (Recommended)

From repo root:

```bash
powershell -ExecutionPolicy Bypass -File .\scripts\restart-dev.ps1
```

This starts both services:
- backend: `http://127.0.0.1:8001`
- frontend: `http://127.0.0.1:5173`

## Run Frontend Locally
```bash
cd frontend
npm run dev
```

Default URL:
- http://localhost:5173

## Backend Connection
The page has a `Backend URL` field.
Recommended backend URL:
- `http://127.0.0.1:8001` (default local dev script)

If this value is wrong, `Start Dialog` or `Submit Answer` will fail.

## Debugging
Use browser DevTools:
1. `Console`: runtime errors
2. `Network`: check `/dialogs/start`, `/dialogs/answer`, `/dialogs/{id}`, `/users/{user_id}/reset`
3. `Sources`: set breakpoints in TSX files

## Quality Commands
Run these in `frontend/`:

```bash
npm run typecheck
npm run lint
npm run build
npm run test
npm run test:e2e
```

Notes:
- `test:e2e` requires Playwright browser install once:

```bash
npx playwright install chromium
```

## Formatting
- Format all files:

```bash
npm run format
```

- Check format only:

```bash
npm run format:check
```

## Git Hook
Pre-commit hook runs lint/format on staged files via `lint-staged`.
Hook file:
- `frontend/.husky/pre-commit`

## Common Issues
1. `vite failed to load config / spawn EPERM`
- Retry command with proper terminal permissions.
- Ensure Node/npm are correctly installed and not blocked by policy.

2. `dialog_id not found`
- The dialog does not exist in current backend data (deleted/reset/restarted with different project/credentials).
- Start a new dialog and confirm `Backend URL` + `User ID` are correct.

3. `EBADENGINE`
- Means current Node version does not match project `engines`.
- Switch to Node 22 LTS.

## Related Docs
- Modernization plan: `docs/FRONTEND_MODERNIZATION_PLAN.md`
- Project overview: `README.md`
