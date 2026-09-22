#!/bin/bash
# Go to the repository directory
cd "$(dirname "$0")" || exit 1

# Export PATH for cron environment
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:$PATH"

# Activate virtual environment if present
if [ -d "venv" ]; then
    source venv/bin/activate
elif [ -d "../venv" ]; then
    source ../venv/bin/activate
fi

LOG_FILE="crawler_run.log"

exec >> "$LOG_FILE" 2>&1

echo "=========================================="
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting PolitAgent Crawler..."

# Ensure repository is synced with remote before crawling
git pull origin main --rebase -X ours

# Run crawler with max-process 50
python3 -u crawler.py --max-process 50

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Staging files in git..."
git add .

# Check if there are changes to commit
if ! git diff-index --quiet HEAD --; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Committing changes..."
    git commit -m "auto: PolitAgent Crawler update"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Pushing to GitHub..."
    git pull origin main --rebase -X ours
    git push
else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] No changes to commit."
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Done."
