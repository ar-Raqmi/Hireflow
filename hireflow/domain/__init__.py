from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


class ApplicationStatus(str, Enum):
    MATCHED = "matched"
    ROUTED = "routed"
    DRAFTED = "drafted"
    SUBMITTED = "submitted"


@dataclass
class WorkTypeClassifier:
    """Deterministic work-type gate. Returns remote|hybrid|onsite|any."""

    _REMOTE_MARKERS = ("remote", "work from anywhere", "work from home", "wfh", "telecommut", "fully online", "distributed", "worldwide", "anywhere")
    _ONSITE_MARKERS = ("onsite", "on-site", "on site", "in-office", "in office", "on office", "office based", "office-based", "at the office")
    _HYBRID_MARKERS = ("hybrid", "mix of remote", "part remote", "flexible work")
    _ONLY_WORK_TYPE_VALUES = {"remote", "hybrid", "onsite", "any"}

    @classmethod
    def classify(cls, text: str | None) -> str:
        lowered = (text or "").lower()
        has_hybrid = any(marker in lowered for marker in cls._HYBRID_MARKERS)
        remote_hits = sum(marker in lowered for marker in cls._REMOTE_MARKERS)
        onsite_hits = sum(marker in lowered for marker in cls._ONSITE_MARKERS)
        if has_hybrid:
            return "hybrid"
        if remote_hits and not onsite_hits:
            return "remote"
        if onsite_hits and not remote_hits:
            return "onsite"
        if remote_hits and onsite_hits:
            return "hybrid" if remote_hits >= onsite_hits else "onsite"
        return "any"

    @classmethod
    def is_valid(cls, value: str) -> bool:
        return value.strip().lower() in cls._ONLY_WORK_TYPE_VALUES


@dataclass
class Profile:
    id: str = ""
    resume_text: str = ""
    skills: list[str] = field(default_factory=list)
    years_experience: float = 0.0
    target_roles: list[str] = field(default_factory=list)
    locations: list[str] = field(default_factory=list)
    work_type: str = "any"
    residence: str = ""
    salary_floor: int | None = None
    culture_keywords: list[str] = field(default_factory=list)
    parsed_at: datetime | None = None

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> Profile:
        return cls(
            id=str(data.get("id", "")),
            resume_text=str(data.get("resume_text", "") or ""),
            skills=list(data.get("skills", [])),
            years_experience=float(data.get("years_experience", 0.0)),
            target_roles=list(data.get("target_roles", [])),
            locations=list(data.get("locations", [])),
            work_type=str(data.get("work_type", "any") or "any"),
            residence=str(data.get("residence", "") or ""),
            salary_floor=data.get("salary_floor"),
            culture_keywords=list(data.get("culture_keywords", [])),
            parsed_at=_parse_datetime(data.get("parsed_at")),
        )

    def to_mapping(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "resume_text": self.resume_text,
            "skills": self.skills,
            "years_experience": self.years_experience,
            "target_roles": self.target_roles,
            "locations": self.locations,
            "work_type": self.work_type,
            "residence": self.residence,
            "salary_floor": self.salary_floor,
            "culture_keywords": self.culture_keywords,
            "parsed_at": self.parsed_at.isoformat() if self.parsed_at else None,
        }


@dataclass
class JobPosting:
    id: str = ""
    source: str = ""
    title: str = ""
    company: str = ""
    location: str = ""
    post_url: str = ""
    posted_at: datetime | None = None
    raw_data: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> JobPosting:
        return cls(
            id=str(data.get("id", "")),
            source=data.get("source", ""),
            title=data.get("title", ""),
            company=data.get("company", ""),
            location=data.get("location", ""),
            post_url=data.get("post_url", ""),
            posted_at=_parse_datetime(data.get("posted_at")),
            raw_data=data.get("raw_data", {}),
        )

    def to_mapping(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "source": self.source,
            "title": self.title,
            "company": self.company,
            "location": self.location,
            "post_url": self.post_url,
            "posted_at": self.posted_at.isoformat() if self.posted_at else None,
            "raw_data": self.raw_data,
        }


@dataclass
class Application:
    id: str = ""
    job: JobPosting | None = None
    profile_id: str = ""
    status: ApplicationStatus = ApplicationStatus.MATCHED
    score: int = 0
    submitted_at: datetime | None = None
    human_handoff: bool = False
    drafts: dict[str, str] = field(default_factory=dict)
    ats_confirmation: str = ""

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> Application:
        job = data.get("job")
        return cls(
            id=str(data.get("id", "")),
            job=JobPosting.from_mapping(job) if isinstance(job, dict) else None,
            profile_id=data.get("profile_id", ""),
            status=ApplicationStatus(data.get("status", ApplicationStatus.MATCHED.value)),
            score=int(data.get("score", 0)),
            submitted_at=_parse_datetime(data.get("submitted_at")),
            human_handoff=bool(data.get("human_handoff", False)),
            drafts=dict(data.get("drafts", {}) or {}),
            ats_confirmation=str(data.get("ats_confirmation", "") or ""),
        )

    def to_mapping(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "job": self.job.to_mapping() if self.job else None,
            "profile_id": self.profile_id,
            "status": self.status.value,
            "score": self.score,
            "submitted_at": self.submitted_at.isoformat() if self.submitted_at else None,
            "human_handoff": self.human_handoff,
            "drafts": self.drafts,
            "ats_confirmation": self.ats_confirmation,
        }


@dataclass
class ResumeFinding:
    """One ATS-health finding produced by GeminiClient.audit_resume."""

    id: str = ""
    sev: str = "warn"
    type: str = "input"
    title: str = ""
    area: str = ""
    detail: str = ""
    delta: int = 0
    before: str | None = None
    after: str | None = None
    field: str | None = None
    placeholder: str | None = None

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> ResumeFinding:
        return cls(
            id=str(data.get("id", "") or ""),
            sev=str(data.get("sev", "warn") or "warn"),
            type=str(data.get("type", "input") or "input"),
            title=str(data.get("title", "") or ""),
            area=str(data.get("area", "") or ""),
            detail=str(data.get("detail", "") or ""),
            delta=_parse_int(data.get("delta")),
            before=data.get("before"),
            after=data.get("after"),
            field=data.get("field"),
            placeholder=data.get("placeholder"),
        )

    def to_mapping(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "sev": self.sev,
            "type": self.type,
            "title": self.title,
            "area": self.area,
            "detail": self.detail,
            "delta": self.delta,
            "before": self.before,
            "after": self.after,
            "field": self.field,
            "placeholder": self.placeholder,
        }


def _parse_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


__all__ = [
    "Profile",
    "JobPosting",
    "Application",
    "ApplicationStatus",
    "ResumeFinding",
    "WorkTypeClassifier",
]