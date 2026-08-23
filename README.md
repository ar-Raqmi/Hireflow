# Hireflow

Autonomous AI job-search agent for **All Things Agentic Hackathon 2026** (Taskmaster track).

> *"The agent never waits to be asked. It watches, decides, and acts — the human only approves."*

Pipeline: `Find → Analyze → Rank → Research → Prepare → Approve → Track`

by ar-Raqmi and Izaaz

---

## What is real now (2026-08-23)

### Live
- **Cloud Run backend** — `https://hireflow-backend-296941301245.us-central1.run.app` — `/health` returns `{"status":"ok"}` (verified Aug 22). Note: the **live build predates** the RouterAgent pipeline, SSE streaming, AND the search-intelligence pass (its `/pipeline/run` answers `agent_not_configured`). The new build below is the acceptance target — redeploy with `docs/DEPLOY.md`, then prove it with `docs/CURL_E2E.md`.
- **Keyless job-source registry (curl-verified):** freehire (193 countries), RemoteOK, Remotive, LinkedIn guest search, JSON-LD career pages, ATS boards (Greenhouse GitLab 204 jobs, Ashby Notion 128 jobs). Lever (404) and Workable (0 jobs) are coded but disabled.

### Implemented in code — live proof pending redeploy + curl e2e
- **Agent pipeline** — Five agents (Search → Match → Research → Prepare, orchestrated by RouterAgent) run server-side through `GeminiClient` (Vertex AI, Gemini 3.5 Flash — the only LLM entry point, no stubs/mocks). `/pipeline/run` is async and streams per-stage progress over SSE; `/upload` does a real Gemini resume parse (text, or vision via PyMuPDF page images when text is thin).
- **Search intelligence** — `QueryExpander` (Gemini synonym expansion per role + deterministic fallback), multiple query variants per source (seed-rotated so runs vary), gate-then-cap (work-type + **location** + **recency**), cross-run seen-job dedup (`?seen=` from browser `localStorage`), per-company diversity cap (max 2/company). Knobs in `hireflow/config.py`: `QUERY_EXPANSION`, `QUERY_EXPANSION_TERMS`, `JOB_RECENCY_DAYS`, `DIVERSITY_MAX_SAME_COMPANY`, `USE_UNVERIFIED_SOURCES`, `FREEHIRE_SOURCES`.
- **Johor/Israel false-global bug FIXED in code** — `Johor` now maps to `my` (`geo.py`), and an unmapped location no longer silently widens freehire to a global onsite search. Needs redeploy to prove live.
- **APAC relays** — freehire `source=seek` (JobStreet engine → MY/ID/SG/AU/NZ) and `source=mycareersfuture` (SG) are wired in via `FreehireRegionalSource`, registered by default. Wantedly + JapanDev (JP) are in the tree but flag-gated (`USE_UNVERIFIED_SOURCES=1`).
- **Clients** — `hireflow.sh` / `hireflow.bat` → `hireflow_run.py`, and `python -m hireflow.cli` are thin clients of the deployed API; after a run they export `result-demo.html` + `result-demo.json` (full self-contained report, clickable links, no truncation).

### In flight (not in this tree yet — verify before trusting)
- Universal **webfetch + discovery** layer (`webfetch.py`/`discovery.py`) — the keyless catch-all replacing the retired CSE 50-site whitelist; no 50-domain whitelist.
- **Embeddings re-rank** (`embeddings.py`, `gemini-embedding-001`; `text-embedding-005` fallback) — knob documented in `docs/GCP_SETUP.md` §4.
- **Real-submit sandbox ATS** — `/sandbox/ats/apply`, `ApplicationStatus.SUBMITTED`, `/approve` submitting for real. Today `/approve` only flips status to `approved`.
- **Layer II Playwright** — scaffolded/opt-in only (`HIREFLOW_PLAYWRIGHT=1`); Chromium is not in the Dockerfile yet.
- **Agent Search** (formerly CSE) — **optional**, not set up. Only indexes domains you can verify you own (`docs/GCP_SETUP.md` §3). Not needed for the core pipeline.

## Docs
- `docs/CURL_E2E.md` — exact curl acceptance playbook (upload → run → SSE → jobs → approve) against the live URL.
- `docs/DEPLOY.md` — one-command Cloud Run redeploy + Vertex IAM grant.
- `docs/GCP_SETUP.md` — one-time GCP runbook: APIs, SA grant, embeddings check, optional Agent Search, big-instance deploy.

## Stack
- **Gemini 3.5 Flash** via Vertex AI — `hireflow/config.py`
- **Google ADK** (Python) — `hireflow/agents/adk_router.py` (LlmAgent graph + FunctionTools)
- **FastAPI** backend — `hireflow/api/app.py` (stateless, in-memory per run; no DB)
- **Cloud Run** (scale-to-zero) — `Dockerfile`
- Frontend: **Vite + React** (planned — `hireflow-frontend.html` is the reference prototype only)

## Hackathon compliance (see RULES.md)
Gemini 3.5+ via Vertex AI ✓ · Google ADK ✓ · Cloud Run ✓ · hosted public URL ✓ · open GitHub repo ✓ · README spin-up ✓ · architecture diagram in AGENTS.md (clean image pending) · ≤4-min demo video (pending) · repo access for `testing@devpost.com` + `cloudhackathons@google.com` (pending).