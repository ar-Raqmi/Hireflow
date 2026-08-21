# AGENTS.md — Hireflow

> **Read this first. It is the memory for this project.**
> Project name is `Hireflow` (lowercase `f`).

---

## 1. What this is

**Hireflow** — an autonomous AI job-search agent for the **All Things Agentic Hackathon 2026** (Taskmaster track, deadline **Aug 31, 2026 @ 5:00pm PDT**).

The agent is **not a chatbot**. The user uploads a resume + preferences once; the agent watches for new matching jobs, scores fit, researches companies, tailors a CV + cover letter, and queues the application for **human approval**. It tracks status and drafts follow-ups.

**Pipeline:** `Find → Analyze → Rank → Research → Prepare → Approve → Track`

**One-line identity:** *"The agent never waits to be asked. It watches, decides, and acts — the human only approves."*

---

## 2. Hackathon rules that MUST be satisfied (every submission)

1. **Gemini 3.5 or newer** via Gemini API or Vertex AI
2. **One Google agent framework**: Google ADK, GenAI SDK, Antigravity SDK, or GenKit → we use **Google ADK (Python)**
3. **At least one Google Cloud infra service**: Cloud Run, Cloud SQL, Firestore, GKE, Pub/Sub → we use **Cloud Run** (stateless, scales-to-zero). **No SQL/database** — the rules don't require one; user data lives in the browser (see §4). Cloud Scheduler = optional.

Submit: ≤4-min unedited demo video (YouTube/Vimeo, English/subtitled), code repo + README spin-up, architecture diagram, and **visible proof it runs on Google Cloud** (Cloud Run console / Vertex logs / .run URL on camera).

**Judging:** Innovation & autonomy 40% · Architecture 30% · Demo & production readiness 30%.

**Cost notes:** Flash-first (use Gemini Flash for scoring/routing, reserve Pro for final reasoning), Cloud Run scales to zero, record demo proof then shut services off. Credits: $150 via `forms.gle/5PtXmw1dSbDnpYke9` (deadline Aug 28 12pm PT).

---

## 3. Team split (who does what)

| Role | Owner | Scope |
|------|-------|-------|
| Coding + backend | **You** (with your AI) | ADK agent, FastAPI, job-source clients, single-file HTML UI, demo video |
| Cloud (all Google things) | **Zach** | GCP project, $150 credits, enable APIs, service-account key, Vertex AI, Cloud Run deploy, IAM, GCloud console proof for demo |

**Handoffs:** Zach gives → project id + service-account credentials JSON + enabled APIs. You give → Dockerfile + code. Zach returns → Cloud Run URL. No DB setup required on either side.

---

## 4. Locked decisions (do not silently change)

| Decision | Choice |
|----------|--------|
| Name | **Hireflow** (repo, code, docs) |
| Agent framework | **Google ADK (Python)** |
| Model | **Gemini 3.5 Flash** via Vertex AI (Flash-first; Pro only for review step if needed) |
| Backend | **FastAPI** (Python) |
| Frontend | **Single-file HTML prototype** (`hireflow-frontend.html`, Material Web, mock-driven; later wired to FastAPI) — no Vite/React build |
| Database/state | **None — no SQL.** User data stays in the browser (`localStorage`: preferences + history). Backend is stateless; in-memory only for the current run. Fast + private by design. |
| Hosting | **Cloud Run** (scale-to-zero) |
| Scheduling | **Cloud Scheduler** (poll job sources) — optional |
| Job sources | keyless APIs: **RemoteOK, Remotive, freehire.me** (primary); LinkedIn guest = stretch/low-volume/personal-use |
| Apply strategy | **Sandboxed job board (simple ATS)** for the demo; real-world = draft-for-approval |
| Scoring | 5 dimensions: skills, experience, location, salary band, culture/keywords |
| Human handoff | offers, salary negotiations, counter-offers → flag "needs human" |
| Approval gates | score ≥80% → auto-draft; 60–79% → draft for review; <60% → archive. **Final submit always needs human approval.** |
| Work-type pref | Hard filter `remote | onsite | hybrid | any`, asked in its own dialog after the audit gate; skippable → `any` |
| Location pref | Preferred *work* locations — separate dialog, NEVER defaulted from resume residence; skippable → anywhere |
| History | New tab, `localStorage`, its own "Clear history" button (reset button does NOT touch it) |
| Gemini client | `MockGeminiClient` (offline/deterministic) when no creds; `GeminiClient` (Vertex/API-key) via a factory when creds exist |

