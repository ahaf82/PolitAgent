#!/bin/bash
# Go to the script directory
cd "$(dirname "$0")"

# Activate the virtual environment
source venv/bin/activate

echo "=========================================="
echo "[$(date)] Starting PolitAgent Crawler..."

# Run crawler
python -u crawler.py

echo "[$(date)] Staging files in git..."
git add .

# Check if there are changes to commit
if ! git diff-index --quiet HEAD --; then
    echo "[$(date)] Committing changes..."
    git commit -m "auto: PolitAgent Crawler update"
    echo "[$(date)] Pushing to GitHub..."
    git push
else
    echo "[$(date)] No changes to commit."
fi

echo "[$(date)] Done."
