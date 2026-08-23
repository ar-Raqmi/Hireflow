# AGENTS.md — Hireflow

> **Read this first. It is the memory for this project.**
> Project name is `Hireflow` (lowercase `f`).

---

## 1. What this is

**Hireflow** — an autonomous AI job-search agent for the **All Things Agentic Hackathon 2026** (Taskmaster track, deadline **Aug 31, 2026 @ 5:00pm PDT**).

The agent is **not a chatbot**. The user uploads a resume + preferences once; the agent watches for new matching jobs, scores fit, researches companies, tailors a CV + cover letter, and queues the application for **human approval**. It tracks status and drafts follow-ups.

**Pipeline:** `Find → Analyze → Rank → Research → Prepare → Approve → Track`

**One-line identity:** *"The agent never waits to be asked. It watches, decides, and acts — the human only approves."*

**Working model — online-e2e only (do not deviate):**
- I never asked for a local-only run. **Everything is tested end-to-end against the deployed Cloud Run backend.** No mock/fake/stub/Gemini stand-ins anywhere (tests included the ones hitting job sources).
- Terminal/CLI tests are done by **curling the live Cloud Run URL** with a real `.pdf` resume and the real Gemini model through Vertex AI — same path the dashboard uses.
- If something only works locally, it does not count as done. Demo proof must be on a `.run.app` URL.

---

## 2. Hackathon rules that MUST be satisfied (from RULES.md — verify against RULES.md, it is the source of truth)

**Category:** Taskmaster — *a complete workflow, not just a chatbot*. Judges look for high-value autonomous execution over simple chat queries: "does the agent successfully intercept and complete a multi-step background workflow without human intervention?"

**Mandatory for all categories (RULES §6, §65–67):**
1. **Gemini 3.5 or newer** accessed via Gemini API or Vertex AI → we use **Gemini 3.5 Flash**.
2. **At least one Google Agent Framework**: Google ADK, GenAI SDK, Antigravity SDK, or GenKit → we use **Google ADK (Python)**.
3. **At least one Google Cloud infra service**: Cloud Run, Cloud SQL, Firestore, GKE, Pub/Sub → we use **Cloud Run** (stateless, scales-to-zero, outbound HTTPS = where all job-source calls happen).

**Submission requires (RULES.md §5-6, §111+):**
- Hosted/public URL for judging (a public hosted project is **highly encouraged**) → our **Cloud Run URL**.
- Public or private GitHub URL granted to `testing@devpost.com` + `cloudhackathons@google.com`.
- README **spin-up instructions** (proves reproducibility).
- **Architecture diagram**.
- **Demo video ≤4 min**, English or subtitled, which must **visually prove the backend runs on Google Cloud** (Cloud Run console / Cloud dashboard / Vertex AI logs / `.run` URL on camera), and must show **live execution** (terminal/API logs).
- English support at minimum.

**Judging weights (RULES.md §8):** Innovation & Operational Utility **40%** · Architectural Discipline & Tech Stack **30%** · Demo & Production Readiness **30%**.

**Eligibility traps in RULES.md (do not trip):**
- Project must be **built during the Submission Period** (Aug 3 – Aug 31 2026).
- **No pre-existing work from a previous contest / outside activity**; third-party data/SDKs must be used per their terms (so mark the job-source APIs as public-keyless usage; never claim an API key/country coverage we have not verified).
- All source code must be **original work of the team**; open-source is fine but license-appropriate. Inspirational repos (e.g. MadsLorentzen/ai-job-search) are **ideas only — never copy code**.
- **$150 credits form** closes **Aug 28 12:00pm PT** (link in §13; official RULES §8).
- **Bonus (≤0.6 pts):** each additional Google AI model integrated (Gemma, Veo, Lyria). **Optional, low-priority.**

**Cost notes:** Flash-first everywhere (Gemini Flash for scoring/routing; Pro only if a review step needs it). Cloud Run scales to zero. Record the demo proof, then shut services off.

---

## 3. Team split (who does what)

| Role | Owner | Scope |
|------|-------|-------|
| Coding + backend | **You** (with your AI) | ADK agent, FastAPI, job-source clients, Vite+React frontend, demo video |
| Cloud (all Google things) | **Zach** | GCP project, $150 credits, enable APIs, service-account key, Vertex AI, Cloud Run deploy, IAM, GCloud console proof for demo |

