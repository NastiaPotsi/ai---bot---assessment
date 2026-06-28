#!/usr/bin/env bash
set -euo pipefail

python3 -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip
python -m pip install -r requirements.txt

python -m compileall app
python -m pytest
docker build -t engineering-service-desk-chatbot:latest .
