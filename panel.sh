#!/usr/bin/env bash
# Lanceur du panel pour Linux / macOS / WSL.
set -euo pipefail
cd "$(dirname "$0")"

PY=""
for candidate in python3 python; do
  if command -v "$candidate" >/dev/null 2>&1 &&
     "$candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' 2>/dev/null; then
    PY="$candidate"; break
  fi
done

if [ -z "$PY" ]; then
  echo "Python 3.9+ requis. Installez-le puis relancez :" >&2
  echo "  Debian/Ubuntu : sudo apt install python3" >&2
  echo "  macOS         : brew install python" >&2
  exit 1
fi

echo "MC Servers Panel — http://localhost:8765/"
exec "$PY" -m mcpanel "$@"
