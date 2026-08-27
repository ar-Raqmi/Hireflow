# Hireflow

Autonomous AI job-search agent for **All Things Agentic Hackathon 2026** (Taskmaster track).

> *"The agent never waits to be asked. It watches, decides, and acts - the human only approves."*

Pipeline: `Find → Analyze → Rank → Research → Prepare → Approve → Track`

Hireflow is a **watcher**, not a chatbot. You upload a résumé once; the agent watches for new matching jobs, scores fit, researches companies, and drafts a tailored CV + cover letter. Come back tomorrow and it has re-searched, shows the **NEW roles since your last check ranked on top**, and you decide which to apply to. It never spam-submits to every board - most boards are Cloudflare/anti-bot locked, so the **final submission is intentionally human-gated by design**: the agent does everything autonomously up to the last click, and the human only approves.

by ar-Raqmi and Izaaz

---

## What is real now (2026-08-27)

- **Cloud Run backend LIVE** - `https://hireflow-backend-296941301245.us-central1.run.app` - the **full RouterAgent pipeline runs end-to-end** against the deployed build. `/pipeline/run` runs async with SSE (Search→Match→Career→Research→Prepare→approve) and `/approve` submits to the sandbox ATS. A live run this session produced `parse→audit→search→match→career→research→prepare→approve` stages, **10 matches ranked** (3 drafted / 2 routed / 4 matched), drafts (CV + cover letter) generated, and per-source new counts in `search` (freehire 5, linkedin 6, remoteok 3, ats 1, …). Soft-fail errors (e.g. JobStreet 403 Cloudflare, Ashby 404) were surfaced cleanly, never a 500. The upload gate works live: a resume scored 65/100 → "needs_improvement" confirm → "Run anyway".
- **Keyless job-source registry (curl-verified):** freehire (193 countries), RemoteOK, Remotive, LinkedIn guest search, JSON-LD career pages, ATS boards (Greenhouse GitLab 204 jobs, Ashby Notion 128 jobs). Lever (404) and Workable (0 jobs) are coded but disabled.
- **Vite + React frontend (`frontend/`) LIVE-verified** (2026-08-27) - `npm install && npm run build` passes; run live in-browser against the real backend (`localhost:5173`). Rebuilt on the **M3E (Material 3 Expressive) component library** (`@m3e/react`): app wrapped in `<M3eTheme color="#8F4100" scheme="light" motion="expressive">` (Hireflow's brand primary drives the full Material 3 palette), with M3E buttons, dialog (prefs), tabs, icons, chips, snackbar, progress indicators, segmented button, `M3eSelect`/`M3eOption` sort, `M3eFilterChip`/`M3eFilterChipSet` source filters. Custom dropzone + SSE timeline stay custom markup themed via `var(--md-sys-color-primary)`. **Watcher UX verified live:** upload-gate audit dialog → **live SSE agent timeline** → Results shows **"10 new since your last check · 10 matches ranked"**, a banner ("10 new roles since your last check - ranked on top. You decide which to apply to."), a **"New since last check (N)"** filter chip, per-card **"new" badges**, the primary CTA flips to **"Check for new jobs"** after a run, draft view (CV + cover letter) works, and History shows a "10 new" stat. Views: **Agent run / Results / History** (no separate Applications tab). Base URL via `VITE_HIREFLOW_API` (dev proxy in `vite.config.js`). `hireflow-frontend.html` is the retired reference prototype only.
- **Agent pipeline** - five agents (Search → Match → Career → Research → Prepare, orchestrated by RouterAgent) run server-side through `GeminiClient` (Vertex AI, Gemini 3.5 Flash - the only LLM entry point, no stubs/mocks). `/pipeline/run` is async and streams per-stage progress over SSE; `/upload` does a real Gemini parse (text, or vision via PyMuPDF page images when text is thin). Verified live end-to-end.
- **Search intelligence** - `QueryExpander` (Gemini synonym expansion per query + deterministic fallback), multiple query variants per source (seed-rotated so runs vary), gate-then-cap (work-type + **location** + **recency**), cross-run seen-job dedup (`?seen=` from browser `localStorage`), per-company diversity cap (max 2/company). Knobs in `hireflow/config.py`.
- **Johor/Israel false-global bug fixed** - `Johor` maps to `my` (`geo.py`); an unmapped location no longer silently widens freehire to a global onsite search.
- **Career-page company sourcing** - after matching, `CareerSourceAgent` probes each distinct top-matched company's `/careers` page + ATS boards via `WebFetchSource.webfetch_company` and merges the new jobs back into the pipeline.
- **Universal webfetch + Gemini grounded-search layer** - `webfetch.py`/`gemini_search.py`, the catch-all replacing the retired CSE 50-site whitelist; `GeminiWebSearchSource` (`gemini_web`) uses Google Search grounding via `GeminiClient.grounded_search` to surface real source URLs (the rate-limited DuckDuckGo scrape was dropped), each turned into a JobPosting via `WebFetchSource.fetch_url`. `WebFetchSource` is also used by the career-page step. **Embeddings re-rank** (`embeddings.py`, `gemini-embedding-001`; `text-embedding-005` fallback) gated by `SEMANTIC_SEARCH`.
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
Gemini 3.5+ via Vertex AI ✓ · Google ADK ✓ · Cloud Run ✓ · hosted public URL **LIVE** ✓ · open GitHub repo ✓ · README spin-up ✓ · architecture diagram in AGENTS.md (clean image pending) · ≤4-min demo video (pending) · repo access for `testing@devpost.com` + `cloudhackathons@google.com` (pending).
