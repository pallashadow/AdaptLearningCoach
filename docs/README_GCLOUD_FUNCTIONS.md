# Google Cloud Deployment (Current Project)

This repository's backend is a FastAPI ASGI app in `main.py` (`app = FastAPI(...)`).

Important current-state notes:
- There is **no** `deploy/deploy.sh` in this repo.
- Dependencies are installed from `requirements.txt` (not Poetry).
- Current API endpoints are `/health`, `/dialogs/start`, `/dialogs/answer`, `/dialogs/{dialog_id}`.
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

## About Cloud Functions (2nd gen)

Cloud Functions requires an HTTP function entry point (`--entry-point`), but the current project exposes a FastAPI app object instead.

So with current code, direct Cloud Functions deployment is **not ready yet**.

If you must use Cloud Functions, add an adapter entry point first (plus any required bridge dependency), then deploy with `gcloud functions deploy ... --gen2 --entry-point ...`.