**Handoffs:** Zach gives → project id + service-account credentials JSON + enabled APIs. You give → Dockerfile + code. Zach returns → Cloud Run `.run.app` URL. No DB setup needed.

---

## 4. Locked decisions (do not silently change)

| Decision | Choice |
|----------|--------|
| Name | **Hireflow** (repo, code, docs — lowercase `f` everywhere) |
| Agent framework | **Google ADK (Python)** |
| Model | **Gemini 3.5 Flash** via **Vertex AI** (Flash-first; Pro only if a review step demands it) |
| Backend | **FastAPI** (Python) |
| Frontend | **Vite + React** (the real app, wired to the deployed FastAPI via fetch). `hireflow-frontend.html` is the clickable prototype/reference only — the React app replaces it. |
| Database/state | **No SQL**. Browser `localStorage` owns prefs + history; backend is stateless, in-memory only for a run |
| Hosting | **Cloud Run** (scale-to-zero) |
| Scheduling | **Cloud Scheduler** → `POST /pipeline/run` (job polling) — optional |
| Job sources | **Global source registry — keyless + native APIs + fallback CSE/JSON-LD/Playwright** (details §10). Never "remote-only" nor "US-only" |
| Apply strategy | **Sandboxed job board (simple ATS)** in the demo; real-world = draft-for-approval |
| Scoring | 5 dimensions: skills, experience, location, salary band, culture/keywords |
| Human handoff | offers, salary talks, counter-offers → flag "needs human" |
| Approval gates | score ≥80 → auto-draft; 60–79 → draft for review; <60 → archive. **Final submit always human-approved** |
| Work-type pref | hard filter `remote | onsite | hybrid | any`, asked in its own dialog; skippable → `any` |
| Location pref | preferred *work* locations — separate dialog, NEVER defaulted from residence; skippable → anywhere |
| History | New tab, `localStorage`, own "Clear history" button (reset does not touch it) |
| Gemini client | **`GeminiClient` only** (Vertex AI first, API-key fallback). **No mock/fake/stub/deterministic stand-in.** Real model in every run & online test |
| **Runtime rule** | **No local e2e. Everything is verified with curl against the live Cloud Run URL.** |

---

## 5. Architecture (multi-agent — the 5 agents are the LIVE pipeline)

```
[User] → [Vite + React app → fetch to FastAPI] → [RouterAgent (orchestrator)]
                                                         │  SSE progress: parse→audit→search→match→research→prepare→approve
                   ┌─────────────────────────────────────┼────────────────────────────┐
                   ▼                                     ▼                            ▼
          SearchAgent                         MatchAgent(CV Analysis)      ResearchAgent
          search_jobs(global registry)       score_fit() 5-dim scoring     company_research()
                                            + audit_resume (ATS)
                   └─────────────────────────────────────┼────────────────────────────┘
                                                         ▼
                                        PrepareAgent: DRAFTER → REVIEWER → REVISE
                                                         ▼
                                               [ HUMAN APPROVAL GATE ]
                                                         ▼
                                        Browser localStorage (history + tracking)
```

MVP agents: **Search, Match/Analyze, Research, Prepare (drafter→reviewer→revise)**, orchestrated by **RouterAgent**. Every agent runs server-side through `GeminiClient` (the only LLM entry point) and tags its stage on the SSE stream. Tracking = passive localStorage/dashboard. No DB.

State story (judge-grade): **client-side persistence, stateless backend.** Nothing sensitive is ever stored server-side.

---

## 6. OOP conventions (STRICT — past violations cost us a broken tree)

- **All backend code object-oriented.** No free functions doing work; logic lives in classes.
- Abstract base classes define contracts:
  - `hireflow/storage/` → `Repository` (ABC): `InMemoryRepository` (default)
  - `hireflow/agents/` → `BaseAgent` (ABC): `SearchAgent`, `MatchAgent`, `ResearchAgent`, `PrepareAgent`, `RouterAgent` — **these are the LIVE pipeline** (RouterAgent orchestrates them; every one uses `GeminiClient`)
  - `hireflow/tools/` → `JobSource` (ABC): `RemoteOKSource`, `RemotiveSource`, `FreehireSource` (+ any new global sources)
  - `hireflow/tools/` → `GeminiClient` — THE only LLM entry point. No alternative/fallback LLM path, no stub.
