# GCP setup runbook (one-time, ~30–45 min)

Everything Hireflow needs from GCP, step by step. Each step has a "why" and a
**"you're done when"** check so you know it worked. Copy-paste friendly.

**Project:** `hireflow-506207` · **Region:** `us-central1` · **Today:** 2026-08-23

> **Verified against live Google Cloud docs:** 2026-08-23.
> Re-verify URLs if they drift - Google renames products often. Current naming:
> **Vertex AI** → **Gemini Enterprise Agent Platform**; **Vertex AI Search** →
> **Agent Search** (console = **AI Applications**). The underlying service/API
> IDs are unchanged.

> 💡 **ARCHITECTURE NOTE - §3 is OPTIONAL. Don't block on it.**
> Agent Search website indexing only works on domains **you can verify you own**
> (or get the domain owner to approve). It is NOT a keyless way to index
> third-party job boards like glassdoor/jobstreet/kalibrr. The core Hireflow
> search pipeline does NOT depend on §3 at all - it pulls jobs directly from
> freehire, RemoteOK, Remotive, ATS boards (Greenhouse/Ashby), JSON-LD career
> pages, and LinkedIn guest search. If you hit a billing or verification wall in
> §3, **skip it and continue** - it's a nice-to-have supplement, not a blocker.

---

## 0. Preflight (I'm authenticated, project is right)

`gcloud` is still the current CLI (now marketed as the "Google Cloud CLI" - the
command name is unchanged).

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
- `aiplatform` = Gemini + **embeddings** (the vector search). This is still the
  correct service ID even though the product is marketed as "Gemini Enterprise
  Agent Platform".
