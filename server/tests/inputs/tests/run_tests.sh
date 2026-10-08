#!/usr/bin/env bash
# Run the automated test suite from any current working directory.
set -euo pipefail

project_directory="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_directory"
python -m pytest -q tests