---

## 5. Architecture (multi-agent)

```
[User] → [Dashboard (single-file HTML)] → [FastAPI] → [ROUTER (ADK orchestrator)]
                                                        │
                  ┌─────────────────────────────────────┼────────────────────────────┐
                  ▼                                     ▼                            ▼
         SearchAgent                         MatchAgent(CV Analysis)      ResearchAgent
         search_jobs()                       parse_resume()/score_fit()   company_research()
                  └─────────────────────────────────────┼────────────────────────────┘
                                                        ▼
                                       PrepareAgent: DRAFTER → REVIEWER → REVISE
                                                        ▼
                                              [ HUMAN APPROVAL GATE ]
                                                        ▼
                                        Browser localStorage (history + tracking)
```

MVP agents: **Search, Match, Research, Prepare (with drafter→reviewer)**. Tracking = passive localStorage/dashboard. No DB.

State story (judge-grade): **client-side persistence, stateless backend.** The browser owns all user data (prefs + history in `localStorage`); Cloud Run processes one run at a time in memory and returns results — nothing sensitive is ever stored server-side.

---

## 6. OOP conventions (STRICT)

- **All backend code is object-oriented.** No free functions doing work; logic lives in classes.
- Use abstract base classes where a contract exists:
  - `hireflow/storage/` → `Repository` (ABC): `InMemoryRepository` (Firestore optional, not default)
  - `hireflow/agents/` → `BaseAgent` (ABC): `SearchAgent`, `MatchAgent`, `ResearchAgent`, `PrepareAgent`, `RouterAgent`
  - `hireflow/tools/` → `JobSource` (ABC): `RemoteOKSource`, `RemotiveSource`, `FreehireSource`
  - `hireflow/tools/` → `GeminiClient` / `MockGeminiClient` share one interface; a factory picks real vs. offline mock from env creds
- Domain models in `hireflow/domain/`: `Profile` (incl. `residence`, `work_type`, preferred `locations`), `JobPosting`, `JobMatch`, `Application`, `ResumeFinding`, `WorkTypeClassifier` — plain classes with typed fields and behaviour, no framework imports.
- **Naming:** classes `PascalCase`, methods/vars `snake_case`, constants `UPPER_SNAKE`. Private helpers `_underscore`.
- **No code comments unless asked** — intent lives in class/method names and in AGENTS.md / docs.
- Type hints everywhere (Python 3.11+).
- Frontend (when built): apply OOP where natural (classes/factories for API client, stores); React components stay functional.

---

## 7. File layout (repo)

```
Repo/hireflow/
├── AGENTS.md                 # this file — read first
├── README.md                 # human + spin-up instructions
├── hireflow-frontend.html    # single-file UI prototype (mock-driven, localStorage persistence)
├── requirements.txt
├── Dockerfile
├── .gitignore
├── hireflow/                 # python package (backend)
│   ├── config.py
│   ├── cli.py                # terminal end-to-end run: parse → audit → prefs → search → rank → prepare → approve
│   ├── domain/               # OOP domain models
│   │   └── __init__.py       # Profile (+residence/work_type/locations), JobPosting, JobMatch, Application, ResumeFinding, WorkTypeClassifier
│   ├── storage/              # repository pattern (ABC + in-memory; Firestore optional)
│   │   ├── repository.py
│   │   ├── firestore_repository.py   # optional, not default
│   │   ├── memory_repository.py
│   │   └── factory.py        # StorageFactory (in-memory default)
│   ├── agents/               # OOP agents (ABC + concrete) + ADK wiring
│   │   ├── base_agent.py
│   │   ├── router.py         # Search/Match/Research/Prepare/Router (step executors)
│   │   └── adk_router.py     # HireflowAgent + HireflowTools (Google ADK graph)
│   ├── tools/                # job sources (ABC + concrete), gemini client + mock, resume parser
│   │   ├── job_source.py
│   │   ├── remoteok.py
│   │   ├── remotive.py
│   │   ├── freehire.py
│   │   ├── gemini.py         # real GeminiClient (Vertex/API-key)
│   │   ├── mock_gemini.py    # deterministic offline stand-in
│   │   └── resume_parser.py  # .txt/.pdf/.docx → text
│   └── api/                  # FastAPI
│       └── app.py
├── tests/
└── web/                      # unused — frontend lives in hireflow-frontend.html
```

