import pytest
from fastapi.testclient import TestClient

from hireflow.api.app import create_app
from hireflow.agents.adk_router import HireflowAgent, HireflowTools
from hireflow.agents.router import SearchAgent, MatchAgent, ResearchAgent, PrepareAgent, RouterAgent


class _StubGemini:
    async def generate(self, prompt: str) -> str:
        return "{}"

    async def score_fit(self, job, profile) -> tuple[int, list[str]]:
        return 90, ["skills match"]

    async def research_company(self, company: str) -> dict:
        return {"company": company, "summary": "stub"}

    async def draft_application(self, profile, job) -> dict[str, str]:
        return {"raw": "draft"}

    async def review_application(self, draft) -> str:
        return "review"

    async def revise_application(self, draft, review) -> dict[str, str]:
        return {"raw": "revised"}


class _StubSource:
    name = "stub"

    async def search(self, query: str = "", location: str = "", limit: int = 25) -> list:
        return []


def test_router_wires_agents() -> None:
    router = RouterAgent(
        SearchAgent([_StubSource()]),
        MatchAgent(_StubGemini()),
        ResearchAgent(_StubGemini()),
        PrepareAgent(_StubGemini()),
    )
    assert router.name == "router"


def test_health_endpoint() -> None:
    client = TestClient(create_app())
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_approve_endpoint() -> None:
    client = TestClient(create_app())
    response = client.post("/approve?application_id=app-1")
    assert response.status_code == 200
    assert response.json()["status"] == "approved"


def test_adk_agent_builds() -> None:
    hireflow = HireflowAgent(HireflowTools(sources=[], gemini=_StubGemini()))
    assert hireflow.agent.name == "hireflow_router"
    assert len(hireflow.agent.tools) == 4


def test_upload_persists_profile_and_shows_in_dashboard() -> None:
    client = TestClient(create_app())
    response = client.post(
        "/upload",
        files={"file": ("resume.txt", b"python engineer resume", "text/plain")},
        data={"target_roles": "ML Engineer", "locations": "Remote"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "stored"

    dashboard = client.get("/dashboard").json()
    assert dashboard["profiles"] == 1
    assert dashboard["pipeline"].startswith("Find")