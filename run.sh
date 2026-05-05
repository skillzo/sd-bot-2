#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/.."

exec python3 -m uvicorn webhook.app:app --host 0.0.0.0 --port "${PORT:-8001}"