---

## 8. Backend API surface (FastAPI)

- `POST /upload` — resume + preferences → store → trigger parse
- `GET /dashboard` — pipeline status (current run; browser localStorage holds prefs + history)
- `GET /jobs` — job postings
- `GET /applications` — applications
- `POST /approve` — human approval gate (the win)
- healthcheck endpoint for Cloud Run

---

## 9. Roadmap / build order (to Aug 31)

- **Phase 0** (done): repo scaffold + AGENTS.md + OOP skeleton
- **Phase 1** (done): ADK wiring (`HireflowAgent` + `HireflowTools` via `google.adk`), Gemini client (Vertex/API-key, 3.5 flash) + offline `MockGeminiClient`, in-memory storage, real API endpoints, 5 passing tests
- **Phase 1.5** (in progress): terminal CLI end-to-end — parse/audit, work-type + location preference gate, search, rank, prepare, human approval, tracking
- **Phase 2**: job-source clients live (RemoteOK/Remotive/freehire real API params) + end-to-end router run
- **Phase 3**: drafter→reviewer prepare pipeline + sandboxed ATS + approval gate
- **Phase 4**: production hardening + Docker + Cloud Run deploy (Zach)
- **Phase 5**: wire `hireflow-frontend.html` to FastAPI + localStorage persistence (prefs/history)
- **Phase 6**: demo video ≤4 min + architecture diagram + write-up + submit

---

## 10. Reference links

- Hackathon: `allthingsagentichackathon.devpost.com`
- Credits form: `forms.gle/5PtXmw1dSbDnpYke9`
- ADK: `google.github.io/adk-docs` · `github.com/google/adk-python`
- Gemini: `ai.google.dev` (AI Studio) · Vertex AI docs
- Inspo/pattern (ideas only, NOT code): `github.com/MadsLorentzen/ai-job-search` — borrow its query-by-function search, gates-before-scoring fit, and seen-job dedup; not its local-only runtime
- GEAR free labs: `developers.google.com/program/gear`

---

## 11. Next session: where to pick up

1. Read `AGENTS.md` + `README.md` (done — that's this file).
2. Confirm stack + OOP skeleton under `hireflow/` is intact.
3. Finish **Phase 1.5**: terminal CLI end-to-end run (parse → audit → prefs gate → search → rank → prepare → approve), then wire the API + frontend HTML.
4. Live job sources + Gemini need Zach's credentials (service-account JSON or `GEMINI_API_KEY`); use `MockGeminiClient` until then.
5. Keep name `Hireflow` lowercase everywhere. Ask user for Zach's credentials when needed.

---

## 12. Zach handoff checklist (cloud owner)

Send Zach this list. Everything on it blocks real end-to-end runs.

**Must provide:**
1. `GCP_PROJECT_ID` (e.g. `hireflow-123456`)
2. Service-account credentials JSON (path set via `GOOGLE_APPLICATION_CREDENTIALS`) — needs **Vertex AI** permissions only (no Firestore/DB — see §4)
3. Enabled APIs in that project: **Vertex AI** (plus Cloud Run for later; Cloud Scheduler optional)
4. `GEMINI_API_KEY` (for Gemini API fallback) — optional if we go Vertex-only, but good to have
5. Confirm which model string works in the project, e.g. `gemini-3.5-flash` (rules require Gemini 3.5+)

**Later (Phases 2–4):**
6. Deploy the `Dockerfile` to **Cloud Run** and share the `.run.app` URL (needed for the "proof on Google Cloud" video)
7. Optionally set up **Cloud Scheduler** to hit `POST /pipeline/run` on a schedule (job polling)
8. Record/verify Cloud Run console + Vertex AI logs for the demo video

**No DB needed:** the demo shows a Cloud Run-backed run; all user data stays in the browser (`localStorage`), so no Firestore/Cloud SQL setup is required on either side.

*Bismillah.*