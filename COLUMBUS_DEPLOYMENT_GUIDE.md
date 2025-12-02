# Columbus Chat Production Deployment Guide

## Issues Fixed (Commit 9e19ff0)

1. **Alpine.js Null-Safety** - `templates/columbus_chat/index.html`
   - Added null-safe operators (`?.` and `??`) for `score_breakdown` fields
   - Prevents "Cannot read properties of undefined" errors
   - Falls back to 0 if score_breakdown is missing

2. **CSRF 403 on Reset** - `apps/dashboard/views_columbus_chat.py`
   - Added `@csrf_exempt` decorator to `reset_chat()` function
   - Fixes 403 Forbidden error on `/columbus/reset/` endpoint

3. **Nginx Buffer Settings** - `nginx_zoektrends.conf`
   - Increased `proxy_buffer_size` to 16k (was 4k)
   - Increased `proxy_buffers` to 16×32k = 512k total (was 8×16k = 128k)
   - Increased `proxy_busy_buffers_size` to 64k (was 32k)
   - Fixes `ERR_CONTENT_LENGTH_MISMATCH` on large JSON responses

4. **Diagnostic Script** - `test_server_columbus.py`
   - Tests environment variables (GOOGLE_APPLICATION_CREDENTIALS)
   - Tests BigQuery connection and data retrieval
   - Tests company scoring and score_breakdown structure
   - Tests Columbus Chat service response format

---

## Deployment Steps

### Step 1: SSH to Server
```bash
ssh rustem_kamalidenov@217.154.199.142
```

### Step 2: Pull Latest Code
```bash
cd ~/zoektrends-dashboard
git pull origin main
```

**Expected output:**
```
Updating 63a8f67..9e19ff0
Fast-forward
 apps/dashboard/views_columbus_chat.py | 1 +
 nginx_zoektrends.conf                 | 72 ++++++++++++++++++++++++++++++++++
 templates/columbus_chat/index.html    | 12 +++---
 test_server_columbus.py               | 214 +++++++++++++++++++++++++++++++++++
 4 files changed, 291 insertions(+), 6 deletions(-)
```

### Step 3: Run Diagnostic Script
```bash
source venv/bin/activate
python test_server_columbus.py
```

**What to check:**
- ✅ GOOGLE_APPLICATION_CREDENTIALS path exists
- ✅ BigQuery returns companies (>0 found)
- ✅ Companies have `score_breakdown` field after scoring
- ✅ Columbus Chat response includes `score_breakdown`

**If diagnostics fail:**
- Check `.env` file has correct `GOOGLE_APPLICATION_CREDENTIALS` path
- Verify `google-credentials.json` exists at that path
- Check file permissions: `ls -la ~/zoektrends-dashboard/*.json`

### Step 4: Update Nginx Configuration
```bash
# Backup current config
sudo cp /etc/nginx/sites-available/zoektrends /etc/nginx/sites-available/zoektrends.backup

# Deploy new config
sudo cp ~/zoektrends-dashboard/nginx_zoektrends.conf /etc/nginx/sites-available/zoektrends

# Test configuration
sudo nginx -t
```

**Expected output:**
```
nginx: the configuration file /etc/nginx/nginx.conf syntax is ok
nginx: configuration file /etc/nginx/nginx.conf test is successful
```

**If test fails:**
```bash
# Restore backup
sudo cp /etc/nginx/sites-available/zoektrends.backup /etc/nginx/sites-available/zoektrends
```

**If test passes, reload Nginx:**
```bash
sudo systemctl reload nginx
```

### Step 5: Restart Django Application
```bash
sudo systemctl restart zoektrends-django

# Check status
sudo systemctl status zoektrends-django
```

**Expected output:**
```
● zoektrends-django.service - Zoektrends Django Application
     Active: active (running)
     Status: "Gunicorn arbiter booted"
      Tasks: 5 (4 workers)
     Memory: ~230M
```

**Check logs if issues:**
```bash
tail -f ~/zoektrends-dashboard/logs/error.log
tail -f ~/zoektrends-dashboard/logs/access.log
```

### Step 6: Test Columbus Chat

1. **Open browser:** http://217.154.199.142/columbus

2. **Test Query 1: Top Prospects**
   ```
   Give me top 5 hot prospects
   ```
   **Expected:**
   - Company cards display with names, scores, categories
   - No Alpine.js errors in console
   - Score breakdown section shows all 6 scores (tech, type, industry, size, activity, recency)

3. **Test Query 2: Company Details**
   ```
   Tell me about Xccelerated
   ```
   **Expected:**
   - Company information displays
   - Strategy analysis if available
   - No errors in console

4. **Test Query 3: Technology Search**
   ```
   Find technology companies using BigQuery
   ```
   **Expected:**
   - Companies matching BigQuery technology returned
   - Company cards render correctly
   - No NoneType errors

