# GCP setup runbook (one-time, ~30–45 min)

Everything Hireflow needs from GCP, step by step. Each step has a "why" and a
**"you're done when"** check so you know it worked. Copy-paste friendly.

**Project:** `hireflow-506207` · **Region:** `us-central1` · **Today:** 2026-08-23

> Heads-up: Google renamed things. "Vertex AI" is now marketed as **Gemini
> Enterprise Agent Platform**, and search is **Agent Search**. URLs below are the
> current live ones. Don't be thrown by the new names.

---

## 0. Preflight (I'm authenticated, project is right)

```bash
gcloud config set project hireflow-506207
gcloud auth print-access-token >/dev/null && echo AUTH_OK
gcloud projects describe hireflow-506207 --format='value(projectId)' && echo PROJECT_OK
```
✅ Both print `..._OK` → continue.

---

## 1. Enable the APIs (one command)

```bash
gcloud services enable \
  run.googleapis.com \
  aiplatform.googleapis.com \
  discoveryengine.googleapis.com \
  cloudbuild.googleapis.com
```
- `aiplatform` = Gemini + **embeddings** (the vector search).
- `discoveryengine` = **Agent Search** (career-page search, the CSE replacement).
- `run` + `cloudbuild` = Cloud Run deploy from source.

✅ Check: `gcloud services list --enabled | grep -E "run|aiplatform|discoveryengine"`

---

## 2. Grant the Cloud Run runtime service account Vertex permission

The app's pipeline calls Gemini/embeddings from Cloud Run **as itself** via the
runtime SA — it needs `roles/aiplatform.user` or every call is 401/403.

```bash
SA="$(gcloud projects describe hireflow-506207 --format='value(projectNumber)')-compute@developer.gserviceaccount.com"
gcloud projects add-iam-policy-binding hireflow-506207 \
  --member "serviceAccount:$SA" --role roles/aiplatform.user
```

✅ We'll verify implicitly in §5 (the app's `/health` plus a real run).

---

## 3. Create the site-search data store (Agent Search, ≤50 job domains)

The old "Custom Search JSON API" is **closed to new customers** (Google said it —
transition by Jan 1 2027; new signups can't use it). Google's recommended
replacement for searching ≤50 domains is **Agent Search** via Discovery Engine.

1. Open the console:
   `https://console.cloud.google.com/gen-app-builder/data-stores/create`
   (already on `hireflow-506207`).
2. Under **Website Content**, click **Select**.
3. Turn **ON** the **Advanced website indexing** toggle.
4. In **URL patterns to index** → **Sites to include**, add the career/job
   domains you want the agent to search. Start with these (patterns):
   ```
   https://www.mycareersfuture.gov.sg/*
   https://www.glassdoor.com/*
   https://www.jobstreet.com.my/*
   https://www.jobstreet.com.sg/*
   https://www.kalibrr.com/*
   https://www.wantedly.com/*
   https://www.greenhouse.io/careers/*
   https://jobs.ashbyhq.com/*
   ```
   (You can add/curate more later — up to 50.)
5. **Data store location:** choose **`global`** (used by the docs + our API calls).
6. Name it: `hireflow-jobs` → the **Data store ID** is auto-generated. **Copy the
   ID** (you'll hand it to the team).
7. **Create.**

✅ Check: it appears under
`https://console.cloud.google.com/gen-app-builder/data-stores` with ID visible.

**You now have the equivalent of our old "CSE key + engine ID."** Share the
**datastore ID** (looks like `hireflow-jobs-...`) — we call it `AGENT_SEARCH_DATASTORE`.

> 💡 Why not the new Custom Search JSON API? It's closed to new signups today.
> Agent Search is Google's supported path and it gives us a vector-backed,
> domain-restricted web search — better for "find jobs on company / job sites".

---

## 4. Verify embeddings work (vector search)

The app's semantic re-ranking uses a Vertex embedding model (`gemini-embedding-001`).
Confirm it's callable with **your** credentials:

```bash
mkdir -p /tmp/hl && cat > /tmp/hl/req.json <<'EOF'
{
  "instances": [ { "content": "machine learning engineer" } ],
  "parameters": { "autoTruncate": true }
}
EOF

curl -X POST \
  -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  -H "Content-Type: application/json; charset=utf-8" \
  -d @/tmp/hl/req.json \
  "https://us-central1-aiplatform.googleapis.com/v1/projects/hireflow-506207/locations/us-central1/publishers/google/models/gemini-embedding-001:predict"
```

✅ Done (expected): a JSON `predictions[0].embeddings.values[...]` array. If you get
`PERMISSION_DENIED` → grant `aiplatform.user` (step 2) to *your* account too. If
`NOT_FOUND` on `gemini-embedding-001` → let us know, we'll pick `text-embedding-005`.

---

## 5. Redeploy Cloud Run (bigger instance + long timeout + new env)

The pipeline now does Gemini + embeddings + (optionally) site-search + Playwright
rendering. It needs more memory and a long request timeout, and it must be public
for `curl`/CLI e2e.

```bash
gcloud run deploy hireflow-backend \
  --region us-central1 \
  --source . \
  --allow-unauthenticated \
  --service-account <SA-email-from-step-2> \
  --memory 1Gi --cpu 1 \
  --timeout 3600 \
  --set-env-vars \
    GCP_PROJECT_ID=hireflow-506207, \
    GEMINI_USE_VERTEX=true, \
    VERTEX_LOCATION=global, \
    GEMINI_MODEL=gemini-3.5-flash, \
    RESUME_PARSE_MODE=hybrid, \
    QUERY_EXPANSION=true, \
    JOB_RECENCY_DAYS=14, \
    DIVERSITY_MAX_SAME_COMPANY=2, \
    AGENT_SEARCH_DATASTORE=<the-datastore-id-from-step-3>
```

- `--memory 1Gi` + `--timeout 3600` → needed for Chromium (Playwright) + long
  async runs. (Default 300s WILL kill the ~7–10 min pipeline; we already hit that.)
- `--source .` builds the `Dockerfile` via Cloud Build (`.dockerignore` keeps
  secrets out).
- If Chromium/Playwright is enabled later, bump to `--memory 2Gi --cpu 2`.

✅ Done: `curl -s https://hireflow-backend-296941301245.us-central1.run.app/health` → `{"status":"ok"}`.

---

## If something breaks

| Symptom | Fix |
|---|---|
| App boots, Gemini 401/403 | missing `roles/aiplatform.user` on the run SA (step 2) |
| `agent_not_configured` | old build — redeploy (step 5) |
| Embeddings 404 | model name env (`EMBEDDING_MODEL=text-embedding-005`) |
| Pipeline times out | `--timeout 3600` not set → rerun step 5 |
| Site-search not matching | datastore needs `Advanced website indexing` on + let it index (~24h) |

---

*This runbook was generated from live Google Cloud docs (2026-08-23). Re-verify
URLs if they drift — Google renames products often.*