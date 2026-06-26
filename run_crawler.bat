@echo off
cd /d "c:\Users\a_h82\OneDrive\Dokumente\Projects\PolitAgent"
(
echo ==========================================
echo [%date% %time%] Starting PolitAgent Crawler...
python -u crawler.py --max-process 50
echo [%date% %time%] Staging files in git...
git add .
echo [%date% %time%] Committing...
git commit -m "auto: PolitAgent Crawler update"
echo [%date% %time%] Pushing...
git push
echo [%date% %time%] Done.
) >> crawler_run.log 2>&1
