#!/usr/bin/env bash
#
# Deploy the Civic AI Engine to Cloud Run.
#
#   ./deploy/cloudrun.sh YOUR_GCP_PROJECT_ID
#   ./deploy/cloudrun.sh YOUR_GCP_PROJECT_ID --account you@example.com
#
# Builds the container with Cloud Build and deploys it. Safe to re-run; it
# updates the existing service in place.
#
# WHICH ACCOUNT THIS USES
#
# gcloud keeps one active account per machine, and it is easy to be logged into
# a work identity and a personal one at the same time. Deploying a community's
# AI to the wrong organization is not a mistake you want to discover from a
# billing alert, so this script refuses to guess: it prints the account, the
# project and the project's owning organization, and stops if any of it looks
# wrong. Set EXPECTED_ACCOUNT (or --account) to make the check strict.
#
# What this gives you is a testable instance, not a production deployment. It
# runs one instance with an in-memory filesystem, which means the archive does
# not survive a restart. Read deploy/README.md before putting a town on it; the
# short version is that production needs Cloud SQL, and ROADMAP.md explains why.

set -euo pipefail

PROJECT_ID=""
EXPECTED_ACCOUNT="${EXPECTED_ACCOUNT:-}"
ASSUME_YES="${ASSUME_YES:-}"
REGION="${REGION:-us-central1}"
SERVICE="${SERVICE:-civic-ai-engine}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --account)  EXPECTED_ACCOUNT="${2:-}"; shift 2 ;;
    --region)   REGION="${2:-}"; shift 2 ;;
    --service)  SERVICE="${2:-}"; shift 2 ;;
    --yes|-y)   ASSUME_YES="1"; shift ;;
    -h|--help)  sed -n '2,25p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    -*)         echo "unknown option: $1" >&2; exit 2 ;;
    *)          PROJECT_ID="$1"; shift ;;
  esac
done

PROJECT_ID="${PROJECT_ID:-${GOOGLE_CLOUD_PROJECT:-}}"

if [[ -z "$PROJECT_ID" ]]; then
  echo "usage: $0 YOUR_GCP_PROJECT_ID [--account you@example.com]" >&2
  exit 2
fi

if ! command -v gcloud >/dev/null 2>&1; then
  echo "gcloud is not installed. Get it at https://cloud.google.com/sdk/docs/install" >&2
  exit 1
fi

# --- who is about to spend money -----------------------------------------

ACTIVE_ACCOUNT="$(gcloud config get-value account 2>/dev/null || true)"

if [[ -z "$ACTIVE_ACCOUNT" || "$ACTIVE_ACCOUNT" == "(unset)" ]]; then
  echo "No active gcloud account. Log in first:" >&2
  echo "  gcloud auth login" >&2
  exit 1
fi

if [[ -n "$EXPECTED_ACCOUNT" && "$ACTIVE_ACCOUNT" != "$EXPECTED_ACCOUNT" ]]; then
  cat >&2 <<EOF

REFUSING TO DEPLOY: wrong account.

  active account:   $ACTIVE_ACCOUNT
  expected account: $EXPECTED_ACCOUNT

Switch, then run this again:

  gcloud config set account $EXPECTED_ACCOUNT

Accounts gcloud knows about on this machine:
EOF
  gcloud auth list --format="  value(account)" 2>/dev/null >&2 || true
  exit 1
fi

# --- who owns the project ------------------------------------------------
#
# A project under an organization belongs to that organization's Google
# Workspace, not to the person running this. That is the distinction worth
# catching: a personal project has no organization parent.

if ! PROJECT_JSON="$(gcloud projects describe "$PROJECT_ID" --format=json 2>/dev/null)"; then
  echo "Cannot read project '$PROJECT_ID' as $ACTIVE_ACCOUNT." >&2
  echo "Either the project does not exist, or this account cannot see it." >&2
  echo "Projects this account can see:" >&2
  gcloud projects list --format="  value(projectId)" 2>/dev/null | head -20 >&2 || true
  exit 1
fi

PARENT_TYPE="$(printf '%s' "$PROJECT_JSON" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("parent",{}).get("type",""))' 2>/dev/null || true)"
PARENT_ID="$(printf '%s' "$PROJECT_JSON" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("parent",{}).get("id",""))' 2>/dev/null || true)"

ORG_NAME=""
if [[ "$PARENT_TYPE" == "organization" ]]; then
  ORG_NAME="$(gcloud organizations describe "$PARENT_ID" --format='value(displayName)' 2>/dev/null || echo "$PARENT_ID")"
fi

echo
echo "================================================================"
echo "  About to deploy, and this will incur charges."
echo "================================================================"
printf "  account   %s\n" "$ACTIVE_ACCOUNT"
printf "  project   %s\n" "$PROJECT_ID"
if [[ -n "$ORG_NAME" ]]; then
  printf "  owned by  organization: %s\n" "$ORG_NAME"
  printf "            NOT a personal project\n"
else
  printf "  owned by  no organization (personal project)\n"
fi
printf "  region    %s\n" "$REGION"
printf "  service   %s\n" "$SERVICE"
echo "================================================================"

if [[ -n "$ORG_NAME" && -z "$EXPECTED_ACCOUNT" ]]; then
  echo
  echo "  This project belongs to an organization. If you meant to deploy to a"
  echo "  personal project, stop now and pick a different project id."
fi

if [[ -z "$ASSUME_YES" ]]; then
  echo
  if [[ -t 0 ]]; then
    read -r -p "Deploy as $ACTIVE_ACCOUNT to $PROJECT_ID? [y/N] " reply
    case "$reply" in
      [yY]|[yY][eE][sS]) ;;
      *) echo "Stopped. Nothing was deployed."; exit 0 ;;
    esac
  else
    echo "Not a terminal and --yes was not passed. Stopping rather than"
    echo "deploying unattended to an account nobody confirmed."
    exit 1
  fi
fi

# --- deploy ----------------------------------------------------------------

echo
echo "==> Setting project"
gcloud config set project "$PROJECT_ID" >/dev/null

echo "==> Enabling the APIs this needs (no-op if already on)"
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  --quiet

IMAGE="gcr.io/${PROJECT_ID}/${SERVICE}"

echo "==> Building the container (several minutes the first time)"
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
  --set-env-vars "COMMUNITY_SYNC_ENABLED=false,COMMUNITY_AI_VERSION=0.3" \
  --quiet

URL="$(gcloud run services describe "$SERVICE" --region "$REGION" --format='value(status.url)')"

echo
echo "================================================================"
echo "  Deployed: $URL"
echo "  Account:  $ACTIVE_ACCOUNT"
echo "  Project:  $PROJECT_ID"
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
echo "     when the instance restarts. Fine for a look; not fine for a town."
echo "     See deploy/README.md."
