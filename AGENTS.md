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
| Coding + backend | **You** (with your AI) | ADK agent, FastAPI, job-source clients, single-file HTML UI, demo video |
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
| Frontend | Single-file HTML (`hireflow-frontend.html`) — mock UI today, **wired to the deployed FastAPI via fetch** once the CLI e2e passes |
| Database/state | **No SQL**. Browser `localStorage` owns prefs + history; backend is stateless, in-memory only for a run |
| Hosting | **Cloud Run** (scale-to-zero) |
| Scheduling | **Cloud Scheduler** → `POST /pipeline/run` (job polling) — optional |
| Job sources | **Global source registry — keyless + native APIs + fallback CSE/JSON-LD** (details §10). Never "remote-only" nor "US-only" |
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

## 5. Architecture (multi-agent)

```
[User] → [hireflow-frontend.html → fetch to FastAPI] → [ROUTER (ADK orchestrator)]
                                                        │
                  ┌─────────────────────────────────────┼────────────────────────────┐
                  ▼                                     ▼                            ▼
         SearchAgent                         MatchAgent(CV Analysis)      ResearchAgent
         search_jobs(global registry)       parse_resume()/audit()/      company_research()
                                            score_fit()
                  └─────────────────────────────────────┼────────────────────────────┘
                                                        ▼
                                       PrepareAgent: DRAFTER → REVIEWER → REVISE
                                                        ▼
                                              [ HUMAN APPROVAL GATE ]
                                                        ▼
                                        Browser localStorage (history + tracking)
```

MVP agents: **Search, Match/Analyze, Research, Prepare (drafter→reviewer→revise)**. Tracking = passive localStorage/dashboard. No DB.

State story (judge-grade): **client-side persistence, stateless backend.** Nothing sensitive is ever stored server-side.

---

## 6. OOP conventions (STRICT — past violations cost us a broken tree)

- **All backend code object-oriented.** No free functions doing work; logic lives in classes.
- Abstract base classes define contracts:
  - `hireflow/storage/` → `Repository` (ABC): `InMemoryRepository` (default)
  - `hireflow/agents/` → `BaseAgent` (ABC): `SearchAgent`, `MatchAgent`, `ResearchAgent`, `PrepareAgent`, `RouterAgent`
  - `hireflow/tools/` → `JobSource` (ABC): `RemoteOKSource`, `RemotiveSource`, `FreehireSource` (+ any new global sources)
  - `hireflow/tools/` → `GeminiClient` — THE only LLM entry point. No alternative/fallback LLM path, no stub.
- Domain models in `hireflow/domain/` — plain typed classes, no framework imports:
  - `Profile` (incl. `residence`, `work_type`, preferred `locations`, `salary_floor`)
  - `JobPosting`, `JobMatch`, `Application` (+ `ApplicationStatus`)
  - **`ResumeFinding`** — NEEDED but NOT YET present (missing from the tree — see §9; this breaks `GeminiClient.audit_resume`, which imports it: `from hireflow.domain import JobPosting, Profile, ResumeFinding`).
  - **`WorkTypeClassifier`** — NOT YET present (do not silently assume it exists).
- **Naming:** classes `PascalCase`, methods/vars `snake_case`, constants `UPPER_SNAKE`, private helpers `_underscore`.
- **No code comments unless asked.**
- Type hints everywhere (Python 3.11+).
- Frontend OOP rules don't apply; no build tool.

---

## 7. File layout (repo — reality as of Aug 22)

