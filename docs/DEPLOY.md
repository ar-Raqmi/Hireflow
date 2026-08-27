# Hireflow - Cloud Run redeploy (for Izaaz)

Target: the **existing** Cloud Run service `hireflow-backend` in `us-central1`
(project `hireflow-506207`) - the one already serving
`https://hireflow-backend-296941301245.us-central1.run.app`. Redeploying updates
it in place; the URL does not change. No secrets are needed on the command line
(ADC / runtime SA handles Vertex auth).

## 0. One-time: confirm APIs + runtime SA permission

```bash
gcloud config set project hireflow-506207
gcloud services enable run.googleapis.com aiplatform.googleapis.com

# Give the Cloud Run runtime service account permission to call Vertex AI.
# (Default runtime SA = <PROJECT_NUMBER>-compute@developer.gserviceaccount.com)
gcloud projects add-iam-policy-binding hireflow-506207 \
  --member "serviceAccount:$(gcloud projects describe hireflow-506207 --format='value(projectNumber)')-compute@developer.gserviceaccount.com" \
  --role roles/aiplatform.user
```

Without `roles/aiplatform.user` the app boots but every Gemini call fails with
401/PERMISSION_DENIED on Vertex. If you deployed with a custom `--service-account`,
grant the role to that SA instead.

## 1. Redeploy (single command)

```bash
gcloud run deploy hireflow-backend --region us-central1 --source . \
  --allow-unauthenticated \
  --set-env-vars GCP_PROJECT_ID=hireflow-506207,GEMINI_USE_VERTEX=true,VERTEX_LOCATION=global,GEMINI_MODEL=gemini-3.5-flash,RESUME_PARSE_MODE=hybrid \
  --memory 1Gi --timeout 3600
```

- `--source .` builds the `Dockerfile` via Cloud Build. `.dockerignore`
  excludes `.env`, `API.md`, `*-credential.json`, `.venv`, etc. from the build
  context.
- `--memory 1Gi --timeout 3600` - Chromium (Playwright) is installed in the
  image, and the pipeline streams SSE progress from a background task; the
  request must stay open while the client drains `/events`, so give it room
  (Cloud Run max is 3600s). Bump to `--memory 2G --cpu 2` under heavy Playwright
  load.
- `RESUME_PARSE_MODE` - `hybrid` (default): Gemini text parse, upgraded to
  Gemini **vision** page-images when the PDF's extracted text is thin;
  `vision`: always render PDF pages + Gemini vision; `text`: text-only parse.
- Optional tuning (defaults are fine for the demo):
  `PIPELINE_MAX_JOBS=60`, `PIPELINE_MAX_SCORE=60`, `PIPELINE_MAX_PREP=5`,
  `PIPELINE_MAX_RESEARCH=10`, `PIPELINE_MIN_MATCHES=10`, `PIPELINE_SCORE_BATCH=10`,
  `PIPELINE_MAX_SEARCH_SWEEPS=3`, `FREEHIRE_POSTED_WITHIN_DAYS=14`.

## 2. Verify

```bash
curl -s https://hireflow-backend-296941301245.us-central1.run.app/health
# {"status":"ok"}
```

Then verify the **watcher body-path** is live (added 2026-08-27 - the frontend
auto-check depends on it). This must return a `run_id` (not a 422 / `missing
profile_id`):

```bash
curl -s -X POST https://hireflow-backend-296941301245.us-central1.run.app/pipeline/run \
  -H "Content-Type: application/json" \
  -d '{"profile":{"work_type":"any","target_roles":["Engineer"],"resume_text":"demo"}}'
```

The one-command redeploy in §1 (with `--source .`) picks up the code change -
no new flags are needed.

Then run the full acceptance sequence in `docs/CURL_E2E.md`
(upload → pipeline/run → jobs → applications → approve). Watch the service logs
for Vertex calls:

```bash
gcloud run services logs read hireflow-backend --region us-central1 --limit 50
```

Screen-capture the console/logs for the demo video.