- `discoveryengine` = **Agent Search** (the CSE replacement; the API is still
  `discoveryengine.googleapis.com` even though the console UI is now "AI
  Applications").
- `run` + `cloudbuild` = Cloud Run deploy from source.

✅ Check: `gcloud services list --enabled | grep -E "run|aiplatform|discoveryengine"`

---

## 2. Grant the Cloud Run runtime service account Vertex permission

The app's pipeline calls Gemini/embeddings from Cloud Run **as itself** via the
runtime SA. By default Cloud Run uses the project's Compute Engine default
service account, which is `<projectNumber>-compute@developer.gserviceaccount.com`.
It needs `roles/aiplatform.user` (shown as "Agent Platform User" in the console
now - the role ID is unchanged) or every model/embedding call returns 401/403.

```bash
SA="$(gcloud projects describe hireflow-506207 --format='value(projectNumber)')-compute@developer.gserviceaccount.com"
gcloud projects add-iam-policy-binding hireflow-506207 \
  --member "serviceAccount:$SA" --role roles/aiplatform.user
```

✅ We'll verify implicitly in §4 and §5 (the `/health` plus a real run).
- If the org was created after May 3 2024, the default SA may **not** be
  auto-granted any role - this binding is what fixes that.

---

## 3. OPTIONAL - create a website-search data store (Agent Search)

**Why it changed from the old note:** the retired Custom Search JSON API let you
scope a search to up to ~50 sites keyless. Agent Search site search is NOT
keyless for that - a website data store with **Advanced website indexing only
indexes domains you can verify** (Search Console ownership, or a domain-owner
association request). It also requires **billing enabled**, and you must attach
the data store to an app with **Enterprise Edition on** (extra cost). Indexed
pages count against the project's "Number of documents" quota.

**The core Hireflow search does not need this.** Do §0–§2 and §5–§6 first.
Come back here only if you own the sites you want to index (e.g. a demo domain).

If you want to try it, the current flow:

1. Open the **AI Applications** console (Agent Search):
   `https://console.cloud.google.com/gen-app-builder/`
2. In the navigation menu, click **Data Stores** → **Create data store**.
3. On the **Website** page, choose **Website Content**.
4. Decide whether to turn on **Advanced website indexing**. Needed for
   summarization / follow-up answers; costs extra, requires domain
   verification, and **can't be turned off later**.
5. In **Sites to include**, add one URL pattern per line, no protocol prefix -
   e.g. `example.com/careers/*`. Add exclusions in **Sites to exclude** to stop
   dynamic-URL bloat (sitemap-discovery mode can grow the index + storage cost).
6. **Data store location:** choose **global (Global)** - the sites must be
   public and global gives the best availability.
7. Name it `hireflow-jobs` → **Create**. Copy the auto-generated **Data store
   ID** (looks like `hireflow-jobs-...`) - the optional Agent Search ID. It is
   **not read by the app code yet** (Agent Search stays optional/unwired).
8. After create, **verify the domains** you listed (Data page → Website tab →
   **Verify**). Indexing only starts after verification, and large sites may
   exceed the default page quota (upgrade via quota request if so).

✅ Check: it appears under `https://console.cloud.google.com/gen-app-builder/`
→ **Data Stores** with the ID visible.

> If you can't verify a domain or don't want the cost - **skip this step.** The
> core pipeline works without it.

---

## 4. Verify embeddings work (vector search)

The app's semantic re-ranking uses a Vertex embedding model. The current
flagship is `gemini-embedding-001` (3072-dim; unifies `text-embedding-005` and
`text-multilingual-embedding-002`). Confirm it's callable with **your**
credentials:

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

✅ Done (expected): a JSON `predictions[0].embeddings.values[...]` array.
- `PERMISSION_DENIED` → grant `aiplatform.user` (step 2) to your account too.
- `NOT_FOUND` on `gemini-embedding-001` → fall back to `text-embedding-005`
  (768-dim, still available; set `EMBEDDING_MODEL` accordingly).
- Note: `gemini-embedding-001` accepts **one input text per request**; the curl
  above sends one, so it's fine.

---

## 5. Redeploy Cloud Run (bigger instance + long timeout + new env)

The pipeline now does Gemini + embeddings + (optionally) Agent Search + site
search + Playwright rendering. It needs more memory and a long request timeout,
and it must be public for `curl`/CLI e2e.

```bash
gcloud run deploy hireflow-backend \
  --region us-central1 \
  --source . \
  --allow-unauthenticated \
  --service-account "$(gcloud projects describe hireflow-506207 --format='value(projectNumber)')-compute@developer.gserviceaccount.com" \
  --memory 1Gi --cpu 1 \
  --timeout 3600 \
  --set-env-vars GCP_PROJECT_ID=hireflow-506207,GEMINI_USE_VERTEX=true,VERTEX_LOCATION=global,GEMINI_MODEL=gemini-3.5-flash,RESUME_PARSE_MODE=hybrid,QUERY_EXPANSION=true,JOB_RECENCY_DAYS=14,DIVERSITY_MAX_SAME_COMPANY=2
```

- `--memory 1Gi` + `--timeout 3600` → needed for Chromium (Playwright) + long
  async runs. (Default 300s WILL kill the ~7–10 min pipeline; we already hit
  that.)
- `--source .` builds the `Dockerfile` via Cloud Build (`.dockerignore` keeps
  secrets out).
- **`--set-env-vars` gotcha:** it takes ONE comma-separated `KEY=VALUE` list
  with **no trailing commas and no spaces**. Keep it on a single line as above.
- Cloud Run listens on **port 8080 by default** - the FastAPI app must bind 8080
  (or pass `--port`).
- If Chromium/Playwright is enabled later, bump to `--memory 2G --cpu 2`.

✅ Done: `curl -s https://hireflow-backend-296941301245.us-central1.run.app/health` → `{"status":"ok"}`

---

## If something breaks

| Symptom | Fix |
|---|---|
| App boots, Gemini 401/403 | missing `roles/aiplatform.user` on the run SA (step 2) |
| `agent_not_configured` | old build - redeploy (step 5) |
| Embeddings 404 | model name env (`EMBEDDING_MODEL=text-embedding-005`) |
| Pipeline times out | `--timeout 3600` not set → rerun step 5 |
| Agent-search not matching | domain not verified - Advanced indexing only indexes domains you can verify; skip §3 (core search is unaffected) |

---

*Verified against live Google Cloud docs on 2026-08-23. URLs and product names
drift - re-check before a demo. Bismillah.*