- Domain models in `hireflow/domain/` — plain typed classes, no framework imports:
  - `Profile` (incl. `residence`, `work_type`, preferred `locations`, `salary_floor`)
  - `JobPosting`, `Application` (+ `ApplicationStatus` — only `MATCHED`/`ROUTED`/`DRAFTED`/`APPROVED` are used at runtime)
  - **`ResumeFinding`** — one ATS-health finding produced by `GeminiClient.audit_resume` (now present; `from hireflow.domain import JobPosting, Profile, ResumeFinding` resolves).
  - **`WorkTypeClassifier`** — deterministic `remote|hybrid|onsite|any` gate (now present; used by `ResumeParser.infer_work_type` and `SearchAgent._infer_work_type`).
- **Naming:** classes `PascalCase`, methods/vars `snake_case`, constants `UPPER_SNAKE`, private helpers `_underscore`.
- **No code comments unless asked.**
- Type hints everywhere (Python 3.11+).
- Frontend OOP rules don't apply (Vite + React — build tool allowed).

---

## 7. File layout (repo — reality as of Aug 22)

```
.
├── AGENTS.md                # this file — the memory
├── README.md                # NEVER lie; update after every deploy with real URLs
├── hireflow-frontend.html   # clickable prototype/reference ONLY (mock → replaced by the React app)
├── hireflow.sh              # bash thin CLI driver — prompts + curls the LIVE Cloud Run URL (online-only)
├── requirements.txt
├── Dockerfile
├── .dockerignore            # keeps .env/API.md/credential JSON out of the Cloud Build context
├── .gitignore
├── RULES.md                 # official hackathon rules — read before decisions
├── docs/
│   ├── CURL_E2E.md          # exact online curl playbook (upload → run → approve) against live URL
│   └── DEPLOY.md            # Zach's one-command Cloud Run redeploy + Vertex IAM grant
├── hireflow/
│   ├── config.py            # Settings (project id, model, vertex/api-key flags, thresholds 80/60,
│   │                        #   caps, RESUME_PARSE_MODE)
│   ├── cli.py               # `python -m hireflow.cli` — thin client of the deployed API (streams SSE)
│   ├── domain/__init__.py   # Profile, JobPosting, Application, ApplicationStatus, ResumeFinding,
│   │                        #   WorkTypeClassifier (all present — import tree unblocked)
│   ├── storage/             # Repository ABC + InMemory + StorageFactory (in-memory only, no DB)
│   ├── agents/              # BaseAgent ABC, router.py (Search/Match/Research/Prepare/Router — the LIVE
│   │                        #   pipeline), adk_router.py (HireflowAgent ADK graph + HireflowTools),
│   │                        #   runlog.py (RunLog — in-memory per-run SSE event log)
│   ├── tools/               # JobSource ABC, RemoteOK, Remotive, Freehire, geo (LocationMapper),
│   │                        #   resume_parser, gemini.py (REAL GeminiClient, incl. vision parse),
│   │                        #   linkedin.py (LinkedInSource), jsonld.py (JsonLdSource),
│   │                        #   ats.py (AtsBoardSource), browser.py (PlaywrightSource, opt-in)
│   └── api/app.py           # FastAPI: health, upload (text+vision parse), dashboard, jobs,
│                            #   applications, approve, pipeline/run (async), pipeline/run/{id}/events (SSE)
└── frontend/                # Vite + React app (future — the real frontend; replaces hireflow-frontend.html)
```

**Deps (requirements.txt):** adds `PyMuPDF` (renders PDF pages → PNG for the
Gemini vision path; pure-pip, no system libs). `google-cloud-firestore`,
`google-cloud-aiplatform`, and `google-generativeai` were removed as dead
imports (Vertex/API access is handled by `google-genai`).

**No `tests/` directory — by design.** Offline tests (stub agent, `_StubGemini`,
`TestClient`) were deleted. The acceptance gate is the online curl e2e in
`docs/CURL_E2E.md` against the live Cloud Run URL — never a local pytest run.

