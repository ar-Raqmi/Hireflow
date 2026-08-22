from __future__ import annotations

import uuid
from collections import Counter

from fastapi import FastAPI, File, Form, HTTPException, UploadFile

from hireflow.agents.adk_router import HireflowAgent, HireflowTools
from hireflow.domain import Application, ApplicationStatus, JobPosting, Profile
from hireflow.storage.factory import StorageFactory
from hireflow.tools.freehire import FreehireSource
from hireflow.tools.gemini import GeminiClient
from hireflow.tools.remoteok import RemoteOKSource
from hireflow.tools.remotive import RemotiveSource
from hireflow.tools.resume_parser import ResumeParser


def _build_default_agent() -> HireflowAgent:
    gemini = GeminiClient()
    sources = [FreehireSource(), RemoteOKSource(), RemotiveSource()]
    tools = HireflowTools(sources=sources, gemini=gemini)
    return HireflowAgent(tools=tools)


def create_app(
    storage: StorageFactory | None = None, agent: HireflowAgent | None = None
) -> FastAPI:
    """App factory — injectable storage/agent for tests; defaults to real ones."""
    api = FastAPI(title="Hireflow API", version="0.2.0")
    api.state.storage = storage or StorageFactory()
    api.state.agent = agent or _build_default_agent()
    api.state.parser = ResumeParser()

    @api.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @api.post("/upload")
    async def upload_resume(
        file: UploadFile = File(...),
        work_type: str = Form("any"),
        locations: str = Form(""),
        target_roles: str = Form(""),
        salary_floor: str = Form(""),
    ) -> dict:
        parser = api.state.parser
        try:
            parser.validate(file.filename)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        normalized_work_type = work_type.strip().lower()
        if normalized_work_type not in {"remote", "hybrid", "onsite", "any"}:
            raise HTTPException(
                status_code=400,
                detail="work_type must be one of remote|hybrid|onsite|any",
            )
        content = await file.read()
        try:
            text, pages = parser.parse_bytes(file.filename or "resume", content)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        salary_parsed = _parse_salary_floor(salary_floor)
        profile = Profile(
            id=str(uuid.uuid4()),
            resume_text=text,
            work_type=normalized_work_type,
            target_roles=_split_csv(target_roles),
            locations=_split_csv(locations),
            salary_floor=salary_parsed,
        )
        await api.state.storage.profiles().put(profile)
        return {
            "id": profile.id,
            "filename": file.filename,
            "status": "parsed_and_stored",
            "pages": pages,
            "work_type": profile.work_type,
            "locations": profile.locations,
            "target_roles": profile.target_roles,
            "salary_floor": profile.salary_floor,
        }

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
    async def run_pipeline(profile_id: str) -> dict:
        profile = await api.state.storage.profiles().get(profile_id)
        if profile is None:
            return {"profile_id": profile_id, "status": "profile_not_found"}
        try:
            result = await api.state.agent.run_pipeline(profile.to_mapping())
        except Exception as exc:  # noqa: BLE001 - surface agent failure as a status, not a 500
            return {
                "profile_id": profile_id,
                "status": "error",
                "detail": f"{type(exc).__name__}: {str(exc)[:400]}",
            }

        job_count = 0
        for job_map in result.get("jobs", []):
            job = JobPosting.from_mapping(job_map)
            await api.state.storage.jobs().put(job)
            job_count += 1

        app_count = 0
        for app_map in result.get("applications", []):
            application = Application.from_mapping(app_map)
            await api.state.storage.applications().put(application)
            app_count += 1

        return {
            "profile_id": profile_id,
            "status": "completed",
            "jobs_found": job_count,
            "matches": result.get("matches", []),
            "applications": result.get("applications", []),
            "needs_human": result.get("needs_human", []),
            "errors": result.get("errors", []),
            "drafts_ready": result.get("drafts", {}),
            "pipeline": "search -> score -> research -> prepare -> approve",
        }

    return api


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _approx_pages(text: str) -> int:
    return max(1, (len(text) + 2999) // 3000)


def _parse_salary_floor(value: str) -> int | None:
    if not value or not value.strip():
        return None
    try:
        return int(value.strip().replace(",", ""))
    except ValueError:
        return None


app = create_app()