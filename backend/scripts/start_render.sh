#!/usr/bin/env sh
set -eu

export PORT="${PORT:-10000}"
exec sh scripts/start.sh