```
.
├── AGENTS.md                # this file — the memory
├── README.md                # NEVER lie; update after every deploy with real URLs
├── hireflow-frontend.html   # single-file UI (mock today → real fetch wiring)
├── requirements.txt
├── Dockerfile
├── .gitignore
├── RULES.md                 # official hackathon rules — read before decisions
├── chat/chat.py             # terminal chat against REAL GeminiClient (proves Gemini works)
├── hireflow/
│   ├── config.py            # Settings (project id, model, vertex/api-key flags, thresholds 80/60)
│   ├── domain/__init__.py   # Profile, JobPosting, JobMatch, Application, ApplicationStatus
│   │                        #  MISSING (must add): ResumeFinding (blocks import), WorkTypeClassifier
│   ├── storage/             # Repository ABC + InMemory + Firestore(optional) + StorageFactory
│   ├── agents/              # BaseAgent ABC, router.py (Search/Match/Research/Prepare/Router),
│   │                        #   adk_router.py (HireflowAgent + HireflowTools, Google ADK)
│   ├── tools/               # JobSource ABC, RemoteOK, Remotive, Freehire, resume_parser,
│   │                        #   gemini.py (REAL GeminiClient)
│   └── api/app.py           # FastAPI: health, upload, dashboard, jobs, applications, approve, pipeline/run
├── tests/test_app.py        # the ONLY test file today (others existed only as cached .pyc)
└── web/                     # unused — frontend lives in hireflow-frontend.html
```

**Ghosts of the tree — do NOT restore them as ground truth:**
- `cli.py` — **was never committed** (only `.pyc` proved it existed). We WILL build it as a thin client calling the deployed API for a terminal e2e.
- `json_repository.py`, `openrouter.py`, `mock_gemini.py` — existed only as `.pyc`; do NOT take them as ground truth.

---

## 8. Backend API surface (FastAPI) — current state (real!)

- `GET /health` → `{"status":"ok"}` — live, works (verified Aug 22).
- `POST /upload` — stores profile in in-memory repo. **does not parse/run yet.**
- `GET /dashboard` — counts only, no pipeline progress.
- `GET /jobs` / `GET /applications` — list repository contents.
- `POST /approve` — flips an application to approved.
- `POST /pipeline/run` — **returns `agent_not_configured`** because `create_app()` default `agent=None` (see `hireflow/api/app.py:71`). THIS ONLY RUNS WHEN AGENT IS SELF-WIRED. **TODO: construct real `GeminiClient` + `HireflowTools` + `HireflowAgent` in `create_app` and pass it in.**

---

## 9. Current state of the repo (the honest truth — verified by me, do not trust the old AGENTS claims)

- **Chat breaks on import:** `chat/chat.py` and anything importing `hireflow.tools.gemini` fails with `ImportError: cannot import name 'ResumeFinding' from 'hireflow.domain'` — because `ResumeFinding` (and `WorkTypeClassifier`) were committed. This single missing class is the reason **tests today are brick-red** (`tests/test_app.py` fails at collection) and the reason chat can't even be tested.
- **Live Cloud Run** (`https://hireflow-backend-296941301245.us-central1.run.app`) is ALIVE and returns `{"status":"ok"}` (verified Aug 22) — it predates the broken import.
- There is **no real end-to-end path** through anything today until we: (1) add `ResumeFinding` (fix import -> chat works); (2) wire `GeminiClient` into `create_app` (fix `/pipeline/run`); (3) deploy those two fixes to Cloud Run; (4) verify e2e via curl with a real `.pdf`.

**The old AGENTS.md claimed Phases "1 & 1.5 done": that is FALSE.** Phase 0/EA scaffolded; Phase 1 partially (ADK graph exists, but pipeline never walked end-to-end); Phase 1.5 (CLI) was built locally then never committed, and never tested online. Everything must be re-supported by LIVE tests.

---

## 10. Global job-source strategy (the layers — no country is "not supported")

**No single API covers every country with structured JSON.** "Global" is a **layered registry** — every country above zero native feed; the long-tail catch-all is the web layer. Verify each source with a real `curl` before coding it (they rot fast; do not trust my available knowledge or datasets).

