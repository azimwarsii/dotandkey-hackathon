#!/usr/bin/env bash
# Run the pinned, unmodified upstream app when Docker is unavailable.
set -eu
revision=bded6ceaa46649068e8da5882d7c29fd8c977a3b
repo_root="$(cd "$(dirname "$0")/.." && pwd)"
install_dir="${CLIPFORGE_INSTALL_DIR:-$repo_root/data/cache/clipforge-$revision}"
export APP_DATA_DIR="${APP_DATA_DIR:-$repo_root/data/clipforge-service}"
if [ ! -d "$install_dir/.git" ]; then
  git clone https://github.com/xixihhhh/clipforge.git "$install_dir"
fi
cd "$install_dir"
git checkout --quiet "$revision"
if [ ! -x node_modules/.bin/next ]; then
  ELECTRON_SKIP_BINARY_DOWNLOAD=1 npx --yes pnpm@10.33.0 install --frozen-lockfile
fi
export FFMPEG_PATH="${FFMPEG_PATH:-$(node -p "require('ffmpeg-static')")}"
export FFPROBE_PATH="${FFPROBE_PATH:-$(node -p "require('@ffprobe-installer/ffprobe').path")}"
chmod u+x "$FFPROBE_PATH"
mkdir -p "$APP_DATA_DIR"
exec ./node_modules/.bin/next dev --hostname 127.0.0.1 --port "${CLIPFORGE_PORT:-3039}"
