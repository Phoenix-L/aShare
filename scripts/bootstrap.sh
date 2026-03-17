#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_NAME="aShare"
PROJECT_DIR="${HOME}/projects/${PROJECT_NAME}"
VENV_DIR="${PROJECT_DIR}/.venv"

echo "==> Bootstrapping ${PROJECT_NAME}"

if [[ ! -d "${PROJECT_DIR}" ]]; then
  echo "ERROR: Project directory not found: ${PROJECT_DIR}"
  echo "Please clone the repo first."
  exit 1
fi

cd "${PROJECT_DIR}"

echo "==> Current directory: $(pwd)"

if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 not found."
  exit 1
fi

echo "==> Python version"
python3 --version

echo "==> Pulling latest code from GitHub"
git pull --no-rebase origin HEAD || {
  echo "ERROR: git pull failed."
  exit 1
}

if [[ ! -d "${VENV_DIR}" ]]; then
  echo "==> Creating virtual environment"
  python3 -m venv "${VENV_DIR}"
else
  echo "==> Reusing existing virtual environment"
fi

echo "==> Activating virtual environment"
# shellcheck disable=SC1090
source "${VENV_DIR}/bin/activate"

echo "==> Upgrading pip tooling"
python -m pip install --upgrade pip setuptools wheel

if [[ -f "requirements.txt" ]]; then
  echo "==> Installing requirements.txt"
  pip install -r requirements.txt
fi

if [[ -f "pyproject.toml" ]]; then
  echo "==> Installing project in editable mode"
  pip install -e .
fi

echo "==> Python executable"
which python

echo "==> Running pytest"
pytest

echo "==> Bootstrap complete"

