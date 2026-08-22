# Hireflow — Online End-to-End (curl) Playbook

> Rule (AGENTS.md §16): no local-only anything. Every milestone is proven with curl
> against the **live Cloud Run URL**, with a real `.pdf` resume and the real Gemini
> model (Vertex AI). This file is the exact command sequence.

Live URL (after the next redeploy of `hireflow/`):

```text
BASE_URL=https://hireflow-backend-296941301245.us-central1.run.app
```

Redeploy note: the instance currently live returns `{"status":"ok"}` on `/health`
but was built before the pipeline wiring — its `/pipeline/run` answers
`agent_not_configured` and `/upload` answers `status:"stored"`. Upload this code,
then the sequence below is the acceptance test for the redeploy.

---

## 0. Health (proves Cloud Run is alive)

```bash
curl -s "$BASE_URL/health"
```

**Proves success:** `{"status":"ok"}` (HTTP 200).

## 1. Upload a real resume (PDF) + preferences

```bash
curl -s -X POST "$BASE_URL/upload" \
  -F "file=@./path/to/real_resume.pdf" \
  -F "work_type=hybrid" \
  -F "locations=Singapore,Kuala Lumpur,Tokyo" \
  -F "target_roles=ML Engineer,AI Engineer" \
  -F "salary_floor=8000"
```

### Expected output (new build)

```json
{
  "id": "f90c0622-b624-4417-9290-87bbc69516f5",
  "filename": "real_resume.pdf",
  "status": "parsed_and_stored",
  "pages": 2,
  "work_type": "hybrid",
  "locations": ["Singapore", "Kuala Lumpur", "Tokyo"],
  "target_roles": ["ML Engineer", "AI Engineer"],
  "salary_floor": 8000
}
```

- HTTP 400 instead of this ⇒ either the extension is unsupported (only
  `.txt/.pdf/.docx` are accepted) or `work_type` is not one of
  `remote|hybrid|onsite|any`.
- If this pre-deploy build returns `"status":"stored"`, the new build is NOT deployed yet.

Grab the `id` from the response:

```bash
PROFILE_ID="<id from step 1>"
```

## 2. Run the pipeline (server-side agent)

```bash
curl -s -X POST "$BASE_URL/pipeline/run?profile_id=$PROFILE_ID"
```

### Expected output (proves the agent really ran)

```json
{
  "profile_id": "<id>",
  "status": "completed",
  "jobs_found": 19,
  "matches": [
    {
      "rank": 1,
      "job_id": "ml-engineer-luxoft-eyq2ixao",
      "title": "ML Engineer",
      "company": "Luxoft",
      "source": "freehire",
      "post_url": "https://career.luxoft.com/jobs/...",
      "location": "Noida, IN",
      "score": 93,
      "reasons": ["...", "..."],
      "research": {"company": "...", "summary": "..."}
    }
  ],
  "applications": [
    {
      "id": "...", "job_id": "...", "title": "...", "company": "...",
      "status": "drafted", "score": 93,
      "human_handoff": false, "drafted": true
    }
  ],
  "needs_human": [],
  "errors": [],
  "drafts_ready": {
    "<job_id>": {
      "cv": "Tailored CV summary text…",
      "cover_letter": "Dear … covered letter text…"
    }
  },
  "pipeline": "search -> score -> research -> prepare -> approve"
}
```

**What proves success:**
- `"status":"completed"` (NOT `agent_not_configured`)
- `jobs_found > 0` and `matches` have real `score` 0–100 + `reasons` (Gemini called)
- `applications` present for scores ≥ 60 (`drafted` for ≥ 80, `routed` for 60–79)
- `drafts_ready` contains a non-empty `cv` + `cover_letter` (Prepare stage ran)

## 3. Read-back endpoints (proof of persistence)

```bash
curl -s "$BASE_URL/jobs" | python3 -c "import json,sys; d=json.load(sys.stdin); print('jobs:', len(d), '| first:', d[0]['title'] if d else 'none')"

curl -s "$BASE_URL/applications" | python3 -c "import json,sys; d=json.load(sys.stdin); print('apps:', len(d))"

curl -s "$BASE_URL/dashboard"
```

**Proves success:** `/jobs` shows the discovered postings, `/applications` shows a
`drafted`/`routed` item, `/dashboard` shows the counts with `jobs_found` > 0.

## 4. Human approval gate

```bash
APP_ID="<applications[0].id from step 3>"
curl -s -X POST "$BASE_URL/approve?application_id=$APP_ID"
```

**Proves success:** `{"id":"<app-id>","status":"approved"}`. Re-query
`/applications` to see the same id now `"approved"`.

---

## Terminal CLI (same flow, thin client)

```bash
python -m hireflow.cli ./real_resume.pdf \
  --work-type hybrid \
  --location Singapore \
  --location "Kuala Lumpur" \
  --target-role "ML Engineer" \
  --salary-floor 8000 \
  --url "$BASE_URL"
```

Interactive mode (mirrors the frontend's prefs modal — work-type dialog first,
then locations, then target roles, each skippable):

```bash
python -m hireflow.cli ./real_resume.pdf --url "$BASE_URL"
```

CLI prints the styled report: top matches with score + reasons, application
statuses, `needs human` jobs, and non-fatal source warnings.

## What each curl proves is REAL Gemini running on Google Cloud

1. **Vertex AI**: `drafts_ready` cv + cover letter are generated text (nothing a
   stub could produce).
2. **Match scoring** returns varied 0–100 scores with per-job reasons.
3. **Cloud Run dashboard** confirms `/dashboard` `jobs_found`/`applications`
   grew — state changes via the exact HTTP surface the frontend will use.
4. Record this terminal-to-cloudrun session for the demo video, with Vertex AI
   logs on screen.

## Verification must-haves before declaring done (AGENTS.md §16)

- [ ] `curl $BASE_URL/health` → 200
- [ ] Step 1 upload `real_resume.pdf` → `parsed_and_stored`
- [ ] Step 2 `pipeline/run` → `completed` with jobs + matches ≥ 1
- [ ] `dashboard` reflects the run
- [ ] `approve` flips status
- [ ] CLI run prints a report `--url $BASE_URL`