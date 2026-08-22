# Hireflow

Autonomous AI job-search agent for **All Things Agentic Hackathon 2026** (Taskmaster track).

**One-line identity:** *the agent never waits to be asked. It watches, decides, and acts — the human only approves.*

**Pipeline:** `Find → Analyze → Rank → Research → Prepare → Approve → Track`

---

## What's real right now (updated Aug 22, 2026)

- **Backend (FastAPI, Cloud Run):** `https://hireflow-backend-296941301245.us-central1.run.app`
  - `GET /health` → `{"status":"ok"}` — **live, verified**.
  - `POST /upload` — parses a real resume (`.txt/.pdf/.docx`) with `ResumeParser`
    and stores a `Profile` (work_type gate, locations, target roles, salary floor).
    Returns `status: "parsed_and_stored"` + `pages`.
  - `POST /pipeline/run?profile_id=…` — runs the **real agent end-to-end**
    (`search → score → research → prepare`) with **real Gemini** (Vertex AI first,
    API-key fallback), persists discovered jobs + applications, returns a summary.
    Capped for demo time: ≤25 jobs, ≤10 scored, ≤5 drafted (env-tunable).
  - `GET /dashboard`, `GET /jobs`, `GET /applications`, `POST /approve?application_id=…`.
- **Agent:** Google ADK `LlmAgent` (`hireflow_router`) + 4 `FunctionTool`s
  (search / score / research / prepare). Deterministic pipeline runner wired
  through the same tools: `HireflowAgent.run_pipeline`.
- **Job sources (all keyless, failure-tolerant — a down board returns `[]`):**
  - `FreehireSource` → `https://freehire.me/api/v1/agent/jobs/search`
    (`q`, `countries`/`regions`, `work_mode`, `posted_within_days`,
    `include_description`). **Live verified Aug 22** (200, `regions=apac`,
    `countries=my` return real rows; 193-country coverage).
  - `RemoteOKSource`, `RemotiveSource` — **live verified** (`curl` 200; parses
    `posted_at` + `raw_data`).
- **CLI:** `python -m hireflow.cli resume.pdf [--work-type … --location … --target-role …]`
  — thin client that uploads to the deployed API, runs the pipeline server-side,
  prints a styled report. No pipeline logic reimplemented in the client.
- **Verification (online-e2e only):** no offline tests. Every milestone is proven
  with curl against the live URL (see `docs/CURL_E2E.md`) using a real `.pdf`
  resume and the real Gemini model via Vertex AI — no mocks, stubs, or stand-ins.
- **Frontend:** `hireflow-frontend.html` is a mock UI (not yet wired via fetch).

### Sources still awaiting curl verification
- Google Custom Search (CSE) catch-all, JSON-LD career-page parsing, LinkedIn
  guest API, Playwright/Chromium (Layer II) — designed in AGENTS.md §10, **not yet
  implemented or verified**. Do not claim "global" from this milestone alone;
  freehire is the spatial floor.

## Architecture

> ASCII diagram below (dev reference). **TODO:** export a clean PNG/draw.io
> architecture image for the submission (judges look for a clear visual
> representation — RULES.md §124).

```
[User] → [hireflow-frontend.html → fetch] → [FastAPI /pipeline/run]
                                                 │
                          ┌──────────────────────┼──────────────────────┐
                          ▼                      ▼                      ▼
                   SearchAgent            MatchAgent              ResearchAgent
                   global sources        score_fit (Gemini)      company_research
                          │                      │                      │
                          └──────────────────────┼──────────────────────┘
                                                 ▼
                                        PrepareAgent: DRAFT → REVIEW → REVISE
                                                 ▼
                                        [ HUMAN APPROVAL GATE /approve ]
                                                 ▼
                          Browser localStorage (history + tracking) — no DB
```

Backend is **stateless and in-memory per run** (nothing sensitive stored
server-side; browser `localStorage` owns prefs + history). Cloud Run scales to
zero. Storage: `InMemoryRepository` by default; `FirestoreRepository` optional
(opt-in via `HIREFLOW_STORAGE=firestore`).

---

## Requirements

- Python 3.11+ (developed on 3.14).
- Google Cloud: project `hireflow-506207`, **Vertex AI** enabled, service-account
  JSON on disk, or `GEMINI_API_KEY` as API-key fallback. **No DB needed.**

## Setup (local dev)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # fill GCP_PROJECT_ID / GOOGLE_APPLICATION_CREDENTIALS / GEMINI_API_KEY
```

## Run the CLI against the live backend

```bash
python -m hireflow.cli ./real_resume.pdf \
  --work-type hybrid --location Singapore --target-role "ML Engineer" --url https://hireflow-backend-296941301245.us-central1.run.app
```

Interactive (mirrors the frontend's prefs modal): `python -m hireflow.cli resume.pdf --url BASE_URL`.

The same flow as a bash driver (no Python needed):
`./hireflow.sh` — prompts for resume + prefs, uploads, runs, prints the report.

## Deploy to Cloud Run

Handed off to Zach — single command + IAM grant in `docs/DEPLOY.md`:

```bash
gcloud run deploy hireflow-backend --region us-central1 --source . \
  --allow-unauthenticated \
  --set-env-vars GCP_PROJECT_ID=hireflow-506207,GEMINI_USE_VERTEX=true,VERTEX_LOCATION=global,GEMINI_MODEL=gemini-3.5-flash
```

(`docs/DEPLOY.md` also has the one-time `roles/aiplatform.user` grant that lets
the Cloud Run runtime SA call Vertex AI — without it every Gemini call 401s.)

## Verify online (end-to-end)

`docs/CURL_E2E.md` — the exact curl sequence against the live URL
(upload → run → jobs → applications → approve) plus what each response must
contain to count as success: `https://github.com/ar-Raqmi/Hireflow/blob/main/docs/CURL_E2E.md`

---

*Built during the All Things Agentic Hackathon 2026 Submission Period (Aug 3–31).*