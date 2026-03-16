#!/bin/bash
# Tindahan Store POS – startup script
set -e
cd "$(dirname "$0")"

echo "Initialising database and starting server..."
python3 app.py
