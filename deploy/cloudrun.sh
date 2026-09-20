#!/usr/bin/env bash
#
# Deploy Community AI to Cloud Run.
#
#   ./deploy/cloudrun.sh YOUR_GCP_PROJECT_ID
#
# Builds the container with Cloud Build and deploys it. Safe to re-run; it
# updates the existing service in place.
#
# What this gives you is a testable instance, not a production deployment. It
# runs one instance with an in-memory filesystem, which means the archive does
# not survive a restart. Read deploy/README.md before putting a town on it; the
# short version is that production needs Cloud SQL, and ROADMAP.md explains why.

set -euo pipefail

PROJECT_ID="${1:-${GOOGLE_CLOUD_PROJECT:-}}"
REGION="${REGION:-us-central1}"
SERVICE="${SERVICE:-community-ai}"

if [[ -z "$PROJECT_ID" ]]; then
  echo "usage: $0 YOUR_GCP_PROJECT_ID" >&2
  echo "   or: GOOGLE_CLOUD_PROJECT=... $0" >&2
  exit 2
fi

if ! command -v gcloud >/dev/null 2>&1; then
  echo "gcloud is not installed. Get it at https://cloud.google.com/sdk/docs/install" >&2
  exit 1
fi

echo "==> Project: $PROJECT_ID   Region: $REGION   Service: $SERVICE"
gcloud config set project "$PROJECT_ID" >/dev/null

echo "==> Enabling the APIs this needs (no-op if already on)"
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  --quiet

IMAGE="gcr.io/${PROJECT_ID}/${SERVICE}"

echo "==> Building the container (this takes a few minutes the first time)"
gcloud builds submit --tag "$IMAGE" --timeout=1800s .

echo "==> Deploying to Cloud Run"
gcloud run deploy "$SERVICE" \
  --image "$IMAGE" \
  --region "$REGION" \
  --platform managed \
  --allow-unauthenticated \
  --port 8080 \
  --memory 4Gi \
  --cpu 2 \
  --timeout 600 \
  --concurrency 20 \
  --min-instances 0 \
  --max-instances 1 \
  --set-env-vars "COMMUNITY_SYNC_ENABLED=false,COMMUNITY_AI_VERSION=0.2" \
  --quiet

URL="$(gcloud run services describe "$SERVICE" --region "$REGION" --format='value(status.url)')"

echo
echo "================================================================"
echo "  Deployed: $URL"
echo "================================================================"
echo
echo "Check it:"
echo "  curl $URL/healthz"
echo "  open  $URL"
echo
echo "Two things to know before you test:"
echo
echo "  1. There is no model attached yet. Point a project at your LM Studio"
echo "     server over a tunnel, or set a frontier API key:"
echo "       gcloud run services update $SERVICE --region $REGION \\"
echo "         --set-env-vars ANTHROPIC_API_KEY=sk-ant-..."
echo
echo "  2. The filesystem is in-memory. Projects and the archive disappear"
echo "     when the instance restarts. That is fine for a look; it is not fine"
echo "     for a town. See deploy/README.md."