**Layer 0 — Universal catch-all (every country, everyone):**
- **Google Custom Search JSON API** (CSE) — search expression restricted to job sites/ATS domains per country (e.g. `site:careers.x jp`). Needs a CSE **API key + engine ID** from Zach (one-time, free tier ~100 queries/day, fine for the demo, paid for scale). This is the "any country" floor — the moment CSE/CDN-JSON exists for a country, we can search it.
- **JSON-LD / schema.org `JobPosting`** — parse structured data out of any company's career page HTML (`httpx` + regex). This is the true "career page" tap without scraping infra.
- **LinkedIn guest API** (`jobs-guest` endpoints) — keyless, global, works for location strings (verified: Tokyo returned 200). Personal-use, low volume; keep it as a source, but not the demo centerpiece.

**Layer I — keyless aggregators (remote, hybrid, onsite):**
- **freehire.me** (covers **193 countries**; verified `regions=apac`/`countries=jp|id|my|...`; `work_mode` remote/hybrid/onsite; `enrichment.salary_min/max`; full description in-search via `include_description=true`). It is a **personal project (no SLA, tier badges)** — plan a one-line swap via `FREEHIRE_API_URL`.
- **RemoteOK, Remotive** — remote-only, good EU/US.

**C — Regions, currently curated:**
- **MY**: freehire(my) · JobStreet MY · Maukerja
- **ID**: freehire(id) + JobStreet ID · (Kalibrr is SPA-only; use page/JSON-LD)
- **JP**: freehire(jp) · Wantedly/Sapphire are SPA/anti-bot → use **CSE scoped to jp career pages** · K-Worknet (KR)
- **KR**: K-Worknet (**official public job API**, free key, ktor-friendly)
- **SG**: freehire(sg) · MyCareersFuture (SPA — read its real JSON feed if you can establish it; else CSE `domain:careers.gov.sg`)
- **EU/NA**: freehire + RemoteOK/Remotive + ATS boards (Greenhouse/Lever/Ashby/Workable — verified keyless for Greenhouse-GitLab, Ashby-Notion, Workable-Tokopedia)

**D — verification rule (REQUIREMENT):** Before any country/source is "supported", run a real `curl` and post the HTTP code + job count in the PR/commit. No `curl` = not supported. Update this section each time we verify a new one.

**The golden rule:** never scrape a site with a brute-force bot or pretend a job board is something it isn't. Job boards are public APIs; career pages are JSON-LD or ATS-APIs; everything runs on Cloud Run (no VPS).

---

## 11. Backend API surface (target, FastAPI)

- `POST /upload` — resume (txt/pdf/docx) + preferences → store → **trigger parse/audit** (real Gemini)
- `GET /dashboard` — live pipeline status
- `GET /jobs` / `GET /applications` — read
- `POST /approve` — human approval gate
- `POST /pipeline/run` — run Search→Match→Research→Prepare end-to-end (needs the non-`None` agent)
- healthcheck (`/health`) for Cloud Run

---

## 12. Roadmap — realistic, online-e2e (to Aug 31)

**Now (the base, mandatory — stops the "partial runtime" myth):**
1. **Unblock the import tree**: add `ResumeFinding` (+ `WorkTypeClassifier`) to `hireflow/domain/__init__.py` — `GeminiClient.audit_resume` needs the ready-made mapping.
2. **Wire real agent into API**: in `create_app`, construct real `GeminiClient` (Vertex FIRST, API-key fallback) + `HireflowTools` + `HireflowAgent`; pass into the factory. `POST /pipeline/run` now actually runs.
3. **Fix `freehire.py`** to the live endpoint (`/api/v1/agent/jobs/search` + facets) + make `source`/`title`/etc. core schema stable across all sources.
4. **Run `.venv/bin/python -m pytest`** — green.
5. **Re-deploy to Cloud Run** → curl `/health`, then curl a **real** e2e: upload a real `.pdf` → `/pipeline/run` → `/jobs` shows live results → `/dashboard` reflects it → `/approve`. **Video-record the curl-to-cloud proof.**
6. Build the **terminal CLI test** (`.py`) but as a thin client hitting the live API (not a separate runtime).

