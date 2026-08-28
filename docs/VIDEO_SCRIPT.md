# Hireflow — demo video storyboard (target 3:30–4:00, hard cap 4:00)

Rules this must satisfy (RULES.md §6 + judging §8 + the livestream Q&A notes):
- **Hook in the first 30 seconds** — problem → solution, no preamble.
- **Real human voice** (no AI voice). Energy. Screen-record everything live.
- **Visually prove Google Cloud**: Cloud Run console, Vertex AI logs, and the
  `.run.app` URL on camera at least once.
- **Unedited live execution**: terminal/API logs or UI changes happening live —
  no cuts inside a run.
- Long-running agent? Show the **end-state result and scroll the logs** — do
  not show the whole wait.
- English throughout. Upload to YouTube/Vimeo (public), link on Devpost.

Pre-flight checklist (before recording):
- [ ] Backend healthy: `curl https://hireflow-backend-296941301245.us-central1.run.app/health`
- [ ] Frontend up: https://hireflow-pi-five.vercel.app
- [ ] Cloud Run console open on the `hireflow-backend` service (metrics + logs tab ready)
- [ ] Vertex AI → Model Garden / logs view ready to show a request
- [ ] A real resume PDF + a **fresh browser profile** (localStorage clean)
- [ ] Terminal ready with `docs/CURL_E2E.md` commands for the backend proof

| # | Time | On screen | Voiceover |
|---|------|-----------|-----------|
| 1 | 0:00–0:25 | Screen: a wall of 40+ job-board tabs → cut to the Hireflow landing view. | "Job hunting is a chore you repeat every single day: search, read, filter, tailor. Hireflow is an agent that does that work for you — and unlike a chatbot, it **doesn't wait to be asked**: it watches, decides, and only asks you for the final yes." |
| 2 | 0:25–0:50 | Live browser: drag a real PDF into the dropzone → ATS audit modal appears (health score + findings) → click "Run anyway". | "Upload your résumé once. The agent immediately audits it for ATS health with Gemini, then kicks off the pipeline on **Google Cloud Run** — this URL is live right now." (cursor on the `.run.app` request in devtools) |
| 3 | 0:50–1:50 | Live SSE agent timeline animating: parse → audit → search (expanded queries + per-source counts) → match → career → research → prepare. Do NOT cut — this is the unedited proof. Then the ranked results: score dials, reasons, drafts. | "Five agents run on Google ADK inside Cloud Run: Search expands my roles into synonym queries across global keyless sources — freehire, RemoteOK, Remotive, LinkedIn, ATS boards, plus Gemini grounded web search. Match scores every posting on five dimensions. CareerSource probes the matched companies' own careers pages for jobs boards miss. Research and Prepare draft a tailored CV and cover letter per match." |
| 4 | 1:50–2:20 | Click "View Draft" on a top match → show CV + cover letter → click "Approve" → SUBMITTED toast + HFS confirmation. | "Scoring ≥80 auto-drafts; 60–79 waits for my review. **The final submit is always human-approved** — job boards are anti-bot by design, so the agent's job is to get everything ready, not to impersonate me. Approve routes it to the sandbox ATS with a confirmation id." |
| 5 | 2:20–3:00 | **The watcher moment**: come back on a later run — "Check for new jobs" → New-jobs modal "N new jobs found while you were away", new ones re-ranked on top with NEW badges. Then the History tab. | "The agent is a watcher: preferences and seen-job memory live in your browser, so when you come back anytime, it re-runs, and new matches since your last check are re-ranked on top. You only ever decide which ones to pursue." |
| 6 | 3:00–3:35 | Switch to terminal (CURL_E2E.md): `curl /health` → run pipeline via curl → SSE stream scrolls → Cloud Run console logs + Vertex AI logs visible. | "It's the same backend judges can test with plain curl — here's the live run, and here it is in the Cloud Run console with Vertex AI serving Gemini 3.5 Flash. Stateless backend, no database; user data stays in the browser." |
| 7 | 3:35–3:55 | Architecture diagram (docs/architecture.svg) full-screen, 3 highlights only: Cloud Run box, ADK agents row, human gate. | "One glance: React app → FastAPI on Cloud Run → five ADK agents through Gemini on Vertex AI → keyless global sources → drafts → a human gate. Honest limits: it drafts and submits to the sandbox, it never auto-applies to real employers on your behalf." |
| 8 | 3:55–4:00 | End card: Hireflow name + repo URL + the `.run.app` link. | "Hireflow. The agent watches — you decide." |

Recording notes:
- Record at 1080p+, browser zoom ~110%, dark terminal with a big font.
- Keep the devtools Network tab open during shot 2 so the `.run.app` host is visible.
- If a run takes >90s, start the recording with the run already in flight and
  show the SSE tail + full logs scroll afterwards (still unedited evidence).
- Never claim: auto-submit to real employers, follow-up emails, or scheduled runs —
  none are built.
