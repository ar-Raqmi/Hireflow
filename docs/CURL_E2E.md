# Hireflow — Online End-to-End (curl) Playbook

> Rule (AGENTS.md §16): no local-only anything. Every milestone is proven with curl
> against the **live Cloud Run URL**, with a real `.pdf` resume and the real Gemini
> model (Vertex AI). This file is the exact command sequence.

Live URL (after the next redeploy of `hireflow/`):

```text
BASE_URL=https://hireflow-backend-296941301245.us-central1.run.app
```

Redeploy note: the instance currently live returns `{"status":"ok"}` on `/health`
but was built before the pipeline wiring AND the SSE streaming — its
`/pipeline/run` answers `agent_not_configured` and `/upload` answers
`status:"stored"`. Upload this code, then the sequence below is the acceptance
test for the redeploy.

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
  "salary_floor": 8000,
  "skills": ["Python", "TensorFlow", "PyTorch", "Kubernetes"],
  "years_experience": 6.0,
  "residence": "Kuala Lumpur, Malaysia",
  "culture_keywords": ["fast-paced", "startup", "ownership"],
  "parse_errors": []
}
```

- `skills` / `years_experience` are **not empty** — they come from the real
  Gemini parse (text-only normally; Gemini vision page-images when the PDF's
  extracted text is thin, or when `RESUME_PARSE_MODE=vision`).
- HTTP 400 instead of this ⇒ either the extension is unsupported (only
  `.txt/.pdf/.docx` are accepted) or `work_type` is not one of
  `remote|hybrid|onsite|any`.
- If this pre-deploy build returns `"status":"stored"`, the new build is NOT deployed yet.

Grab the `id` from the response:

```bash
PROFILE_ID="<id from step 1>"
```

## 2. Run the pipeline — async, SSE live progress (the centerpiece)

The pipeline now runs **in the background**; `/pipeline/run` returns a `run_id`
immediately, and a second endpoint streams Server-Sent Events showing each
pipeline stage live:

```bash
RUN_ID="$(curl -s -X POST "$BASE_URL/pipeline/run?profile_id=$PROFILE_ID" \
  | python3 -c "import json,sys; print(json.load(sys.stdin).get('run_id',''))")"
echo "run_id: $RUN_ID"
```

**Expected output (proves the run started, returns instantly):**

```json
{"run_id":"<uuid>","profile_id":"<id>","status":"started"}
```

Then stream the live progress:

```bash
curl -N "$BASE_URL/pipeline/run/$RUN_ID/events"
```

**Expected output (proves the agent is actually working — live terminal proof):**

```text
event: started
data: {"run_id":"<uuid>","status":"started"}

data: {"seq":1,"stage":"parse","detail":"resume ready — 14 skills · 6.0 yrs · roles ['ML Engineer']","ts":...}

data: {"seq":2,"stage":"audit","detail":"ATS health 72/100 · 3 findings","ts":...}

data: {"seq":3,"stage":"search","detail":"freehire(Singapore,Kuala Lumpur,Tokyo): 12 found","ts":...}

data: {"seq":4,"stage":"search","detail":"remoteok: 9 found","ts":...}

data: {"seq":5,"stage":"search","detail":"remotive: 11 found","ts":...}

data: {"seq":6,"stage":"match","detail":"scoring 10 jobs… 5/10 done (best so far: 87 Acme · ML Engineer)","ts":...}

data: {"seq":7,"stage":"research","detail":"researching 3 companies… 2/3 done (Beta)","ts":...}

data: {"seq":8,"stage":"prepare","detail":"drafting CV + cover letter… 2/2 done (Acme · ML Engineer)","ts":...}

data: {"seq":9,"stage":"approve","detail":"2 drafted · 1 routed · 0 matched · 1 needs human","ts":...}

event: done
data: {"profile_id":"<id>","run_id":"<uuid>","status":"completed","jobs_found":32,"matches":[...],"applications":[...],"needs_human":[...],"errors":[...],"drafts":{...}}
```

**What proves success:**
- The stream shows every stage boundary (`parse` → `audit` → `search` →
  `match` → `research` → `prepare` → `approve`) with **counts + names**, not a
  silent wait.
- The final `event: done` carries the full result JSON:
  - `"status":"completed"` (NOT `agent_not_configured`)
  - `jobs_found > 0` and `matches` have real `score` 0–100 + `reasons` (Gemini called)
  - `applications` present for scores ≥ 60 (`drafted` for ≥ 80, `routed` for 60–79)
  - `drafts` contains a non-empty `cv` + `cover_letter` (Prepare stage ran)
- Non-fatal source failures degrade to `errors` entries and are shown as
  `search` stage events with `0 found` — never a 500.

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

CLI prints the styled report **after streaming live per-stage progress** — each
SSE event is printed with an elapsed clock (`[+12s] ▶ search …`), so you see the
agent working before the final report renders.

## What each curl proves is REAL Gemini running on Google Cloud

1. **Resume parse**: `/upload` returns non-empty `skills` + `years_experience` —
   a real Gemini extraction (vision page-rendering when text is thin).
2. **Live pipeline**: the SSE stream shows `match`/`research`/`prepare` stages
   advancing in real time with company/job names — a stub could not produce
   varied 0–100 scores with per-job reasons.
3. **Vertex AI**: `drafts` cv + cover letter are generated text.
4. **Cloud Run dashboard** confirms `/dashboard` `jobs_found`/`applications`
   grew — state changes via the exact HTTP surface the frontend will use.
5. Record this terminal-to-cloudrun session for the demo video, with Vertex AI
   logs on screen.

## Verification must-haves before declaring done (AGENTS.md §16)

- [ ] `curl $BASE_URL/health` → 200
- [ ] Step 1 upload `real_resume.pdf` → `parsed_and_stored` with non-empty `skills`
- [ ] Step 2 `pipeline/run` → `{"run_id":…,"status":"started"}`
- [ ] `curl -N …/events` streams stage events and ends with `event: done`
      → `completed` with jobs + matches ≥ 1
- [ ] `dashboard` reflects the run
- [ ] `approve` flips status
- [ ] CLI run prints live progress + a report `--url $BASE_URL`