**Next (global + demo):**
7. Complete the **global job-source registry** §10 with live-verified rows + the ATS-brand detector (Greenhouse/Lever/Ashby/Workable per company).
8. Add **Google CSE** + **JSON-LD** carriage as catch-alls (needs CSE API key from Zach).
9. Wire `hireflow-frontend.html` to the live backend (fetch) — the dashboard calls the same endpoints the CLI calls.
10. **Demo & docs**: architecture diagram, README spin-up, ≤4-min unedited video showing Cloud Run console + Vertex AI logs + live `.run` calls. Email `testing@devpost.com` / `cloudhackathons@google.com` access.

---

## 13. Reference links (real ones; find the rest online before trusting)

- Hackathon site: `allthingsagentichackathon.devpost.com`
- Credits form: `forms.gle/riGhgDSHkHeMx8Ca6` (closes **Aug 28, 12:00pm PT**; not `5PtXmw1dSbDnpYke9` — that was wrong in the old doc)
- Rules: `RULES.md` is the full official text — trust it over any summary.
- Google ADK: `google.github.io/adk-docs`, `github.com/google/adk-python`
- Gemini: `ai.google.dev` (API key), Vertex AI docs
- Inspo sources — ideas only, NOT code:
  - `github.com/MadsLorentzen/ai-job-search` — fits the query-by-function search, gates-before-scoring, seen-job adoption; **their runtime is local (Claude Code) — we are Cloud Run**.
  - `github.com/strelov1/freehire` — freehire.me is MIT open-source backend (Go+Postgres+Meilisearch); `FREEHIRE_API_URL` env-swap is our one-line failover.
- **Job-source references (verified live 2026-08-22, but re-verify):**
  - Greenhouse: `GET https://boards-api.greenhouse.io/v1/boards/{board}/jobs`
  - Ashby: `GET https://api.ashbyhq.com/posting-api/job-board/{board}`
  - Lever: `GET https://api.lever.co/v0/postings/{board}?mode=json`
  - Workable: `GET https://apply.workable.com/api/v1/widget/accounts/{account}`
  - freehire: `GET https://freehire.me/api/v1/agent/jobs/search` + facets `/api/v1/jobs/facets`
  - Remotive: `GET https://remotive.com/api/remote-jobs`
  - RemoteOK: `GET https://remoteok.com/api`
  - LinkedIn stem: `https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search`

---

## 14. Next session: where to pick up

1. Add `ResumeFinding` (+ `WorkTypeClassifier`) to domain to unblock `GeminiClient.audit_resume` → then `pytest` green, `chat.chat` works.
2. Wire a real `GeminiClient → HireflowAgent` into `create_app` so `/pipeline/run` is real.
3. Re-deploy to Cloud Run → live curl e2e with a real `.pdf` (see §12-5): upload → run → jobs → approve.
4. Build the **CLI as a client of the deployed API**.
5. Global registry column §10.
6. Frontend wiring + docs + video.

---

## 15. Zach handoff checklist (cloud owner)

**Must provide (blocks real e2e):**
1. `GCP_PROJECT_ID` (we have `hireflow-506207` in-use — confirm).
2. Service-account credentials JSON (path → `GOOGLE_APPLICATION_CREDENTIALS`) — **Vertex AI** permission only; no DB.
3. Enabled APIs: **Vertex AI** (required), **Cloud Run** (later), Cloud Scheduler (optional).
4. `GEMINI_API_KEY` (Gemini API fallback) — need it to run chat/Vertex-less; we have a real one on-disk (last verified live at repo time).
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
- **Never call two things "done" until a live e2e on that deploy proves it.** Phase labels in the old AGENTS.md were fiction; the repo has broken imports and no live pipeline — fix, verify, THEN write done in the file.

*Bismillah.*