#!/bin/bash
# Manually trigger a full scrape + push right now.
# The remote Claude agent will pick it up within a minute.

set -e
DIR="$(cd "$(dirname "$0")" && pwd)"

echo "==> Running scraper..."
"$DIR/venv/bin/python3" "$DIR/scrape.py"

echo ""
echo "Done! new_jobs.json pushed to GitHub."
echo "The remote Claude agent will summarize and email the digest shortly."
echo ""
echo "To trigger the agent immediately (instead of waiting for its schedule):"
echo "  Visit https://claude.ai/code/routines and click 'Run Now'"
