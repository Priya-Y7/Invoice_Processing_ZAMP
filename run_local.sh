#!/usr/bin/env bash
# Local run without Docker. Needs Python 3.11+, Node 18+, and Tesseract (apt install tesseract-ocr / brew install tesseract).
set -e
cd "$(dirname "$0")/frontend" && npm install --no-audit --no-fund && npm run build
rm -rf ../backend/static && cp -r dist ../backend/static
cd ../backend && pip install -r requirements.txt
PYTHONPATH=. python3 -m uvicorn app.main:app --port 8000
