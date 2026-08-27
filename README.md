# Hireflow

Autonomous AI job-search agent for **All Things Agentic Hackathon 2026** (Taskmaster track).

> *"The agent never waits to be asked. It watches, decides, and acts - the human only approves."*

Pipeline: `Find → Analyze → Rank → Research → Prepare → Approve → Track`

by ar-Raqmi and Izaaz

---

## What is real now (2026-08-25)

### Live
- **Cloud Run backend** - `https://hireflow-backend-296941301245.us-central1.run.app` - `/health` returns `{"status":"ok"}` (verified Aug 22). The **deployed build still answers `agent_not_configured` on `/pipeline/run`** until the new build (RouterAgent pipeline + SSE + search intelligence) is redeployed - that redeploy is the remaining acceptance step (`docs/DEPLOY.md`, then prove with `docs/CURL_E2E.md`).
- **Keyless job-source registry (curl-verified):** freehire (193 countries), RemoteOK, Remotive, LinkedIn guest search, JSON-LD career pages, ATS boards (Greenhouse GitLab 204 jobs, Ashby Notion 128 jobs). Lever (404) and Workable (0 jobs) are coded but disabled.
- **Vite + React frontend (`frontend/`) built + verified live** (2026-08-25) - `npm install && npm run build` passes. **Rebuilt on the M3E (Material 3 Expressive) component library** (`@m3e/react`): the app is wrapped in `<M3eTheme color="#8F4100" scheme="light" motion="expressive">` (Hireflow's ember brand primary drives the full Material 3 palette), with M3E buttons, dialog (prefs), tabs, icons, chips, snackbar, progress indicators, segmented button, **`M3eSelect`/`M3eOption` sort** and **`M3eFilterChip`/`M3eFilterChipSet` source filters**. The custom dropzone + SSE timeline stay custom markup themed via `var(--md-sys-color-primary)`. Verified in a headless-Chromium render: all M3E web components upgrade, no console errors, tabs + dialog + segmented-select interactions work. Wired to the live backend via `fetch`: resume upload → `/api`, **adaptive SSE agent timeline (animates from the real streamed events)**, and localStorage run history. **Auto-runs the pipeline on upload.** **Views: Agent run / Results / History** (no separate Applications tab). **Results** shows ranked matches with a **M3E circular-progress score (number only, no `/100`)**, rank label, **Open Link**, an expandable **View Draft (CV + cover letter from the done payload `drafts[job_id]`)**, collapsed-by-default reasons + research (rendered as markdown via `marked`), and **client-side filters** (sort by score/company/date, per-source chips, "has draft"). `ApplicationsList` + `ScoreDial` are deleted (application status is shown inline on each match card). Base URL via `VITE_HIREFLOW_API` (dev proxy in `vite.config.js`). `hireflow-frontend.html` is retired as the reference prototype. Remaining: prove the same run against the deployed `.run.app` URL after the redeploy.

### Implemented in code - live proof on the `.run.app` URL still needs Zach's redeploy
- **Agent pipeline** - Five agents (Search → Match → Research → Prepare, orchestrated by RouterAgent) run server-side through `GeminiClient` (Vertex AI, Gemini 3.5 Flash - the only LLM entry point, no stubs/mocks). `/pipeline/run` is async and streams per-stage progress over SSE; `/upload` does a real Gemini resume parse (text, or vision via PyMuPDF page images when text is thin). Pipeline + SSE stream run live end-to-end (the frontend timeline animates from the real events).
- **Search intelligence** - `QueryExpander` (Gemini synonym expansion per role + deterministic fallback), multiple query variants per source (seed-rotated so runs vary), gate-then-cap (work-type + **location** + **recency**), cross-run seen-job dedup (`?seen=` from browser `localStorage`), per-company diversity cap (max 2/company). Knobs in `hireflow/config.py`.
- **Johor/Israel false-global bug FIXED in code** - `Johor` maps to `my` (`geo.py`); an unmapped location no longer silently widens freehire to a global onsite search.
- **Career-page company sourcing** - after matching, `CareerSourceAgent` probes each distinct top-matched company's `/careers` page + ATS boards via `WebFetchSource.webfetch_company` and merges the new jobs back into the pipeline.
- **Universal webfetch + discovery layer** - `webfetch.py`/`discovery.py`, the keyless catch-all replacing the retired CSE 50-site whitelist; `WebFetchSource` is used by the career-page step. **Embeddings re-rank** (`embeddings.py`, `gemini-embedding-001`; `text-embedding-005` fallback) gated by `SEMANTIC_SEARCH`.
- **Real-submit sandbox ATS** - `/sandbox/ats/apply`, `ApplicationStatus.SUBMITTED`, and `/approve` submitting for real (records `ats_confirmation`).
- **Layer II Playwright/Chromium** - `browser.py`/`jobstreet.py` share `browser_launcher.py` stealth helpers; Chromium is installed in the `Dockerfile` (`HIREFLOW_PLAYWRIGHT=1`).
- **APAC relays** - freehire `source=seek` (JobStreet engine → MY/ID/SG/AU/NZ) and `source=mycareersfuture` (SG) wired in via `FreehireRegionalSource`, registered by default. Wantedly + JapanDev (JP) are in the tree but flag-gated (`USE_UNVERIFIED_SOURCES=1`).
- **Clients** - `hireflow.sh` / `hireflow.bat` → `hireflow_run.py`, and `python -m hireflow.cli` are thin clients of the deployed API; after a run they export `result-demo.html` + `result-demo.json`.
- **Agent Search** (formerly CSE) - **optional**, not set up. Only indexes domains you can verify you own (`docs/GCP_SETUP.md` §3). Not needed for the core pipeline.

## Docs
- `docs/CURL_E2E.md` - exact curl acceptance playbook (upload → run → SSE → jobs → approve) against the live URL.
- `docs/DEPLOY.md` - one-command Cloud Run redeploy + Vertex IAM grant.
- `docs/GCP_SETUP.md` - one-time GCP runbook: APIs, SA grant, embeddings check, optional Agent Search, big-instance deploy.

## Frontend (Vite + React)

```bash
cd frontend
npm install
npm run build        # production build → frontend/dist
npm run dev          # dev server; /api/* proxied to VITE_HIREFLOW_API (default: the live Cloud Run URL)
```

Set `VITE_HIREFLOW_API=https://hireflow-backend-296941301245.us-central1.run.app` at build time to point the production bundle at the deployed backend. The app calls the **real** API endpoints (`/upload`, `/pipeline/run`, SSE `/pipeline/run/{id}/events`, `/jobs`, `/applications`, `/approve`) - no mock or hardcoded job data. Prefs + run history live in browser `localStorage` (backend stays stateless). `hireflow-frontend.html` is the retired reference prototype only.

## Stack
- **Gemini 3.5 Flash** via Vertex AI - `hireflow/config.py`
- **Google ADK** (Python) - `hireflow/agents/adk_router.py` (the live orchestrator: `LlmAgent` + `Runner` expose the multi-agent `RouterAgent` as a `FunctionTool`)
- **FastAPI** backend - `hireflow/api/app.py` (stateless, in-memory per run; no DB)
- **Cloud Run** (scale-to-zero) - `Dockerfile`
- Frontend: **Vite + React** (`frontend/`) - wired to the live backend via fetch; `hireflow-frontend.html` is the retired reference prototype only

## Hackathon compliance (see RULES.md)
Gemini 3.5+ via Vertex AI ✓ · Google ADK ✓ · Cloud Run ✓ · hosted public URL ✓ · open GitHub repo ✓ · README spin-up ✓ · architecture diagram in AGENTS.md (clean image pending) · ≤4-min demo video (pending) · repo access for `testing@devpost.com` + `cloudhackathons@google.com` (pending).
