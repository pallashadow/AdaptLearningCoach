# Google Cloud Run Deployment Guide (Current Project)

This repository's backend is a FastAPI ASGI app in `main.py` (`app = FastAPI(...)`).

Important current-state notes:
- `deploy/deploy.sh` **exists** and is the recommended deployment script.
- Dependencies are installed from `requirements.txt` (not Poetry).
- Current API endpoints include:
  - `/health`
  - `/dialogs/start`
  - `/dialogs/answer`
  - `/dialogs/{dialog_id}`
  - `/users/{user_id}/dialogs` (delete user dialogs)
  - `/users/{user_id}/reset` (reset persisted user state + dialogs)
- There is **no** Cloud Functions-style Python entry point like `def handler(request): ...` in the current code.

Because of that, the deployment path that matches the current project is **Cloud Run**.

## Prerequisites

1. Google Cloud project with billing enabled
2. `gcloud` CLI installed and authenticated
3. Required APIs enabled

```bash
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com
```

## Deploy to Cloud Run (Recommended)

### Option A: Use repo script (recommended)

From project root (`agentic_learning/`), run:

```bash
./deploy/deploy.sh
```

If you are in PowerShell on Windows, run with Git Bash:

```powershell
& 'D:\Program\Git\bin\bash.exe' -lc 'cd /d/PROJECT/agentic_learning && ./deploy/deploy.sh'
```

The script:
- loads `.env`
- validates required runtime vars (`OPENAI_API_KEY`, `GOOGLE_API_KEY`)
- deploys `main:app` to Cloud Run with source build

### Option B: Manual deploy command

From repo root:

```bash
gcloud run deploy agentic-learning-api \
  --source . \
  --region YOUR_REGION \
  --allow-unauthenticated \
  --set-build-env-vars GOOGLE_ENTRYPOINT="uvicorn main:app --host 0.0.0.0 --port \$PORT" \
  --set-env-vars OPENAI_API_KEY=YOUR_OPENAI_API_KEY,GOOGLE_API_KEY=YOUR_GOOGLE_API_KEY
```

After deployment, test:

```bash
curl https://YOUR_SERVICE_URL/health
```

## Environment Variables

Required:
- `OPENAI_API_KEY`: OpenAI API key
- `GOOGLE_API_KEY`: Gemini API key

Optional:
- `FIRESTORE_PROJECT_ID`: override auto-detected GCP project id
- `FIRESTORE_COLLECTION`: Firestore collection name (default: `agentic_dialogs`)
- `GOOGLE_APPLICATION_CREDENTIALS`: service account JSON path (mainly for local/dev)

## Re-Deploy Checklist (After Code Changes)

1. Commit and push your changes.
2. Run deployment (`./deploy/deploy.sh` or manual `gcloud run deploy ...`).
3. Verify revision is healthy:
   - `GET /health` returns `200`.
4. Run one smoke flow:
   - `POST /dialogs/start`
   - `POST /dialogs/answer`
   - `POST /users/{user_id}/reset`
5. Confirm Cloud Run logs have no startup traceback.

## About Cloud Functions (2nd gen)

Cloud Functions requires an HTTP function entry point (`--entry-point`), but the current project exposes a FastAPI app object instead.

So with current code, direct Cloud Functions deployment is **not ready yet**.

If you must use Cloud Functions, add an adapter entry point first (plus any required bridge dependency), then deploy with `gcloud functions deploy ... --gen2 --entry-point ...`.

