from __future__ import annotations

import uuid
from collections import Counter

from fastapi import FastAPI, File, Form, UploadFile

from hireflow.agents.adk_router import HireflowAgent
from hireflow.domain import Application, ApplicationStatus, Profile
from hireflow.storage.factory import StorageFactory


def create_app(storage: StorageFactory | None = None, agent: HireflowAgent | None = None) -> FastAPI:
    """App factory — lets tests inject repositories/agent; defaults to in-memory storage."""
    api = FastAPI(title="Hireflow API", version="0.1.0")
    api.state.storage = storage or StorageFactory()
    api.state.agent = agent

    @api.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @api.post("/upload")
    async def upload_resume(
        file: UploadFile = File(...),
        target_roles: str = Form(""),
        locations: str = Form(""),
    ) -> dict[str, str]:
        content = (await file.read()).decode("utf-8", errors="replace")
        profile = Profile(
            id=str(uuid.uuid4()),
            resume_text=content,
            target_roles=[role.strip() for role in target_roles.split(",") if role.strip()],
            locations=[loc.strip() for loc in locations.split(",") if loc.strip()],
        )
        await api.state.storage.profiles().put(profile)
        return {"id": profile.id, "filename": file.filename, "status": "stored"}

    @api.get("/dashboard")
    async def dashboard() -> dict:
        applications = await api.state.storage.applications().list_all()
        jobs = await api.state.storage.jobs().list_all()
        profiles = await api.state.storage.profiles().list_all()
        status_counts = Counter(app.status.value for app in applications)
        return {
            "pipeline": "Find -> Analyze -> Rank -> Research -> Prepare -> Approve -> Track",
            "profiles": len(profiles),
            "jobs_found": len(jobs),
            "applications": len(applications),
            "by_status": dict(status_counts),
        }

    @api.get("/jobs")
    async def jobs() -> list[dict]:
        return [job.to_mapping() for job in await api.state.storage.jobs().list_all()]

    @api.get("/applications")
    async def applications() -> list[dict]:
        return [app.to_mapping() for app in await api.state.storage.applications().list_all()]

    @api.post("/approve")
    async def approve(application_id: str) -> dict[str, str]:
        repository = api.state.storage.applications()
        application = await repository.get(application_id) or Application(id=application_id)
        application.status = ApplicationStatus.APPROVED
        await repository.put(application)
        return {"id": application_id, "status": ApplicationStatus.APPROVED.value}

    @api.post("/pipeline/run")
    async def run_pipeline(profile_id: str) -> dict[str, str]:
        if api.state.agent is None:
            return {"profile_id": profile_id, "status": "agent_not_configured"}
        profile = await api.state.storage.profiles().get(profile_id)
        if profile is None:
            return {"profile_id": profile_id, "status": "profile_not_found"}
        await api.state.agent.run(user_id=profile_id, session_id=str(uuid.uuid4()), profile=profile.to_mapping())
        return {"profile_id": profile_id, "status": "completed"}

    return api


app = create_app()
