#!/usr/bin/env sh
set -e

ollama serve &

until curl --silent http://localhost:11434/api/tags >/dev/null; do
  sleep 1
done

[[ -z "${TEST}" ]] && { [[ -z "${DEV}" ]] && python3 || python3 -u src/main.py; }
