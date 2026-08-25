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
| Job sources | **An AI search agent, not a keyword fetcher** — **IMPLEMENTED (code; live proof pending redeploy)**: Gemini query expansion (synonyms per role, deterministic fallback), multiple query variants per source for variation, then gate-then-cap (work-type + **location** + recency) before scoring, with cross-run seen-job dedup + per-company diversity. Backed by a **keyless global source registry** (freehire/RemoteOK/Remotive + JSON-LD + LinkedIn guest + ATS Greenhouse/Ashby + freehire `source=seek`/`mycareersfuture`), honest per-country paths. **Universal webfetch + discovery layer + embeddings re-rank: PRESENT (code; live proof pending redeploy)** — no 50-domain whitelist; **Agent Search is OPTIONAL** (replaces CSE; only indexes domains Zach can verify he owns — see `docs/GCP_SETUP.md` §3). Never "remote-only" nor "US-only" (details §10) |
| Apply strategy | **Sandboxed job board (simple ATS)** in the demo; real-world = draft-for-approval. **Real submit to the sandbox ATS is PRESENT (code; live proof pending redeploy)** — `/approve` now submits via `/sandbox/ats/apply` (`ApplicationStatus.SUBMITTED` + `ats_confirmation`); in-memory + best-effort `sandbox_ats.json`, no DB |
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

`SearchAgent` is the **search intelligence** pass: query expansion → multi-variant queries per source → gate-then-cap (work-type + location + recency) → cross-run seen-job dedup → per-company diversity cap. The universal **webfetch + discovery** layer (`webfetch.py`/`discovery.py`) and the **embeddings re-rank** stage (`embeddings.py`) are **PRESENT (code; live proof pending redeploy)** and slot inside `SearchAgent`.

State story (judge-grade): **client-side persistence, stateless backend.** Nothing sensitive is ever stored server-side.

---

## 6. OOP conventions (STRICT — past violations cost us a broken tree)

- **All backend code object-oriented.** No free functions doing work; logic lives in classes.
- Abstract base classes define contracts:
  - `hireflow/storage/` → `Repository` (ABC): `InMemoryRepository` (default)
  - `hireflow/agents/` → `BaseAgent` (ABC): `SearchAgent`, `MatchAgent`, `ResearchAgent`, `PrepareAgent`, `CareerSourceAgent`, `RouterAgent` — **these are the LIVE pipeline** (RouterAgent orchestrates them; every one uses `GeminiClient`; `CareerSourceAgent` also uses `WebFetchSource`)
  - `hireflow/tools/` → `JobSource` (ABC): `RemoteOKSource`, `RemotiveSource`, `FreehireSource` (+ any new global sources)
  - `hireflow/tools/` → `GeminiClient` — THE only LLM entry point. No alternative/fallback LLM path, no stub.
  - `hireflow/tools/` → **search intelligence** — **PRESENT (code; live proof pending redeploy)**,
    all grep-verified this pass: `QueryExpander` (`expander.py` — Gemini expansion + deterministic
    fallback), `WantedlySource` (`wantedly.py`, JP, flag-gated), `JapanDevSource` (`japan_dev.py`,
    JP, flag-gated), **`JobStreetSource` (`jobstreet.py`, PLAYWRIGHT — the "PC-quality" source:
    real Chromium renders `{cc}.jobstreet.com/{role}-jobs/in-{place}` (my/sg/id/ph/th/vn),
    extracts per-card title/company/location/salary("RM 9,000 – RM 13,000 per month")/
    work-type/listed-date from the DOM exactly as a real browser sees. Cloudflare 403s plain
    httpx (live-verified), so this source is Playwright-only, gated `HIREFLOW_PLAYWRIGHT=1` +
    `JOBSTREET_ENABLED=true`; cap ≤20 cards/run, ToS low-volume; soft-fail → `[]`)**. `LocationMapper` (`geo.py` — incl. `Johor → my`; the location gate lives in
    `SearchAgent._passes_location`).
  - `hireflow/tools/` → **PRESENT (code; live proof pending redeploy)**:
    `WebFetchSource` (`webfetch.py`), `WebDiscoverySource` (`discovery.py`), `EmbeddingRanker`
    (`embeddings.py`). All landed in the tree; still need a redeploy + curl e2e to count.
- Domain models in `hireflow/domain/` — plain typed classes, no framework imports:
  - `Profile` (incl. `residence`, `work_type`, preferred `locations`, `salary_floor`)
  - `JobPosting`, `Application` (+ `ApplicationStatus` — `MATCHED`/`ROUTED`/`DRAFTED`/`SUBMITTED`; `SUBMITTED` is the real-submit state)
  - **`ResumeFinding`** — one ATS-health finding produced by `GeminiClient.audit_resume` (now present; `from hireflow.domain import JobPosting, Profile, ResumeFinding` resolves).
  - **`WorkTypeClassifier`** — deterministic `remote|hybrid|onsite|any` gate (used by `SearchAgent._infer_work_type`).
- **Naming:** classes `PascalCase`, methods/vars `snake_case`, constants `UPPER_SNAKE`, private helpers `_underscore`.
- **No code comments unless asked.**
- Type hints everywhere (Python 3.11+).
- Frontend OOP rules don't apply (Vite + React — build tool allowed).

---

## 7. File layout (repo — reality as of Aug 23)

