#!/bin/sh
set -eu
exec curl --fail-with-body --silent --show-error --connect-timeout 10 --max-time 60 \
  --retry 3 --retry-connrefused -X POST \
  -H "Authorization: Bearer ${JOBS_CRON_TOKEN:?missing cron token}" \
  "${STUDIO_BACKEND:-http://api.railway.internal:8000}/api/jobs/nightly"
