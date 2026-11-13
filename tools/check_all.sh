#!/usr/bin/env bash
# Run every check, in order, from anywhere: compileall, ruff, check_imports,
# check_protected_names --check, unittest. Stops at the first failure.
# Uses ./.venv if it exists (python3 -m venv .venv, then install ruff and the
# packages from both requirements.txt files).
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT=$(pwd)

if [ -x "$ROOT/.venv/bin/python" ]; then
  PYTHON="$ROOT/.venv/bin/python"
else
  PYTHON=python3
fi

# Don't leave .pyc files behind in the source folders.
export PYTHONDONTWRITEBYTECODE=1

echo "== 1/5 compileall"
"$PYTHON" - <<'PY'
import pathlib
import sys

failed = False
for folder in ("discord-bot", "telegram-bot", "tools"):
    for path in sorted(pathlib.Path(folder).rglob("*.py")):
        if ".venv" in path.parts or "__pycache__" in path.parts:
            continue
        try:
            compile(path.read_text(encoding="utf-8"), str(path), "exec")
        except SyntaxError as error:
            print(f"{path}: {error}")
            failed = True
sys.exit(1 if failed else 0)
PY
echo "compileall: ok"

echo "== 2/5 ruff (rules F and E9, see ruff.toml)"
# Without ruff the count below would read 0 and pass, so stop here instead.
if ! "$PYTHON" -m ruff --version >/dev/null 2>&1; then
  echo "ruff: not installed for $PYTHON (install it in .venv)" >&2
  exit 1
fi
"$PYTHON" -m ruff check --statistics . || true
# The findings that existed before #19 are the baseline. The count must not grow.
COUNT=$("$PYTHON" -m ruff check --output-format concise . | grep -cE '^[^ ]+:[0-9]+:[0-9]+: ' || true)
BASELINE=$(tr -d '[:space:]' < tests/ruff-baseline.txt)
echo "ruff findings: $COUNT (baseline $BASELINE)"
if [ "$COUNT" -gt "$BASELINE" ]; then
  echo "ruff: more findings than the baseline" >&2
  exit 1
fi

echo "== 3/5 check_imports"
"$PYTHON" tools/check_imports.py

echo "== 4/5 check_protected_names --check"
"$PYTHON" tools/check_protected_names.py --check

echo "== 5/5 unittest"
(cd discord-bot && "$PYTHON" -m unittest)

echo "check_all: all checks passed"