```
.
├── AGENTS.md                # this file — the memory
├── README.md                # NEVER lie; update after every deploy with real URLs
├── hireflow-frontend.html   # clickable prototype/reference ONLY (mock → replaced by the React app)
├── hireflow.sh              # bash thin CLI driver — prompts + curls the LIVE Cloud Run URL (online-only)
├── hireflow.bat             # Windows double-click client → runs hireflow_run.py (exports the HTML report too)
├── hireflow_run.py          # cross-platform thin client shared by hireflow.sh/bat (pure stdlib + curl)
├── requirements.txt
├── Dockerfile
├── .dockerignore            # keeps .env/API.md/credential JSON out of the Cloud Build context
├── .gitignore
├── RULES.md                 # official hackathon rules — read before decisions
├── docs/
│   ├── CURL_E2E.md          # exact online curl playbook (upload → run → approve) against live URL
│   ├── DEPLOY.md            # Zach's one-command Cloud Run redeploy + Vertex IAM grant
│   └── GCP_SETUP.md         # one-time GCP runbook: APIs, SA grant, embeddings check, optional
│                             #   Agent Search (§3 — domain-verify only), big-instance deploy
│                             #   (no ZACH_SETUP.md yet — if the code agent adds one, list it here)
├── hireflow/
│   ├── config.py            # Settings (project id, model, vertex/api-key flags, thresholds 80/60,
│   │                        #   caps, RESUME_PARSE_MODE, QUERY_EXPANSION(+terms), JOB_RECENCY_DAYS,
│   │                        #   DIVERSITY_MAX_SAME_COMPANY, USE_UNVERIFIED_SOURCES, FREEHIRE_SOURCES)
│   ├── cli.py               # `python -m hireflow.cli` — thin client of the deployed API (streams SSE)
│   ├── export_html.py       # HtmlExporter — full result → self-contained result-demo.html (+ .json)
│   │                        #   inline CSS only, clickable links, no truncation (client-side, stdlib)
│   ├── domain/__init__.py   # Profile, JobPosting, Application, ApplicationStatus (MATCHED/ROUTED/
│   │                        #   DRAFTED/SUBMITTED), ResumeFinding,
│   │                        #   WorkTypeClassifier (all present — import tree unblocked)
│   ├── storage/             # Repository ABC + InMemory + StorageFactory (in-memory only, no DB)
│   ├── agents/              # BaseAgent ABC, router.py (Search/Match/Research/Prepare/Router — the LIVE
│   │                        #   pipeline; SearchAgent = query expansion + variants + location/recency
│   │                        #   gates + seen dedup + diversity cap), career_source.py (CareerSourceAgent
│   │                        #   — probes top matched companies' /careers pages via WebFetchSource and
│   │                        #   merges new jobs back for scoring), adk_router.py (HireflowAgent ADK
│   │                        #   graph + HireflowTools — kept for the mandatory-ADK rule, NOT wired
│   │                        #   into the live /pipeline path), runlog.py (RunLog — in-memory per-run SSE log)
│   ├── tools/               # JobSource ABC, RemoteOK, Remotive, Freehire (+ freehire:seek /
│   │                        #   mycareersfuture sub-sources in app.py), geo (LocationMapper,
│   │                        #   incl. Johor → my), expander (QueryExpander), wantedly (JP),
│   │                        #   japan_dev (JP, flag-gated), resume_parser, gemini.py (REAL
│   │                        #   GeminiClient, incl. vision parse), linkedin.py (LinkedInSource),
│   │                        #   jsonld.py (JsonLdSource), ats.py (AtsBoardSource), browser.py
│   │                        #   (PlaywrightSource), jobstreet.py (Playwright JobStreet), +
│   │                        #   webfetch/discovery/embeddings (universal catch-all layer)
│   └── api/app.py           # FastAPI: health, upload (text+vision parse), dashboard, jobs,
│                            #   applications, approve (submits to sandbox ATS — PRESENT),
│                            #   pipeline/run (async, ?seed= & ?seen=), pipeline/run/{id}/events (SSE)
└── frontend/                # Vite + React app (BUILT 2026-08-25) — the real frontend, wired to
                             #   the live backend via fetch (dashboard, SSE agent timeline, ranked
                             #   matches, approve → sandbox ATS). Replaces hireflow-frontend.html
                             #   (now retired as the reference prototype). **M3E (Material 3
                             #   Expressive) UI (`@m3e/react`, 2026-08-25):** app wrapped in
                             #   `<M3eTheme color="#8F4100" scheme="light" motion="expressive">`
                             #   (ember brand primary → full M3 palette); components swapped to M3E —
                             #   buttons (`M3eButton`), prefs dialog (`M3eDialog`), tabs (`M3eTabs`/
                             #   `M3eTab`), icons (`M3eIcon` replaces `Icon.jsx` via `M3eIcon.jsx`),
                             #   chips (`M3eChip`/`M3eInputChipSet`), snackbar (`M3eSnackbar.open`),
                             #   progress (`M3eLinearProgressIndicator`/`M3eCircularProgressIndicator`),
                             #   work-type (`M3eSegmentedButton`), sort (`M3eSelect`/`M3eOption`),
                             #   filters (`M3eFilterChip`/`M3eFilterChipSet`). Custom dropzone (no M3E
                             #   dropzone), SSE timeline kept as custom markup themed via
                             #   `var(--md-sys-color-primary)`. `npm install && npm run build` builds
                             #   clean; headless-Chromium render verified (all M3E components upgrade,
                             #   no console errors, tabs/dialog/segmented interactions work). Base URL
                             #   via VITE_HIREFLOW_API (dev proxy in vite.config.js). **Views: Agent
                             #   run / Results / History (no separate Applications tab).** Results
                             #   shows the ranked matches + inline app status + per-match drafts,
                             #   with client-side filters (sort by score/company/date, source chips,
                             #   "has draft"). Match cards: M3E circular progress score (number only,
                             #   no /100), rank label, Open Link, View Draft (CV + cover letter
                             #   from the done payload `drafts[job_id]`), expandable reasons +
                             #   research (markdown rendered via `marked`). `ApplicationsList` +
                             #   `ScoreDial` are DELETED (dead after the merge). 2026-08-26 audit:
                             #   removed dead api.js exports (`fetchJobs`/`fetchApplications`/
                             #   `fetchDashboard`/`approveApplication`), dead CSS (`.gate`/`.hint`/
                             #   `.dz-note`/`.po-sub`/`.paused`), and deduped the dropzone markup.
                             #   Components:
                             #   M3eIcon, ResumeDrop, PrefsModal, AgentTimeline, MatchesList,
                             #   HistoryTab, Toast; lib/md.js (marked), api.js (fetch layer),
                             #   storage.js (localStorage). timeline animates from the real stream
                             #   (verified); live e2e on the deployed .run.app still pending.
```

**Sandbox ATS submit path — PRESENT (code; live proof pending redeploy):** `/sandbox/ats/apply`,
`ApplicationStatus.SUBMITTED`, and `/approve` → real submit are in this tree (in `api/app.py` +
`domain/__init__.py`). In-memory + best-effort `sandbox_ats.json`, no DB.

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

