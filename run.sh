#!/bin/bash
# APA 7 Reference Fixer — setup & launch script
# Run this once: bash run.sh
# After that you can just: python3 apa_fixer.py

set -e

echo "=== APA 7 Reference Fixer ==="

# Check Python 3
if ! command -v python3 &>/dev/null; then
    echo "Error: Python 3 is required. Install it from https://www.python.org"
    exit 1
fi

# Install dependency
echo "Installing dependencies..."
pip3 install -q -r requirements.txt

echo ""
echo "Launching app..."
echo "(Set ANTHROPIC_API_KEY env var or enter your key in the app)"
echo ""

python3 apa_fixer.py
