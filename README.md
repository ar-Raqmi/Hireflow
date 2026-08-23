# Hireflow
Autonomous AI job-search agent for **All Things Agentic Hackathon 2026**

by ar-Raqmi and Izaaz

What currently build:
- `AGENTS.md` is for AI assistant knowledge.
- `requirements.txt` might change or add.
- standard `.gitignore`.
- Scaffold Agents and it's Prompt Engineering.
- Standard `status` such as MATCHED, ROUTED, DONE, etc.
- ~~`storage` folder are AI created db calls, need to identify with Izaaz's Google Cloud.~~ *decided no SQL/db design*
- `tools` is a scrape and API calls for job searches website.

Stack will be Vite + React.

Google service that use in this project:
- Gemini 3.5 via Gemini API `hireflow/config.py`
- Google ADK (Python) `hireflow/agents/adk_router.py`
- Google Cloud Run `dockerfile`
