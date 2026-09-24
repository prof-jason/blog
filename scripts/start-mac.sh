#!/usr/bin/env bash
# Build the image and (re)start the app at http://localhost:8000
# Only this computer can reach it by default. To let other devices on the network (e.g. students'
# laptops) reach it, run: BLOG_HOST=0.0.0.0 scripts/start-mac.sh
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ ! -f .env ]]; then
  echo "Missing .env in the project root (it needs OPENROUTER_API_KEY)." >&2
  exit 1
fi

docker build -t blog-app .
docker rm -f blog-app >/dev/null 2>&1 || true
docker run -d --name blog-app --restart unless-stopped \
  -p "${BLOG_HOST:-127.0.0.1}:8000:8000" --env-file .env blog-app >/dev/null
echo "App running at http://localhost:8000"