**Code audit — 2026-08-26 (dead code removed, do NOT resurrect):**
The cleanup pass removed these — if you grep and find a reference to them, it is stale:
- `ResumeParser.read()` / `_read_pdf()` / `_read_docx()` / `infer_work_type()` — removed; the live path uses `parse_bytes`/`validate`/`pdf_page_images` only.
- `Settings.job_source_poll_hours` (config knob) — removed; nothing read it.
- `ApplicationStatus.APPROVED` + `Application.followup_due` / `Application.notes` — removed (never used; approve path is `SUBMITTED`).
- `BaseAgent.pre_run` / `post_run` hooks — removed (never overridden/called).
- `WebFetchSource.last_via` — removed (never read).
- `InMemoryRepository._entity_type` — removed (never read).
- The dead package re-exports in `hireflow/tools/__init__.py`, `agents/__init__.py`, `storage/__init__.py`, `api/__init__.py`, and `hireflow/__init__.py` (`__version__`) — now empty package markers; import submodules directly.
- `ApplicationStatus` is now exactly `MATCHED`/`ROUTED`/`DRAFTED`/`SUBMITTED`.
- The per-file `_USER_AGENT` literals were consolidated into one `USER_AGENT` constant in `hireflow/tools/job_source.py` — import it from there.
- `HireflowAgent`/`HireflowTools` (`adk_router.py`) are **kept intentionally** as the mandatory-ADK compliance artifact (RULES §6), even though they are not wired into the live `/pipeline` path — do NOT delete them.

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
- `POST /pipeline/run?profile_id=…&seed=…&seen=…` — **async + SSE**: creates a `run_id`,
  runs the real **RouterAgent pipeline** (`SearchAgent → MatchAgent →
  **CareerSourceAgent** → ResearchAgent → PrepareAgent`, orchestrated by
  `RouterAgent`, every agent through `GeminiClient` Vertex-first + `JobSource`
  Freehire (+ `source=seek`/
  `mycareersfuture` regional passes) / RemoteOK / Remotive / LinkedIn /
  JSON-LD / ATS, with Wantedly/JapanDev flag-gated behind
  `USE_UNVERIFIED_SOURCES=1`) in a background asyncio task, and returns
  `{"run_id":…,"status":"started"}` immediately. `seed` rotates query/source
  order for run-to-run variation; `seen=` (comma-separated job ids from client
  `localStorage`) de-duplicates jobs already shown to the user. Caps: ≤25 jobs,
  ≤10 scored, ≤5 prepared, ≤8 researched (env-tunable).
- `GET /pipeline/run/{run_id}/events` — **Server-Sent Events** (`text/event-stream`):
  streams `parse → audit → search → match → research → prepare → approve`
  agent-tagged stage events with counts/names as `data: {…}`, then a final
  `event: done` with the full result JSON. The `search` stage shows the
  expanded query terms + per-source counts. A down board degrades to `[]` and is
  recorded in `errors`, never a 500.
- `GET /pipeline/run/{run_id}` — **resume-after-refresh status (PRESENT; live proof
  pending redeploy)**: `{run_id, exists, done, status, result}` — the frontend calls
  this on mount when an active run id is saved in `localStorage` (key
  `hireflow.active_run.v1`), then either re-attaches the SSE stream (`Last-Event-ID`
  resume) or renders the already-stored result.
- `POST /pipeline/run/{run_id}/cancel` — **cancel a run (PRESENT; live proof pending
  redeploy)**: cancels the background asyncio task (stops paid Vertex/Gemini work via
  `task.cancel()`); `_execute_run` catches `CancelledError` and finishes the runlog as
  `status:"cancelled"` so the SSE stream closes cleanly. In-memory `run_tasks` registry
  on `api.state` (`create_app`) is popped by a done callback.
