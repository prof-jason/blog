#!/usr/bin/env bash
set -euo pipefail
docker rm -f blog-app >/dev/null 2>&1 && echo "App stopped." || echo "App was not running."
