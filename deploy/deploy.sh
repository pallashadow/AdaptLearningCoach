#!/bin/bash
# Load .env and deploy FastAPI app to Cloud Run.
# Run from project root: ./deploy/deploy.sh

set -euo pipefail

# Get the project root directory (parent of deploy/).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

SERVICE_NAME="${SERVICE_NAME:-agentic-learning-api}"
REGION="${REGION:-us-central1}"

echo "=== Starting deployment to Google Cloud Run ==="

if [ ! -f .env ]; then
    echo "Error: .env file not found."
    echo "Please create a .env file with required environment variables."
    exit 1
fi

if ! command -v gcloud >/dev/null 2>&1; then
    echo "Error: gcloud CLI not found. Install Google Cloud SDK first."
    exit 1
fi

echo "Loading environment variables from .env file..."
set -a
source .env
set +a

# Validate required runtime env vars.
if [ -z "${OPENAI_API_KEY:-}" ] || [ -z "${GOOGLE_API_KEY:-}" ]; then
    echo "Error: Missing required variables in .env."
    echo "Required: OPENAI_API_KEY, GOOGLE_API_KEY"
    exit 1
fi

ACTIVE_ACCOUNT="$(gcloud config get-value account 2>/dev/null || true)"
ACTIVE_PROJECT="$(gcloud config get-value project 2>/dev/null || true)"
echo "gcloud account: ${ACTIVE_ACCOUNT:-<unknown>}"
echo "gcloud project: ${ACTIVE_PROJECT:-<unknown>}"

if [ -z "${ACTIVE_PROJECT:-}" ]; then
    echo "Error: gcloud project is not set."
    echo "Run: gcloud config set project YOUR_PROJECT_ID"
    exit 1
fi

if ! gcloud projects describe "$ACTIVE_PROJECT" --format='value(projectNumber)' >/dev/null 2>&1; then
    echo ""
    echo "Error: Unable to access GCP project '$ACTIVE_PROJECT'."
    echo "Please check all of the following before retrying:"
    echo "  1) cloudresourcemanager.googleapis.com is enabled"
    echo "  2) This account/service account can access the project"
    echo "  3) Credentials point to the intended deploy identity"
    exit 1
fi

# Build env vars list for Cloud Run runtime.
ENV_ITEMS=(
    "OPENAI_API_KEY=$OPENAI_API_KEY"
    "GOOGLE_API_KEY=$GOOGLE_API_KEY"
)

if [ -n "${FIRESTORE_PROJECT_ID:-}" ]; then
    ENV_ITEMS+=("FIRESTORE_PROJECT_ID=$FIRESTORE_PROJECT_ID")
fi
if [ -n "${FIRESTORE_COLLECTION:-}" ]; then
    ENV_ITEMS+=("FIRESTORE_COLLECTION=$FIRESTORE_COLLECTION")
fi
if [ -n "${API_AUTH_TOKEN:-}" ]; then
    ENV_ITEMS+=("API_AUTH_TOKEN=$API_AUTH_TOKEN")
fi
if [ -n "${CORS_ALLOW_ORIGINS:-}" ]; then
    ENV_ITEMS+=("CORS_ALLOW_ORIGINS=$CORS_ALLOW_ORIGINS")
fi

ENV_VARS="$(IFS=,; echo "${ENV_ITEMS[*]}")"

echo "Deploying service (this may take 5-15 minutes)..."
echo "Service: $SERVICE_NAME"
echo "Region:  $REGION"
echo ""

gcloud run deploy "$SERVICE_NAME" \
  --source . \
  --region "$REGION" \
  --allow-unauthenticated \
  --memory 512Mi \
  --timeout 300 \
  --max-instances 10 \
  --set-build-env-vars "GOOGLE_ENTRYPOINT=uvicorn main:app --host 0.0.0.0 --port \$PORT" \
  --set-env-vars "$ENV_VARS" \
  --quiet

echo ""
echo "=== Deployment completed successfully! ==="