5. **Test Reset Button**
   - Click "Reset Conversation"
   - Should show "Conversation reset successfully"
   - No 403 Forbidden error

---

## Troubleshooting

### Issue: "0 jobs, 0 companies" on dashboard

**Check BigQuery credentials:**
```bash
cd ~/zoektrends-dashboard
source venv/bin/activate
python -c "import os; print(f'Credentials: {os.getenv(\"GOOGLE_APPLICATION_CREDENTIALS\")}'); print(f'Exists: {os.path.exists(os.getenv(\"GOOGLE_APPLICATION_CREDENTIALS\", \"\"))}')"
```

**Test BigQuery connection:**
```bash
python -c "
from apps.dashboard.services.bigquery_service import get_bigquery_service
bq = get_bigquery_service()
jobs = bq.get_jobs(limit=10)
print(f'Found {len(jobs)} jobs')
"
```

### Issue: Alpine.js errors still appearing

**Check browser console:**
- `F12` → Console tab
- Look for "Alpine Expression Error"
- If error mentions `score_breakdown`, verify files were updated:
  ```bash
  grep -n "score_breakdown?." ~/zoektrends-dashboard/templates/columbus_chat/index.html
  ```

**Should show 6 lines with `?.` operator:**
```
225:    <span class="font-medium" x-text="(company.score_breakdown?.tech_score ?? 0) + '/30'"></span>
229:    <span class="font-medium" x-text="(company.score_breakdown?.company_type_score ?? 0) + '/20'"></span>
...
```

### Issue: ERR_CONTENT_LENGTH_MISMATCH

**Verify Nginx buffers increased:**
```bash
sudo grep -A 5 "proxy_buffer" /etc/nginx/sites-available/zoektrends
```

**Should show:**
```
proxy_buffer_size 16k;
proxy_buffers 16 32k;
proxy_busy_buffers_size 64k;
```

### Issue: 500 errors on Columbus Chat

**Check Django logs:**
```bash
tail -50 ~/zoektrends-dashboard/logs/error.log
```

**Common errors:**
- `ModuleNotFoundError` → Reinstall requirements: `pip install -r requirements.txt`
- `OperationalError` → BigQuery credentials issue
- `AttributeError` → Code not updated correctly, run `git pull` again

---

## Rollback Procedure

If deployment causes critical issues:

### Rollback Code
```bash
cd ~/zoektrends-dashboard
git log --oneline -5  # Find previous commit hash
git reset --hard 63a8f67  # Previous working commit
sudo systemctl restart zoektrends-django
```

### Rollback Nginx
```bash
sudo cp /etc/nginx/sites-available/zoektrends.backup /etc/nginx/sites-available/zoektrends
sudo nginx -t
sudo systemctl reload nginx
```

---

## Verification Checklist

- [ ] Code pulled from GitHub successfully
- [ ] Diagnostic script runs without errors
- [ ] BigQuery returns companies (>0 found)
- [ ] Companies have `score_breakdown` field
- [ ] Nginx config updated and reloaded
- [ ] Django service restarted successfully
- [ ] Columbus Chat displays company cards
- [ ] No Alpine.js errors in browser console
- [ ] Score breakdown section shows all 6 scores
- [ ] Reset button works (no 403 error)
- [ ] Technology search returns results

---

## Post-Deployment Notes

**What was fixed:**
1. ✅ Alpine.js rendering errors → Null-safe operators
2. ✅ CSRF 403 on reset → @csrf_exempt decorator
3. ✅ Large response timeouts → Increased Nginx buffers
4. ✅ Diagnostic tooling → test_server_columbus.py

**What still needs investigation (if issues persist):**
1. ❓ BigQuery connection → Run diagnostic script to confirm
2. ❓ Company scoring → Verify score_breakdown field exists
3. ❓ NoneType errors on tech search → Check logs for specific error

**Next steps if issues remain:**
- Run diagnostic script and share output
- Check error logs: `tail -100 ~/zoektrends-dashboard/logs/error.log`
- Test individual components (BigQuery, scoring, chat service)

---

## Contact & Support

**GitHub Repository:** https://github.com/KamalidenovRustem/zoektrends-dashboard-django  
**Latest Commit:** 9e19ff0 (Fix Columbus Chat: null-safe score_breakdown, CSRF fix, diagnostics, nginx buffers)  
**Deployment Date:** December 2024

**Quick Access Commands:**
```bash
# Check service status
sudo systemctl status zoektrends-django

# View logs
tail -f ~/zoektrends-dashboard/logs/error.log

# Restart service
sudo systemctl restart zoektrends-django

# Run diagnostics
cd ~/zoektrends-dashboard && source venv/bin/activate && python test_server_columbus.py
```
