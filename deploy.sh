#!/usr/bin/env bash
set -euo pipefail

# Deploy RepoVision AI backend without collapsing env vars into a comma string.
# Required environment variables must be exported in the shell/CI runner before
# this script is run. Do not replace these with a comma-separated --set-env-vars.

SERVICE="${SERVICE:-repovision-backend}"
REGION="${REGION:-us-central1}"
SOURCE_DIR="${SOURCE_DIR:-backend}"
PROJECT_ID="${GOOGLE_CLOUD_PROJECT:?GOOGLE_CLOUD_PROJECT must be set}"
SERVICE_ACCOUNT="${SERVICE_ACCOUNT:-174510296487-compute@developer.gserviceaccount.com}"

require_env() {
  local name="$1"
  if [[ -z "${!name:-}" ]]; then
    echo "Missing required environment variable: ${name}" >&2
    exit 1
  fi
}

require_env "GITHUB_TOKEN"
require_env "GOOGLE_CLOUD_PROJECT"
require_env "GOOGLE_CLOUD_LOCATION"
require_env "GOOGLE_GENAI_USE_VERTEXAI"

echo "Deploying ${SERVICE} to ${REGION} with no traffic..."
gcloud run deploy "${SERVICE}" \
  --source "${SOURCE_DIR}" \
  --project "${PROJECT_ID}" \
  --region "${REGION}" \
  --service-account "${SERVICE_ACCOUNT}" \
  --allow-unauthenticated \
  --no-traffic

echo "Updating Cloud Run env vars separately..."
gcloud run services update "${SERVICE}" \
  --project "${PROJECT_ID}" \
  --region "${REGION}" \
  --update-env-vars "GITHUB_TOKEN=${GITHUB_TOKEN}"

gcloud run services update "${SERVICE}" \
  --project "${PROJECT_ID}" \
  --region "${REGION}" \
  --update-env-vars "GOOGLE_CLOUD_PROJECT=${GOOGLE_CLOUD_PROJECT}"

gcloud run services update "${SERVICE}" \
  --project "${PROJECT_ID}" \
  --region "${REGION}" \
  --update-env-vars "GOOGLE_CLOUD_LOCATION=${GOOGLE_CLOUD_LOCATION}"

gcloud run services update "${SERVICE}" \
  --project "${PROJECT_ID}" \
  --region "${REGION}" \
  --update-env-vars "GOOGLE_GENAI_USE_VERTEXAI=${GOOGLE_GENAI_USE_VERTEXAI}"

if [[ -n "${GEMINI_API_KEY:-}" ]]; then
  gcloud run services update "${SERVICE}" \
    --project "${PROJECT_ID}" \
    --region "${REGION}" \
    --update-env-vars "GEMINI_API_KEY=${GEMINI_API_KEY}"
fi

if [[ -n "${AGENT_ENGINE_ID:-}" ]]; then
  gcloud run services update "${SERVICE}" \
    --project "${PROJECT_ID}" \
    --region "${REGION}" \
    --update-env-vars "AGENT_ENGINE_ID=${AGENT_ENGINE_ID}"
fi

echo "Migrating traffic to the newest revision..."
gcloud run services update-traffic "${SERVICE}" \
  --project "${PROJECT_ID}" \
  --region "${REGION}" \
  --to-latest

echo "Deployment complete."