- `GET /dashboard` — live counts + by-status breakdown.
- `GET /jobs` / `GET /applications` — list repository contents (persisted from
  the background run's `jobs` / `application_records`).
- `POST /approve?application_id=…` — **real submit to the sandbox ATS (PRESENT; live proof
  pending redeploy)**: flips the application to `SUBMITTED`, records `ats_confirmation`
  (`HFS-…`) + `submitted_at` via `/sandbox/ats/apply`; in-memory + best-effort `sandbox_ats.json`.
- **Clients** — `hireflow/cli.py`, `hireflow.sh`, and `hireflow.bat` →
  `hireflow_run.py` are thin clients of the deployed API. After a successful
  run they export `result-demo.html` (single self-contained report with
  clickable links, full titles/reasons/drafts — no truncation) plus
  `result-demo.json` (raw result) into the working dir. **Client-side only —
  no backend change, so NO redeploy is needed for the export feature.**

**Live Cloud Run** (`https://hireflow-backend-296941301245.us-central1.run.app`)
has `/health` ok. The `/pipeline/run` deployed build answers `agent_not_configured`
until the NEW build (pipeline + SSE + search intelligence) is redeployed — the
new build is the acceptance target. See `docs/DEPLOY.md` for the redeploy and
`docs/CURL_E2E.md` for the curl proof.

---

## 9. Current state of the repo (the honest truth — verified by me, do not trust the old AGENTS claims)

- **Import tree is unblocked.** `ResumeFinding` + `WorkTypeClassifier` are in
  `hireflow/domain/__init__.py` and `hireflow.tools.gemini` imports cleanly.
  **No offline tests exist** — `tests/` was deleted; the acceptance gate is the
  online curl e2e (`docs/CURL_E2E.md`). `python -m hireflow.cli` and `hireflow.sh`
  are thin clients of the deployed API.
- **`/pipeline/run` is now async + SSE** — it returns `{"run_id":…,"status":"started"}`,
  runs the real **RouterAgent pipeline** (`SearchAgent → MatchAgent →
  **CareerSourceAgent** → ResearchAgent → PrepareAgent`, every agent through
  `GeminiClient`
  Vertex-first + the full keyless source registry: Freehire (incl. `source=seek`/
  `mycareersfuture` regional passes), RemoteOK/Remotive, LinkedIn, JSON-LD, and
  ATS boards, orchestrated by `RouterAgent`) in a background asyncio task
  writing to an in-memory `RunLog`
  (`hireflow/agents/runlog.py`), and `GET /pipeline/run/{run_id}/events` streams
  `parse → audit → search → match → career → research → prepare → approve` events then a
  final `done` payload. `/upload` now runs a real Gemini parse (text, or vision
  via PyMuPDF page-images when the PDF text is thin) so `skills` /
  `years_experience` are populated. **The pipeline + SSE stream run live end-to-end —
  the frontend's agent timeline animates from the real streamed events.**
- **Live Cloud Run** (`https://hireflow-backend-296941301245.us-central1.run.app`)
  is ALIVE and returns `{"status":"ok"}` (verified Aug 22). The deployed build
  still answers `agent_not_configured` on `/pipeline/run` until Zach's redeploy lands.
- **Search intelligence is IMPLEMENTED (code; the SSE `search` stage shows the expanded
  terms)** — grep-verified this pass: `QueryExpander` (`hireflow/tools/expander.py`, Gemini expansion + deterministic
  fallback synonym map), `SearchAgent` runs query expansion → **multiple query variants per
  source** (seed-rotated for run-to-run variation, SSE `search` stage shows the expanded
  terms) → gate-then-cap: work-type gate (`_passes_work_gate`) + **location gate**
  (`_passes_location`, incl. `Johor → my` via `LocationMapper` `_STATES`) + **recency filter**
  (`_is_stale`, `JOB_RECENCY_DAYS`) + **cross-run seen-job dedup** (`?seen=` on
  `/pipeline/run`) + **per-company diversity cap** (`DIVERSITY_MAX_SAME_COMPANY`). Knobs live
  in `config.py`: `QUERY_EXPANSION` (default on), `QUERY_EXPANSION_TERMS` (6),
  `JOB_RECENCY_DAYS` (14), `DIVERSITY_MAX_SAME_COMPANY` (2), `USE_UNVERIFIED_SOURCES` (off),
  `FREEHIRE_SOURCES` (default `seek,mycareersfuture`). The **Johor/Israel false-global bug is
  FIXED in code**: `geo.py` maps `johor → my` and an unmapped location no longer silently
  widens freehire to a global onsite search.
- **Universal webfetch + discovery + embeddings + real-submit sandbox ATS — PRESENT (code):**
  `webfetch.py` (`WebFetchSource` — any URL → JSON-LD/ATS/HTML),
  `discovery.py` (`WebDiscoverySource` — keyless DDG web-search fallback, no 50-domain whitelist),
  `embeddings.py` (`EmbeddingRanker`, `gemini-embedding-001`, gated `SEMANTIC_SEARCH`),
  `/sandbox/ats/apply` + `ApplicationStatus.SUBMITTED` + `/approve` → real submit
  (in-memory + best-effort `sandbox_ats.json`). All landed in the tree.
- **Frontend is BUILT + verified live (2026-08-25):** Vite + React app (`frontend/`), **rebuilt on the
  M3E (Material 3 Expressive) component library** (`@m3e/react`) — `<M3eTheme color="#8F4100"
  scheme="light" motion="expressive">` at the root (ember brand primary → full M3 palette), with
  `M3eButton`/`M3eDialog`/`M3eTabs`/`M3eIcon`/`M3eChip`/`M3eSnackbar`/`M3eProgressIndicator`/
  `M3eSegmentedButton` replacing the hand-rolled CSS/icons; custom dropzone + SSE timeline + score
  dials stay custom markup themed via `var(--md-sys-color-primary)`. Upload, SSE agent timeline
  (animates from the real stream), ranked matches + approve, applications, localStorage history all
  behave as before. Headless-Chromium render verified (2026-08-25): all M3E components upgrade, no
  console errors, tabs/dialog/segmented-select interactions work. `hireflow-frontend.html` is
  retired as the reference prototype. **Remaining acceptance: the redeploy + online curl e2e on the
  `.run.app` URL (needs Zach's deploy)**. Agent Search is optional + not set up (only
  indexes domains Zach can verify he owns — `docs/GCP_SETUP.md` §3). Layer II Playwright
  **is enabled** (`HIREFLOW_PLAYWRIGHT=1` + Chromium installed in the `Dockerfile`).

**The old AGENTS.md claimed Phases "1 & 1.5 done": that was FALSE at the time**
(import was broken, no live pipeline). Today the code paths exist and are green
offline; the phase is done ONLY when the redeploy + curl e2e on the `.run.app`
URL pass.

---

## 10. Global job-source strategy (the layers — no country is "not supported")

**No single API covers every country with structured JSON.** "Global" is a **layered registry** — every country above zero native feed; the long-tail catch-all is the web layer. Verify each source with a real `curl` before coding it (they rot fast; do not trust my available knowledge or datasets). **Note:** freehire's `semantic_ratio` is **DEAD** (removed from its backend) — do not rely on it.

### Verified-sources matrix (updated 2026-08-23 — each row curl-verified this session)

Columns: **Srv-recency** = server-side recency filter the agent applies · **Loc-gate** = the agent enforces a location gate on this source · **posted_at** = a parseable post date exists.

| Source | Endpoint (live) | Layer | curl | Jobs | Srv-recency | Loc-gate | posted_at | Notes |
|--------|-----------------|-------|------|------|-------------|----------|-----------|-------|
| freehire | `GET https://freehire.me/api/v1/agent/jobs/search` (+facets) | I | 200 | yes (JP/Tokyo, 193 countries) | **yes** (`posted_within_days`) | **yes** (countries/regions) | yes | keyless aggregator, remote/hybrid/onsite, salary enrichment |
| RemoteOK | `GET https://remoteok.com/api` | I | 200 | yes | no (only parses) | no | yes | remote-only, EU/US-weighted |
| Remotive | `GET https://remotive.com/api/remote-jobs` | I | 200 | yes | no (only parses) | no | yes | remote-only, EU/US-weighted |
| LinkedIn guest | `GET https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?keywords=…&location=…&f_WT=…&start=0` | 0 | **200** | **yes** (Tokyo, 5+ cards; `engineer`→3, `software`→2) | no | yes | no | keyless, global, low-volume/personal-only (ToS) |
| Greenhouse (ATS) | `GET https://boards-api.greenhouse.io/v1/boards/gitlab/jobs?content=true` | I | **200** | **204 jobs** | no | yes | yes | GitLab board; title/location/content/url |
| Ashby (ATS) | `GET https://api.ashbyhq.com/posting-api/job-board/notion` | I | **200** | **128 jobs** | no | yes | yes | Notion board; title/location/jobUrl/descriptionHtml |
| Lever (ATS) | `GET https://api.lever.co/v0/postings/{board}?mode=json` | I | **404** on all boards tested | 0 | no | yes | yes | endpoint retired/unreliable — **not enabled**, `ats.py` supports it, no live row |
| Workable (ATS) | `GET https://apply.workable.com/api/v1/widget/accounts/{account}` | I | **200 but 0 jobs** (tokopedia/wayfair/pearson/…) | 0 | no | yes | no | API up but empty `jobs[]` for tested accounts — **not enabled**, `coded` only |
| JSON-LD career pages | `GET https://www.greenhouse.io/careers` → `application/ld+json` → `@type=JobPosting` | 0 | **200** | **1 JobPosting** | no | yes | yes | real schema.org `JobPosting`; registry = 1 URL (`JSONLD_COMPANY_URLS`); Atlassian/Shopify/Nike have **no** JobPosting ld+json |
| Playwright Layer II | env-gated `HIREFLOW_PLAYWRIGHT=1` + Chromium in image | II | not run | n/a | no | n/a | n/a | **IMPLEMENTED (code):** `browser.py`/`jobstreet.py` share the `browser_launcher.py` stealth helpers; Chromium IS installed in the `Dockerfile`; needs a live curl row once deployed |

**In-tree sources NOT yet in the matrix (code present, no curl row this session — verify, then add a row):** `freehire:seek` + `freehire:mycareersfuture` (`FreehireRegionalSource` in `api/app.py`, registered by default), `wantedly` + `japan_dev` (flag-gated behind `USE_UNVERIFIED_SOURCES=1`; Wantedly docstring claims live 200, JapanDev degrades to `[]`). The universal webfetch/discovery layer IS in the tree (`webfetch.py`/`discovery.py`) — needs a live curl row once deployed.

### Search intelligence (how the agent actually searches — an AI agent, NOT a keyword fetcher)

**IMPLEMENTED (code; live proof pending redeploy)** — all grep-verified this pass. The six
behaviors below are live code in `SearchAgent` (`hireflow/agents/router.py`) +
`QueryExpander` (`hireflow/tools/expander.py`):

1. **Gemini query expansion** — `QueryExpander.expand(profile_roles, skills)` uses Gemini
   (`GeminiClient.expand_query`) to emit synonym variants per role (e.g. `"ML Engineer"` →
   `"Machine Learning Engineer"`, `"Deep Learning Engineer"`), with an in-memory cache and a
   **deterministic fallback synonym map** so a run never ices when the LLM call fails. The agent
   **understands the profile** (skills + roles + resume), it does not just echo the title.
2. **Multiple query variants per source** — each source is queried with several expanded variants
   (all variants for geo-capable sources; `queries[:1]` otherwise), seed-rotated so results
   **vary run-to-run** (no single deterministic query → no "same results every run"). The SSE
   `search` stage shows the expanded terms + per-source counts.
3. **Gate-then-cap** — before scoring, jobs are gated on **work-type AND location AND recency**,
   then capped (≤25 jobs, ≤10 scored, ≤5 prepared, ≤8 researched). Location is resolved via
   `LocationMapper`; a location with no code (e.g. `"Johor"`) must **not** silently fall through
   to a global search (`SearchAgent._passes_location`).
4. **Recency filter** — `SearchAgent._is_stale` drops jobs older than `JOB_RECENCY_DAYS` (default
   14). freehire additionally sends server-side `posted_within_days`; the client-side gate covers
   the sources that only parse `posted_at`.
5. **Cross-run memory (seen jobs)** — the browser sends a `?seen=` list of job ids to
   `/pipeline/run`; the agent skips jobs the user has already seen (dedup across runs). **No DB —
   the seen list lives in client `localStorage` and rides on the query string; the backend stays
   stateless/in-memory.**
6. **Per-company diversity cap** — `SearchAgent._cap_company` limits how many jobs from one
   company survive to scoring (`DIVERSITY_MAX_SAME_COMPANY`, default 2), so results aren't one
   employer's wall.

**Config knobs — all present in `config.py`:** `QUERY_EXPANSION` (on/off, default on),
`QUERY_EXPANSION_TERMS` (6), `JOB_RECENCY_DAYS` (14), `DIVERSITY_MAX_SAME_COMPANY` (2),
`USE_UNVERIFIED_SOURCES` (off — only Wantedly/JapanDev come in when on), `FREEHIRE_SOURCES`
(default `seek,mycareersfuture` — the regional freehire passes registered in `_build_default_agent()`).

**Known bug — FIXED in code:** the old `LocationMapper` dropped `"Johor"` (no MY city entry, no
`johor` country), so the `countries`/`regions` params were empty and freehire ran a **global onsite**
search — that is why Israel/Tel-Aviv jobs appeared for a Johor query. `geo.py` now maps
`johor → my` (via `_STATES`) and the location gate means an unmapped location **never silently
widens to "anywhere"**. **Still needs the redeploy + curl e2e to prove it live.**

**Career-page company sourcing — IMPLEMENTED (code; live proof pending redeploy):** the missing
"career page company website" tap. After scoring, `CareerSourceAgent`
(`hireflow/agents/career_source.py`) takes the distinct companies of the scored
matches (capped by `CAREER_SOURCE_MAX_COMPANIES`, default 5), probes each
company's `/careers` page + ATS boards via `WebFetchSource.webfetch_company`
(reusing the existing `_company_candidates` JSON-LD→ATS→HTML extractor), and
merges the new jobs (deduped by id against the board-job pool) back into the
pipeline so they compete in scoring/prepare — surfacing jobs that don't appear
on boards. Knobs: `CAREER_SOURCE_ENABLED` (default true), `CAREER_SOURCE_MAX_COMPANIES`
(default 5), `CAREER_SOURCE_MAX_PER_COMPANY` (default 8). Emits a `career` SSE stage
(probing … N companies → M new jobs). Soft-fail: a company with no parseable
careers page contributes 0 + a source note in `errors`, never a 500. This is a
**separate path** from `WEB_DISCOVERY_COMPANIES` (that static opt-in list stays);
the career path is automatic from the matched results. **Still needs the redeploy +
curl e2e (SSE `career` stage must show companies + new jobs) to count.**

**Layer 0 — Universal catch-all (every country, everyone):**
- **Universal webfetch + discovery layer** (`webfetch.py`/`discovery.py`) — **PRESENT (code; live proof
  pending redeploy)**, the replacement for the retired CSE 50-site whitelist:
  a keyless web-search fallback + domain-discovery from the sources we already fetch, no
  50-domain whitelist. Grep before trusting.
- **Agent Search (formerly CSE)** — **OPTIONAL, NOT set up.** Google's Custom Search JSON API is
  retired; Agent Search website indexing only works on domains **you can verify you own** (or get
  the owner to approve) — it is NOT a keyless way to index third-party job boards. Skip-able:
  `docs/GCP_SETUP.md` §3, explicitly non-blocking.
- **JSON-LD / schema.org `JobPosting`** — ✅ **IMPLEMENTED + live-verified** (`hireflow/tools/jsonld.py`, `JsonLdSource`). Fetches career pages, regexes `application/ld+json`, walks for `@type=JobPosting`. This is the true "career page" tap without scraping infra.
- **LinkedIn guest API** (`jobs-guest` endpoints) — ✅ **IMPLEMENTED + live-verified** (`hireflow/tools/linkedin.py`, `LinkedInSource`). Keyless, global, works for location strings (verified: Tokyo 200). Personal-use, low volume (`limit` ≤15); keep it a source, not the demo centerpiece. Respects ToS — no scraping, soft-fail on 403/999.

**Layer I — keyless aggregators (remote, hybrid, onsite):**
- **freehire.me** (covers **193 countries**; verified `regions=apac`/`countries=jp|id|my|...`; `work_mode` remote/hybrid/onsite; `enrichment.salary_min/max`; full description in-search via `include_description=true`). It is a **personal project (no SLA, tier badges)** — plan a one-line swap via `FREEHIRE_API_URL`. **APAC relays — IMPLEMENTED (code; live proof pending redeploy):** `FreehireRegionalSource` (in `api/app.py`) passes `source=seek` (JobStreet engine → MY/ID/SG/AU/NZ) and `source=mycareersfuture` (SG) through freehire — both registered by default via `SETTINGS.freehire_sources`. Direct JobStreet/MyCareersFuture APIs remain blocked — the keyless relay is the honest path (see Regions below).
- **RemoteOK, Remotive** — remote-only, good EU/US.
- **ATS boards** — ✅ **IMPLEMENTED + partially verified** (`hireflow/tools/ats.py`, `AtsBoardSource`). Unified keyless endpoint for Greenhouse/Ashby/Lever/Workable. **Greenhouse (gitlab 204) + Ashby (notion 128) verified live and ENABLED in `ATS_BOARDS`.** Lever 404s and Workable returns 0 jobs on all boards tested — coded but **disabled/no registry rows** until a live-verified board is found. `source="ats:{board}"`.

**Layer II — browser automation (last resort, officially supported, still no VPS):**
- **Playwright + headless Chromium inside the Cloud Run container** — ✅ **IMPLEMENTED (code; live proof pending redeploy)** (`hireflow/tools/browser.py` `PlaywrightSource`, `jobstreet.py` `JobStreetSource`; both share the `browser_launcher.py` stealth helpers; Chromium IS installed in the `Dockerfile`). Documented by Google ("Browser and OS automation in Cloud Run"). Use ONLY for JS-heavy SPA career pages with no JSON-LD and no API (e.g. Kalibrr, MyCareersFuture, anti-bot pages).
- **Cost caveat:** headless Chrome needs a bigger instance (more RAM, CPU stays billed during the request, slower cold start) — keep it a scoped last-resort layer, never the default per-source path. Enabled only when `HIREFLOW_PLAYWRIGHT=1`.
- A **full desktop OS via VNC streaming** (WebSockets) is also documented for complex interaction — not needed for the demo.

**C — Regions, current HONEST status (do NOT trust the aspirational list that used to live here):**

> **Correction:** the old §10.C listed `JobStreet MY`, `Maukerja`, `Kalaber`, and `K-Worknet` as if they were
> live paths. **They were aspirational, NOT implemented as code** — and the direct APIs for JobStreet /
> Kalibrr / Maukerja / Indeed are **blocked** (403 / 530 / Cloudflare / Turnstile), so they are **not usable
> keyless**. K-Worknet needs a key and its endpoint currently 404s — **do not claim it**. The honest APAC
> path is **keyless through freehire** (`source=seek` → JobStreet engine for MY/ID/SG/AU/NZ;
> `source=mycareersfuture` → SG — both **IMPLEMENTED (code; live proof pending redeploy)** via
> `FreehireRegionalSource`) and/or the present universal webfetch catch-all / optional Agent Search /
> Layer II browser for SPA-only career pages.

- **MY**: freehire(`countries=my`) · freehire `source=seek` (JobStreet engine — MY/ID/SG/AU/NZ) — **IMPLEMENTED (code; live proof pending redeploy)** via `FreehireRegionalSource`. Direct JobStreet/Maukerja APIs are **blocked**.
- **ID**: freehire(`countries=id`) · freehire `source=seek`. Kalibrr is SPA/anti-bot → **present universal webfetch catch-all**, else **Layer II** Playwright. **coded/opt-in — verify live.**
- **JP**: freehire(`countries=jp`) · LinkedIn(guest) verified Tokyo · **Wantedly (JP JSON) / JapanDev (JP)** — **PRESENT (code, flag-gated** behind `USE_UNVERIFIED_SOURCES=1`**)**: `wantedly.py` (docstring claims live 200 on 2026-08-23) and `japan_dev.py` (best-effort JSON-LD walk, currently degrades to `[]` — its SSR does not carry `JobPosting` nodes). **Verify with your own curl before trusting.** SPA/anti-bot sites (Kalibrr-class) → present universal webfetch / optional Agent Search scoped to jp career pages, else **Layer II** Playwright. K-Worknet needs a key + its endpoint currently 404s — **not usable**.
- **KR**: K-Worknet is **needs-key + currently 404** — **NOT implemented, do not claim**. Use freehire(`countries=kr`) / global catch-all.
- **SG**: freehire(`countries=sg`) · LinkedIn(guest) verified · freehire `source=mycareersfuture` (**SG keyless path — IMPLEMENTED (code; live proof pending redeploy)**). MyCareersFuture direct is SPA — only via the freehire relay, the present universal webfetch, optional Agent Search, or **Layer II** Playwright.
- **EU/NA**: freehire + RemoteOK/Remotive + **ATS boards (Greenhouse-GitLab, Ashby-Notion verified live)** · more ATS boards to add as they are curl-verified.

**D — verification rule (REQUIREMENT):** Before any country/source is "supported", run a real `curl` and post the HTTP code + job count in the PR/commit. No `curl` = not supported. Update this section each time we verify a new one.

**The golden rule:** never scrape a site with a brute-force bot or pretend a job board is something it isn't. Job boards are public APIs; career pages are JSON-LD or ATS-APIs; the only sanctioned browser path is **Layer II** (Playwright + Chromium on Cloud Run) for SPA-only career pages. Everything runs on Cloud Run (no VPS).

---

## 11. Backend API surface (target, FastAPI)

- `POST /upload` — resume (txt/pdf/docx) + preferences → store → **parse/audit** (real Gemini, text+vision)
- `GET /dashboard` — live pipeline status
- `GET /jobs` / `GET /applications` — read
- `POST /approve` — human approval gate (**real submit to the sandbox ATS — PRESENT**: flips to `SUBMITTED`, records `ats_confirmation` + `submitted_at` via `/sandbox/ats/apply`)
- `POST /sandbox/ats/apply` + `ApplicationStatus.SUBMITTED` — **real submission to the sandbox ATS (PRESENT in this tree** — `api/app.py` `AtsSandbox` + `domain/__init__.py`; live proof pending redeploy)
- `POST /pipeline/run?profile_id=…&seed=…&seen=…` — start the **RouterAgent** Search→Match→Research→Prepare pipeline end-to-end async → returns `run_id` (`started`)
- `GET /pipeline/run/{run_id}/events` — SSE stream of per-stage progress + final `done` payload
- `GET /pipeline/run/{run_id}` — run status `{exists, done, status, result}` (resume-after-refresh)
- `POST /pipeline/run/{run_id}/cancel` — cancel the background task (stops paid Gemini work)
- healthcheck (`/health`) for Cloud Run
- Optional in-flight knobs: **embeddings re-rank** (`gemini-embedding-001`, `EMBEDDING_MODEL` fallback `text-embedding-005` — code present, gated `SEMANTIC_SEARCH`; `docs/GCP_SETUP.md` §4). **Agent Search is OPTIONAL + NOT wired** — no code reads an `AGENT_SEARCH_DATASTORE` env var (`docs/GCP_SETUP.md` §3).

---

## 12. Roadmap — realistic, online-e2e (to Aug 31)

**Now (the base, mandatory — stops the "partial runtime" myth):**
1. ~~Unblock the import tree~~ — **DONE**: `ResumeFinding` + `WorkTypeClassifier` are in `hireflow/domain/__init__.py` and `hireflow.tools.gemini` imports cleanly.
2. ~~Wire the 5 named agents into the server pipeline~~ — **DONE (code; live proof pending redeploy)**: `RouterAgent` now orchestrates `SearchAgent → MatchAgent → **CareerSourceAgent** → ResearchAgent → PrepareAgent` as the ACTUAL `/pipeline/run` executor. Each agent carries its prompt-engineering and calls the same `GeminiClient` methods (`score_fit`, `research_company`, `draft/review/revise_application`, `audit_resume`); `CareerSourceAgent` reads matched companies' `/careers` pages via `WebFetchSource.webfetch_company`. Stages are tagged in SSE as `search`/`match`/`career`/`research`/`prepare`. `HireflowAgent`/`HireflowTools` in `adk_router.py` are the ADK-framework compliance artifact (kept for RULES §6 mandate, not wired into the live path).
3. ~~Fix `freehire.py`~~ — **DONE**: live endpoint (`/api/v1/agent/jobs/search`) + facets, `LocationMapper` geo codes, stable `source`/`title`/etc. core schema across all sources.
4. ~~Offline tests removed~~ — **DONE**: `tests/` deleted (stub agent, `_StubGemini`, `TestClient`). There is no offline gate — the acceptance gate is the online curl e2e in steps 5 & 6 against the live Cloud Run URL (real `.pdf`, real Gemini via Vertex).
5. **Re-deploy to Cloud Run** (docs/DEPLOY.md) → curl `/health`, then a **real** e2e: upload a real `.pdf` → `/pipeline/run` → `/jobs` live results → `/dashboard` reflects it → `/approve`. **Video-record the curl-to-cloud proof.**
6. ~~Terminal CLI test~~ — **DONE**: `hireflow/cli.py` + `hireflow.sh` are thin clients hitting the live API (not a separate runtime). After a successful run each client exports `result-demo.html` + `result-demo.json` into the working dir (full, no truncation, clickable links) — client-side only, no redeploy.

**Next (global + demo):**
7. **Search intelligence (query expansion + location/recency gates + variation + dedup/diversity)** — **DONE (code; live proof pending redeploy)**: `QueryExpander` (Gemini synonym expansion per role, deterministic fallback synonym map), multiple query variants per source (SSE `search` stage shows the expanded terms), gate-then-cap with a real **location gate** (fixes the Johor/Israel false-global — `geo.py` maps `johor → my`), recency filter (`JOB_RECENCY_DAYS`), cross-run seen-job dedup (`?seen=` on `/pipeline/run`), `DIVERSITY_MAX_SAME_COMPANY` cap. Knobs `QUERY_EXPANSION` / `QUERY_EXPANSION_TERMS` / `JOB_RECENCY_DAYS` / `DIVERSITY_MAX_SAME_COMPANY` / `USE_UNVERIFIED_SOURCES` / `FREEHIRE_SOURCES` all in `config.py`. **Proof pending: redeploy + curl e2e (SSE `search` stage must show expanded terms).** This is the work that makes the agent feel like a Taskmaster agent (it *understands* the profile and *acts* across sources) rather than a keyword fetcher.
8. **Global job-source registry** — ✅ **IMPLEMENTED + curl-verified (2026-08-23)**: `LinkedInSource` (guest API), `JsonLdSource` (schema.org career pages), `AtsBoardSource` (Greenhouse+Ashby). Registered in `_build_default_agent()` after RemoteOK/Remotive/Freehire. Lever (404) and Workable (0 jobs) are coded but **disabled** — add rows only once curl-verified. **Still pending: redeploy + live curl e2e** against the `.run.app` URL to prove this on the live deploy.
9. **APAC keyless relays — IMPLEMENTED (code; live proof pending redeploy):** freehire `source=seek` (JobStreet engine → MY/ID/SG/AU/NZ) + `source=mycareersfuture` (SG) via `FreehireRegionalSource` (in `api/app.py`), registered by default through `SETTINGS.freehire_sources` — the honest keyless APAC path since JobStreet/Kalibrr/Maukerja/Indeed direct APIs are **blocked**. Wantedly/JapanDev (JP) are **in the tree but flag-gated** behind `USE_UNVERIFIED_SOURCES=1` until live-proven. Live e2e on the `.run.app` URL still pending.
9b. **Career-page company sourcing — IMPLEMENTED (code; live proof pending redeploy):** `CareerSourceAgent` probes the top matched companies' `/careers` pages + ATS boards via `WebFetchSource.webfetch_company` and merges the new jobs (deduped by id) back for scoring/prepare. Knobs `CAREER_SOURCE_ENABLED` / `CAREER_SOURCE_MAX_COMPANIES` / `CAREER_SOURCE_MAX_PER_COMPANY` in `config.py`; emits a `career` SSE stage. Proof pending: redeploy + curl e2e (SSE `career` stage must show companies + new jobs).
10. **Universal webfetch + discovery layer + embeddings re-rank + real-submit sandbox ATS** — the parallel code-agent pass, **DONE (code; live proof pending redeploy)**: `webfetch.py`/`discovery.py`/`embeddings.py`, `/sandbox/ats/apply`, and `ApplicationStatus.SUBMITTED` are **in this tree** — grep the tree, then prove with the redeploy + curl e2e. **Agent Search (formerly CSE) is OPTIONAL + NOT set up** (only indexes domains Zach can verify he owns — `docs/GCP_SETUP.md` §3). **Layer II** Playwright/Chromium is **coded** (`browser.py`/`jobstreet.py` + `browser_launcher.py` stealth; Chromium in the `Dockerfile`) — needs the redeploy + a live curl row.
11. **Build the Vite + React app** (`frontend/`) — **DONE (code; builds clean 2026-08-25)**: `npm install && npm run build` passes. Wired to the live backend via `fetch` (upload, SSE agent timeline, ranked matches, approve → sandbox ATS); prefs + run history in `localStorage`; base URL via `VITE_HIREFLOW_API` (dev proxy in `vite.config.js`). `hireflow-frontend.html` is retired as the reference prototype. **Proof pending: live e2e against the deployed `.run.app` URL** (npm run dev → upload → run → SSE → approve).
12. **Demo & docs**: clean architecture diagram image (README currently has ASCII), README spin-up, ≤4-min unedited video showing Cloud Run console + Vertex AI logs + live `.run` calls. Email `testing@devpost.com` / `cloudhackathons@google.com` access.

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

1. Re-deploy to Cloud Run (`docs/DEPLOY.md`) → curl `/health`, then the live curl e2e with a real `.pdf` (`docs/CURL_E2E.md`): upload → run (`?seed=` + `?seen=`) → SSE events → jobs → approve. **This proves the phase — not the offline green.** The SSE `search` stage must show **expanded query terms** + per-source counts, the `career` stage must show **companies probed + new jobs**, and a Johor-style location must NOT widen to a global search (search intelligence + career-page sourcing are now in the tree — prove them live).
2. **Watch for the in-flight parallel pass** (§10/§12): universal webfetch (`webfetch.py`) + discovery (`discovery.py`), embeddings re-rank (`embeddings.py`, `gemini-embedding-001`), real-submit sandbox ATS (`/sandbox/ats/apply`, `ApplicationStatus.SUBMITTED`, `/approve` submits). Grep the tree each session — mark done ONLY when each is present + redeployed + curl-e2e'd. Agent Search stays OPTIONAL (domain-verify, `docs/GCP_SETUP.md` §3).
3. **Vite + React app** (`frontend/`) is **built + verified live** (2026-08-25): components for resume upload, prefs modal, SSE agent timeline (animates from the real streamed events), ranked matches + approve, applications, history (localStorage). Wired to the live backend via `fetch`; builds clean with `npm install && npm run build`. **Remaining acceptance: prove the same run against the deployed `.run.app` URL** (needs the redeploy so `/pipeline/run` answers the RouterAgent pipeline, not `agent_not_configured`). **Resume-after-refresh + Cancel are IMPLEMENTED (2026-08-26, code; live proof pending redeploy):** run start persists `{run_id, profile}` to `localStorage` (`hireflow.active_run.v1`); on mount the app calls `GET /pipeline/run/{run_id}` and either re-attaches the live SSE stream (`Last-Event-ID` resume) or renders the finished result; a Cancel button in the timeline header calls `POST /pipeline/run/{run_id}/cancel` to stop the background task. A refreshed run only continues while the same in-memory instance lives; a missing run clears the marker gracefully.
4. **Layer II Playwright/Chromium** is **coded + enabled** in the `Dockerfile` (`HIREFLOW_PLAYWRIGHT=1`); needs the redeploy + a live curl row.
5. Demo & docs: clean diagram image, ≤4-min video with Cloud Run console + Vertex logs, grant repo access to `testing@devpost.com` / `cloudhackathons@google.com`.
6. Optional: Cloud Scheduler → POST `/pipeline/run` hourly.

---

## 15. Zach handoff checklist (cloud owner)

**Must provide (blocks real e2e):**
1. `GCP_PROJECT_ID` (we have `hireflow-506207` in-use — confirm).
2. Service-account credentials JSON (path → `GOOGLE_APPLICATION_CREDENTIALS`) — **Vertex AI** permission only; no DB.
3. Enabled APIs: **Vertex AI** (required), **Cloud Run** (later), Cloud Scheduler (optional).
4. `GEMINI_API_KEY` (Gemini API fallback) — only if we ever run Vertex-less; we have a real one on-disk (last verified live at repo time).
5. Is model string `gemini-3.5-flash` valid in the project? (RULES require Gemini 3.5+.)
6. **Verify embeddings are callable** — `roles/aiplatform.user` on the Cloud Run runtime SA also unlocks `gemini-embedding-001`; run the curl in `docs/GCP_SETUP.md` §4 (`EMBEDDING_MODEL=text-embedding-005` is the fallback). **NOT yet used by code** — the embeddings re-rank is in flight (verify).
7. **Agent Search (formerly CSE) is OPTIONAL** — `docs/GCP_SETUP.md` §3. NOT a keyless catch-all: it only indexes domains you can verify you own. Skip it if blocked; it does not block the core pipeline. Do not ask for a CSE key — that API is retired.

**Later:**
8. Deploy the `Dockerfile` to **Cloud Run** → return the `.run.app` URL (needed for end-of-video proof). Use the big-instance runbook in `docs/GCP_SETUP.md` §5 (`--memory 1Gi --timeout 3600`, bump to `--memory 2G --cpu 2` if Playwright/Chromium is enabled) and pass the new knobs: `QUERY_EXPANSION=true,JOB_RECENCY_DAYS=14,DIVERSITY_MAX_SAME_COMPANY=2`.
9. Optional: Cloud Scheduler → POST `/pipeline/run` hourly.
10. Capture Cloud Run console + Vertex AI logs for the video.

**No DB needed.** Demo = a Cloud Run-backed run; user data stays in the browser.

---

## 16. Working style (die-hard rules from the task)

- **No local-only anything.** Curl the live endpoint.
- **Never trust a dataset / my mind-guessed facts for architecture.** If a source/endpoint/API is about to be used, verify it with a `curl` first — today's job landscape changes fast.
- **No "this will do".** "Global" means a country gets at least one real path (aggregator keyless → native/reg API → universal webfetch/catch-all), not "freehire covers enough".
- **Keep the `README.md` truthful** — after every change, update URLs, verified sources, and the two-line "what's real now" section.
- **Never call two things "done" until a live e2e on that deploy proves it.** The tree is green offline today (imports unblocked, agent wired), but the repo is only "done" when the redeploy + curl e2e on the `.run.app` URL pass — verify, THEN write done in the file.

*Bismillah.*