**Ghosts of the tree — do NOT restore them as ground truth:**
- `cli.py` — **was never committed** (only `.pyc` proved it existed). Now it IS committed: `hireflow/cli.py` (thin client of the deployed API) + `hireflow.sh` (bash driver).
- `json_repository.py`, `openrouter.py`, `mock_gemini.py` — existed only as `.pyc`; do NOT take them as ground truth. Never rebuild a mock Gemini path.

---

## 8. Backend API surface (FastAPI) — current state (real!)

- `GET /health` → `{"status":"ok"}` — live, works (verified Aug 22).
- `POST /upload` — real parse: `ResumeParser` extracts text from `.txt/.pdf/.docx`
  (`pypdf`/`python-docx`), validates `work_type ∈ remote|hybrid|onsite|any`,
  builds a `Profile` (work_type gate, locations, target roles, salary floor),
  then **runs a real Gemini parse** (text-only, or Gemini vision page-images via
  PyMuPDF when the PDF text is thin / `RESUME_PARSE_MODE=vision`) to populate
  `skills`, `years_experience`, `culture_keywords`, `residence` and inferred
  `target_roles`. Parse failure degrades to text-only + `parse_errors`, never a
  500. Returns `status: "parsed_and_stored"` + pages + enriched fields.
- `POST /pipeline/run?profile_id=…` — **async + SSE**: creates a `run_id`,
  runs the real **RouterAgent pipeline** (`SearchAgent → MatchAgent →
  ResearchAgent → PrepareAgent`, orchestrated by `RouterAgent`, every agent
  through `GeminiClient` Vertex-first + `JobSource` Freehire/RemoteOK/Remotive)
  in a background asyncio task, and returns `{"run_id":…,"status":"started"}`
  immediately. Caps: ≤25 jobs, ≤10 scored, ≤5 prepared (env-tunable).
- `GET /pipeline/run/{run_id}/events` — **Server-Sent Events** (`text/event-stream`):
  streams `parse → audit → search → match → research → prepare → approve`
  agent-tagged stage events with counts/names as `data: {…}`, then a final
  `event: done` with the full result JSON. A down board degrades to `[]` and is
  recorded in `errors`, never a 500.
