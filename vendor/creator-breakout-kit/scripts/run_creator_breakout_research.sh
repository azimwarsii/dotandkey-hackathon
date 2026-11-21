#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT/.env"

if [[ -f "$ENV_FILE" ]]; then
  set -a
  source "$ENV_FILE"
  set +a
fi

usage() {
  cat <<'EOF'
Usage:
  run_creator_breakout_research.sh \
    --brand-name "Example Brand" \
    --brand-url "https://example.com" \
    --niche "example category" \
    --keywords "example keyword,buyer objection,category trend"

Optional:
  --platforms "tiktok,instagram,youtube"
  --out-dir /path/to/run-dir
  --audience-signals
  --audience-limit 3
  --audience-track videos|creators|both
  --audience-cadence weekly|daily|every_other_day|twelve_hours|six_hours

Before first run:
  cp .env.example .env
  bash scripts/preflight.sh
EOF
}

BRAND_NAME=""
BRAND_URL=""
NICHE=""
KEYWORDS=""
PLATFORMS="tiktok,instagram,youtube"
OUT_DIR=""
AUDIENCE_SIGNALS="false"
AUDIENCE_LIMIT="3"
AUDIENCE_TRACK="videos"
AUDIENCE_CADENCE="weekly"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --brand-name) BRAND_NAME="$2"; shift 2 ;;
    --brand-url) BRAND_URL="$2"; shift 2 ;;
    --niche) NICHE="$2"; shift 2 ;;
    --keywords) KEYWORDS="$2"; shift 2 ;;
    --platforms) PLATFORMS="$2"; shift 2 ;;
    --out-dir) OUT_DIR="$2"; shift 2 ;;
    --audience-signals) AUDIENCE_SIGNALS="true"; shift ;;
    --audience-limit) AUDIENCE_LIMIT="$2"; shift 2 ;;
    --audience-track) AUDIENCE_TRACK="$2"; shift 2 ;;
    --audience-cadence) AUDIENCE_CADENCE="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown arg: $1" >&2; usage; exit 1 ;;
  esac
done

[[ -n "$BRAND_NAME" && -n "$BRAND_URL" && -n "$NICHE" && -n "$KEYWORDS" ]] || { usage; exit 1; }

if [[ -z "$OUT_DIR" ]]; then
  DATE=$(date +%F)
  SLUG=$(echo "$BRAND_NAME" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9]/-/g' | sed 's/-\+/-/g' | sed 's/^-\|-$//g')
  OUT_DIR="$ROOT/runs/${DATE}-${SLUG}-outlier-pass"
fi

mkdir -p "$OUT_DIR"

echo "Running Firecrawl brand discovery..."
python3 "$ROOT/skills/brand-snapshot/scripts/firecrawl_brand_discovery.py" \
  --brand-name "$BRAND_NAME" \
  --brand-url "$BRAND_URL" \
  --out-dir "$OUT_DIR"

echo "Running Virlo outlier research..."
python3 "$ROOT/skills/breakout-pattern-research/scripts/virlo_outlier_research.py" \
  --brand-name "$BRAND_NAME" \
  --niche "$NICHE" \
  --keywords "$KEYWORDS" \
  --platforms "$PLATFORMS" \
  --out-dir "$OUT_DIR"

if [[ "$AUDIENCE_SIGNALS" == "true" ]]; then
  echo "Running Virlo audience-signal tracking..."
  python3 "$ROOT/skills/breakout-pattern-research/scripts/virlo_tracking_intelligence.py" \
    --research-dir "$OUT_DIR" \
    --limit "$AUDIENCE_LIMIT" \
    --track "$AUDIENCE_TRACK" \
    --scrape-cadence "$AUDIENCE_CADENCE"
fi

echo "Done. Outputs in: $OUT_DIR"
