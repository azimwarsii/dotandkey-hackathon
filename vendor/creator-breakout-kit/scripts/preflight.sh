#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT/.env"
EXAMPLE_FILE="$ROOT/.env.example"

if [[ -f "$ENV_FILE" ]]; then
  set -a
  source "$ENV_FILE"
  set +a
fi

status_ok() { printf "✅ %s\n" "$1"; }
status_warn() { printf "⚠️  %s\n" "$1"; }
status_fail() { printf "❌ %s\n" "$1"; }

EXIT_CODE=0

echo "Creator Breakout Kit preflight"
echo "Root: $ROOT"
echo

command -v python3 >/dev/null 2>&1 && status_ok "python3 found ($(python3 --version 2>/dev/null))" || { status_fail "python3 missing"; EXIT_CODE=1; }

if [[ -f "$EXAMPLE_FILE" ]]; then
  status_ok ".env.example present"
else
  status_fail ".env.example missing"
  EXIT_CODE=1
fi

if [[ -f "$ENV_FILE" ]]; then
  status_ok ".env present"
else
  status_warn ".env missing, kit can still run in quick-pass if you export vars elsewhere"
fi

if [[ -n "${FIRECRAWL_API_KEY:-}" ]]; then
  status_ok "FIRECRAWL_API_KEY configured"
else
  status_warn "FIRECRAWL_API_KEY missing, outlier-pass brand discovery will be unavailable"
fi

if [[ -n "${VIRLO_API_KEY:-}" ]]; then
  status_ok "VIRLO_API_KEY configured"
  status_ok "Virlo audience-signal tracking can be run with skills/breakout-pattern-research/scripts/virlo_tracking_intelligence.py"
else
  status_warn "VIRLO_API_KEY missing, Virlo outlier research will be unavailable"
fi

if [[ -n "${VIRLO_COMETS_PATH:-}" ]]; then
  [[ -f "$VIRLO_COMETS_PATH" ]] && status_ok "VIRLO_COMETS_PATH found at $VIRLO_COMETS_PATH" || status_warn "VIRLO_COMETS_PATH set but file not found yet: $VIRLO_COMETS_PATH"
else
  status_warn "VIRLO_COMETS_PATH not set, adapter will not reuse local comet ids"
fi

if [[ -n "${SCRAPECREATORS_API_KEY:-}" ]]; then
  status_ok "SCRAPECREATORS_API_KEY configured"
else
  status_warn "SCRAPECREATORS_API_KEY missing, video intelligence will be unavailable"
fi

if [[ -n "${OPENROUTER_API_KEY:-}" ]]; then
  status_ok "OPENROUTER_API_KEY configured"
else
  status_warn "OPENROUTER_API_KEY missing, Gemini video intelligence will be unavailable"
fi

echo
if [[ -n "${FIRECRAWL_API_KEY:-}" && -n "${VIRLO_API_KEY:-}" ]]; then
  status_ok "Outlier-pass prerequisites look good"
else
  status_warn "Outlier-pass is not fully configured. Use quick-pass or finish connector setup."
fi

if [[ -n "${SCRAPECREATORS_API_KEY:-}" && -n "${OPENROUTER_API_KEY:-}" ]]; then
  status_ok "Video-intelligence prerequisites look good"
else
  status_warn "Video-intelligence stage is not fully configured. Synthesis will fall back to metadata-only evidence."
fi

exit "$EXIT_CODE"