- `GET /dashboard` — live counts + by-status breakdown.
- `GET /jobs` / `GET /applications` — list repository contents (persisted from
  the background run's `jobs` / `application_records`).
- `POST /approve?application_id=…` — flips an application to approved (human gate).

**Live Cloud Run** (`https://hireflow-backend-296941301245.us-central1.run.app`)
is alive (`/health` ok) but still predates the RouterAgent pipeline wiring AND
the SSE streaming — the NEW build is the acceptance target — see
`docs/DEPLOY.md` for the redeploy and `docs/CURL_E2E.md` for the curl proof.

---

## 9. Current state of the repo (the honest truth — verified by me, do not trust the old AGENTS claims)

- **Import tree is unblocked.** `ResumeFinding` + `WorkTypeClassifier` are in
  `hireflow/domain/__init__.py` and `hireflow.tools.gemini` imports cleanly.
  **No offline tests exist** — `tests/` was deleted; the acceptance gate is the
  online curl e2e (`docs/CURL_E2E.md`). `python -m hireflow.cli` and `hireflow.sh`
  are thin clients of the deployed API.
- **`/pipeline/run` is now async + SSE** — it returns `{"run_id":…,"status":"started"}`,
  runs the real **RouterAgent pipeline** (`SearchAgent → MatchAgent →
  ResearchAgent → PrepareAgent`, every agent through `GeminiClient`
  Vertex-first + `JobSource` Freehire/RemoteOK/Remotive, orchestrated by
  `RouterAgent`) in a background asyncio task writing to an in-memory `RunLog`
  (`hireflow/agents/runlog.py`), and `GET /pipeline/run/{run_id}/events` streams
  `parse → audit → search → match → research → prepare → approve` events then a
  final `done` payload. `/upload` now runs a real Gemini parse (text, or vision
  via PyMuPDF page-images when the PDF text is thin) so `skills` /
  `years_experience` are populated. The deployed build still predates this: the
  live `/pipeline/run` answers `agent_not_configured` until the redeploy in
  `docs/DEPLOY.md` lands.
- **Live Cloud Run** (`https://hireflow-backend-296941301245.us-central1.run.app`)
  is ALIVE and returns `{"status":"ok"}` (verified Aug 22) — it predates the
  pipeline wiring AND the SSE streaming.
- **Not yet done (must be proven live, AGENTS.md §16):** the new build is not
  deployed; the online curl e2e (upload → run → stream events → jobs → approve)
  against the live URL has not run with this code; `hireflow-frontend.html` is
  still a mock; CSE / JSON-LD / Layer II (Playwright) are designed but not
  implemented.

**The old AGENTS.md claimed Phases "1 & 1.5 done": that was FALSE at the time**
(import was broken, no live pipeline). Today the code paths exist and are green
offline; the phase is done ONLY when the redeploy + curl e2e on the `.run.app`
URL pass.

---

## 10. Global job-source strategy (the layers — no country is "not supported")

**No single API covers every country with structured JSON.** "Global" is a **layered registry** — every country above zero native feed; the long-tail catch-all is the web layer. Verify each source with a real `curl` before coding it (they rot fast; do not trust my available knowledge or datasets).

### Verified-sources matrix (updated 2026-08-23 — each row curl-verified this session)

| Source | Endpoint (live) | Layer | curl status | Jobs parsed | Countries/notes |
|--------|-----------------|-------|-------------|-------------|-----------------|
| freehire | `GET https://freehire.me/api/v1/agent/jobs/search` (+facets) | I | 200 | yes (JP/Tokyo, 193 countries) | keyless aggregator, remote/hybrid/onsite, salary enrichment |
| RemoteOK | `GET https://remoteok.com/api` | I | 200 | yes | remote-only, EU/US-weighted |
| Remotive | `GET https://remotive.com/api/remote-jobs` | I | 200 | yes | remote-only, EU/US-weighted |
| LinkedIn guest | `GET https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?keywords=…&location=…&f_WT=…&start=0` | 0 | **200** | **yes** (Tokyo, 5+ cards; `engineer` → 3, `software` → 2) | keyless, global, low-volume/personal-use only (ToS) |
| Greenhouse (ATS) | `GET https://boards-api.greenhouse.io/v1/boards/gitlab/jobs?content=true` | I | **200** | **204 jobs** | GitLab board; title/location/content/absolute_url |
| Ashby (ATS) | `GET https://api.ashbyhq.com/posting-api/job-board/notion` | I | **200** | **128 jobs** | Notion board; title/location/jobUrl/descriptionHtml |
| Lever (ATS) | `GET https://api.lever.co/v0/postings/{board}?mode=json` | I | **404** on all boards tested (dropbox/airtable/block/tesla/…) | 0 | endpoint appears retired/unreliable — **not enabled**, `ats.py` supports it but no live row |
| Workable (ATS) | `GET https://apply.workable.com/api/v1/widget/accounts/{account}` | I | **200 but 0 jobs** on every account tried (tokopedia/wayfair/pearson/…) | 0 | API reachable but returns empty `jobs[]` for tested accounts — **not enabled**, `coded` only |
| JSON-LD career pages | `GET https://www.greenhouse.io/careers` → `application/ld+json` → `@type=JobPosting` | 0 | **200** | **1 JobPosting** ("Multiple Open Positions", Greenhouse, Colorado US) | real page w/ schema.org `JobPosting`; registry = 1 verified URL (`JSONLD_COMPANY_URLS`); other big career pages tested (Atlassian, Shopify, Nike…) have **no** JobPosting ld+json |
| Playwright Layer II | env-gated `HIREFLOW_PLAYWRIGHT=1` + Chromium in image | II | not run | n/a | **scaffolded only**, disabled by default, deploy wiring is a TODO |

**Layer 0 — Universal catch-all (every country, everyone):**
- **Google Custom Search JSON API** (CSE) — search expression restricted to job sites/ATS domains per country (e.g. `site:careers.x jp`). Needs a CSE **API key + engine ID from Zach** (one-time, free tier ~100 queries/day, fine for the demo, paid for scale). **NOT DONE — needs Zach key.**
- **JSON-LD / schema.org `JobPosting`** — ✅ **IMPLEMENTED + live-verified** (`hireflow/tools/jsonld.py`, `JsonLdSource`). Fetches career pages, regexes `application/ld+json`, walks for `@type=JobPosting`. This is the true "career page" tap without scraping infra.
- **LinkedIn guest API** (`jobs-guest` endpoints) — ✅ **IMPLEMENTED + live-verified** (`hireflow/tools/linkedin.py`, `LinkedInSource`). Keyless, global, works for location strings (verified: Tokyo 200). Personal-use, low volume (`limit` ≤15); keep it a source, not the demo centerpiece. Respects ToS — no scraping, soft-fail on 403/999.

**Layer I — keyless aggregators (remote, hybrid, onsite):**
- **freehire.me** (covers **193 countries**; verified `regions=apac`/`countries=jp|id|my|...`; `work_mode` remote/hybrid/onsite; `enrichment.salary_min/max`; full description in-search via `include_description=true`). It is a **personal project (no SLA, tier badges)** — plan a one-line swap via `FREEHIRE_API_URL`.
- **RemoteOK, Remotive** — remote-only, good EU/US.
- **ATS boards** — ✅ **IMPLEMENTED + partially verified** (`hireflow/tools/ats.py`, `AtsBoardSource`). Unified keyless endpoint for Greenhouse/Ashby/Lever/Workable. **Greenhouse (gitlab 204) + Ashby (notion 128) verified live and ENABLED in `ATS_BOARDS`.** Lever 404s and Workable returns 0 jobs on all boards tested — coded but **disabled/no registry rows** until a live-verified board is found. `source="ats:{board}"`.

**Layer II — browser automation (last resort, officially supported, still no VPS):**
- **Playwright/Puppeteer + headless Chromium inside the Cloud Run container** — ✅ **scaffolded, OPT-IN** (`hireflow/tools/browser.py`, `PlaywrightSource`). Documented by Google ("Browser and OS automation in Cloud Run"): install Chromium in the image, drive it from an ADK tool, extract content, feed to Gemini. Use ONLY for JS-heavy SPA career pages with no JSON-LD and no API (e.g. Kalibrr, Wantedly, MyCareersFuture, anti-bot pages).
- **Cost caveat:** headless Chrome needs a bigger instance (more RAM, CPU stays billed during the request, slower cold start) — keep it a scoped last-resort layer, never the default per-source path. Default OFF; Chromium-in-Dockerfile is a **documented TODO**.
- A **full desktop OS via VNC streaming** (WebSockets) is also documented for complex interaction — not needed for the demo.

**C — Regions, currently curated:**
- **MY**: freehire(my) · JobStreet MY · Maukerja
- **ID**: freehire(id) + JobStreet ID · (Kalaber is SPA-only; JSON-LD first, else **Layer II** Playwright)
- **JP**: freehire(jp) · LinkedIn(guest) verified Tokyo · Wantingly/Sapphire are SPA/anti-bot → **CSE scoped to jp career pages**, else **Layer II** Playwright · K-Worknet (KR)
- **KR**: K-Worknet (**official public job API**, free key, ktor-friendly)
- **SG**: freehire(sg) · LinkedIn(guest) verified · MyCareersFuture (SPA — read its real JSON feed if you can establish it; else CSE `domain:careers.gov.sg`, else **Layer II** Playwright)
- **EU/NA**: freehire + RemoteOK/Remotive + **ATS boards (Greenhouse-GitLab, Ashby-Notion verified live)** · more ATS boards to add as they are curl-verified.

**D — verification rule (REQUIREMENT):** Before any country/source is "supported", run a real `curl` and post the HTTP code + job count in the PR/commit. No `curl` = not supported. Update this section each time we verify a new one.

**The golden rule:** never scrape a site with a brute-force bot or pretend a job board is something it isn't. Job boards are public APIs; career pages are JSON-LD or ATS-APIs; the only sanctioned browser path is **Layer II** (Playwright + Chromium on Cloud Run) for SPA-only career pages. Everything runs on Cloud Run (no VPS).

---

## 11. Backend API surface (target, FastAPI)

- `POST /upload` — resume (txt/pdf/docx) + preferences → store → **parse/audit** (real Gemini, text+vision)
- `GET /dashboard` — live pipeline status
- `GET /jobs` / `GET /applications` — read
- `POST /approve` — human approval gate
- `POST /pipeline/run` — start the **RouterAgent** Search→Match→Research→Prepare pipeline end-to-end async → returns `run_id` (`started`)
- `GET /pipeline/run/{run_id}/events` — SSE stream of per-stage progress + final `done` payload
- healthcheck (`/health`) for Cloud Run

---

## 12. Roadmap — realistic, online-e2e (to Aug 31)

**Now (the base, mandatory — stops the "partial runtime" myth):**
1. ~~Unblock the import tree~~ — **DONE**: `ResumeFinding` + `WorkTypeClassifier` are in `hireflow/domain/__init__.py` and `hireflow.tools.gemini` imports cleanly.
2. ~~Wire the 5 named agents into the server pipeline~~ — **DONE (code; live proof pending redeploy)**: `RouterAgent` now orchestrates `SearchAgent → MatchAgent → ResearchAgent → PrepareAgent` as the ACTUAL `/pipeline/run` executor. Each agent carries its prompt-engineering and calls the same `GeminiClient` methods (`score_fit`, `research_company`, `draft/review/revise_application`, `audit_resume`). Stages are tagged in SSE as `search`/`match`/`research`/`prepare`. `HireflowTools` is reduced to the ADK `FunctionTool` layer; `HireflowAgent` keeps the mandated ADK `LlmAgent` graph and delegates to `RouterAgent` when wired.
3. ~~Fix `freehire.py`~~ — **DONE**: live endpoint (`/api/v1/agent/jobs/search`) + facets, `LocationMapper` geo codes, stable `source`/`title`/etc. core schema across all sources.
4. ~~Offline tests removed~~ — **DONE**: `tests/` deleted (stub agent, `_StubGemini`, `TestClient`). There is no offline gate — the acceptance gate is the online curl e2e in steps 5 & 6 against the live Cloud Run URL (real `.pdf`, real Gemini via Vertex).
5. **Re-deploy to Cloud Run** (docs/DEPLOY.md) → curl `/health`, then a **real** e2e: upload a real `.pdf` → `/pipeline/run` → `/jobs` live results → `/dashboard` reflects it → `/approve`. **Video-record the curl-to-cloud proof.**
6. ~~Terminal CLI test~~ — **DONE**: `hireflow/cli.py` + `hireflow.sh` are thin clients hitting the live API (not a separate runtime).

**Next (global + demo):**
7. **Global job-source registry** — ✅ **IMPLEMENTED + curl-verified (2026-08-23)**: `LinkedInSource` (guest API), `JsonLdSource` (schema.org career pages), `AtsBoardSource` (Greenhouse+Ashby). Registered in `_build_default_agent()` after RemoteOK/Remotive/Freehire. Lever (404) and Workable (0 jobs) are coded but **disabled** — add rows only once curl-verified. **Still pending: redeploy + live curl e2e** against the `.run.app` URL to prove this on the live deploy.
8. Add **Google CSE** (needs CSE API key from Zach) + finish **Layer II** Playwright/Chromium (Chromium in the Dockerfile, ADK `FunctionTool`) for SPA-only career pages — currently scaffolded/opt-in.
9. Build the **Vite + React app** (`frontend/`, to be scaffolded) wired to the live backend (fetch) — the dashboard calls the same endpoints the CLI calls; `hireflow-frontend.html` is retired as the reference prototype.
10. **Demo & docs**: clean architecture diagram image (README currently has ASCII), README spin-up, ≤4-min unedited video showing Cloud Run console + Vertex AI logs + live `.run` calls. Email `testing@devpost.com` / `cloudhackathons@google.com` access.

---

## 13. Reference links (real ones; find the rest online before trusting)

- Hackathon site: `allthingsagentichackathon.devpost.com`
- Credits form: `forms.gle/riGhgDSHkHeMx8Ca6` (closes **Aug 28, 12:00pm PT**; not `5PtXmw1dSbDnpYke9` — that was wrong in the old doc)
- Rules: `RULES.md` is the full official text — trust it over any summary.
- Google ADK: `google.github.io/adk-docs`, `github.com/google/adk-python`
- Gemini: `ai.google.dev` (API key), Vertex AI docs
- Cloud Run browser automation (Playwright/Chromium, VNC): `cloud.google.com/run/docs/browser-automation`
- Inspo sources — ideas only, NOT code:
  - `github.com/MadsLorentzen/ai-job-search` — fits the query-by-function search, gates-before-scoring, seen-job adoption; **their runtime is local (Claude Code) — we are Cloud Run**.
  - `github.com/strelov1/freehire` — freehire.me is MIT open-source backend (Go+Postgres+Meilisearch); `FREEHIRE_API_URL` env-swap is our one-line failover.
- **Job-source references (verified live 2026-08-23, but re-verify):**
  - Greenhouse: `GET https://boards-api.greenhouse.io/v1/boards/gitlab/jobs?content=true` (204 jobs)
  - Ashby: `GET https://api.ashbyhq.com/posting-api/job-board/notion` (128 jobs)
  - LinkedIn guest: `GET https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?keywords=engineer&location=Tokyo` (200, cards parse)
  - JSON-LD: `GET https://www.greenhouse.io/careers` → ld+json `JobPosting` (1 posting)
  - Lever: `GET https://api.lever.co/v0/postings/{board}?mode=json` — **404 on all boards tested; retired/unreliable, not enabled**
  - Workable: `GET https://apply.workable.com/api/v1/widget/accounts/{account}` — **200 but 0 jobs on all accounts tested; not enabled**
  - freehire: `GET https://freehire.me/api/v1/agent/jobs/search` + facets `/api/v1/jobs/facets`
  - Remotive: `GET https://remotive.com/api/remote-jobs`
  - RemoteOK: `GET https://remoteok.com/api`

---

## 14. Next session: where to pick up

1. Re-deploy to Cloud Run (`docs/DEPLOY.md`) → curl `/health`, then the live curl e2e with a real `.pdf` (`docs/CURL_E2E.md`): upload → run → jobs → approve. **This proves the phase — not the offline green.**
2. Scaffold + wire the **Vite + React app** (`frontend/`) to the deployed API via fetch (dashboard + approve).
3. Global registry column §10: **CSE key from Zach** (not done) + **Layer II Playwright/Chromium wiring in the Dockerfile** (scaffolded/opt-in).
4. Demo & docs: clean diagram image, ≤4-min video with Cloud Run console + Vertex logs, grant repo access to `testing@devpost.com` / `cloudhackathons@google.com`.
5. Optional: Cloud Scheduler → POST `/pipeline/run` hourly.

---

## 15. Zach handoff checklist (cloud owner)

**Must provide (blocks real e2e):**
1. `GCP_PROJECT_ID` (we have `hireflow-506207` in-use — confirm).
2. Service-account credentials JSON (path → `GOOGLE_APPLICATION_CREDENTIALS`) — **Vertex AI** permission only; no DB.
3. Enabled APIs: **Vertex AI** (required), **Cloud Run** (later), Cloud Scheduler (optional).
4. `GEMINI_API_KEY` (Gemini API fallback) — only if we ever run Vertex-less; we have a real one on-disk (last verified live at repo time).
5. Is model string `gemini-3.5-flash` valid in the project? (RULES require Gemini 3.5+.)
6. **Green light/help for Google-CSE API key + JSON-LD** — single key for the catch-all search.

**Later:**
7. Deploy the `Dockerfile` to **Cloud Run** → return the `.run.app` URL (needed for end-of-video proof).
8. Optional: Cloud Scheduler → POST `/pipeline/run` hourly.
9. Capture Cloud Run console + Vertex AI logs for the video.

**No DB needed.** Demo = a Cloud Run-backed run; user data stays in the browser.

---

## 16. Working style (die-hard rules from the task)

- **No local-only anything.** Curl the live endpoint.
- **Never trust a dataset / my mind-guessed facts for architecture.** If a source/endpoint/API is about to be used, verify it with a `curl` first — today's job landscape changes fast.
- **No "this will do".** "Global" means a country gets at least one real path (aggregator keyless → native/reg API → CSE catch-all), not "freehire covers enough".
- **Keep the `README.md` truthful** — after every change, update URLs, verified sources, and the two-line "what's real now" section.
- **Never call two things "done" until a live e2e on that deploy proves it.** The tree is green offline today (imports unblocked, agent wired), but the repo is only "done" when the redeploy + curl e2e on the `.run.app` URL pass — verify, THEN write done in the file.

*Bismillah.*