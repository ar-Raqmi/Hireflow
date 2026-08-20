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
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    SUBMITTED = "submitted"
    FOLLOWUP = "followup"
    REPLIED = "replied"
    DONE = "done"


@dataclass
class Profile:
    id: str = ""
    resume_text: str = ""
    skills: list[str] = field(default_factory=list)
    years_experience: float = 0.0
    target_roles: list[str] = field(default_factory=list)
    locations: list[str] = field(default_factory=list)
    salary_floor: int | None = None
    culture_keywords: list[str] = field(default_factory=list)
    parsed_at: datetime | None = None

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> Profile:
        return cls(
            id=str(data.get("id", "")),
            resume_text=data.get("resume_text", ""),
            skills=list(data.get("skills", [])),
            years_experience=float(data.get("years_experience", 0.0)),
            target_roles=list(data.get("target_roles", [])),
            locations=list(data.get("locations", [])),
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
class JobMatch:
    job: JobPosting
    score: int = 0
    reasons: list[str] = field(default_factory=list)


@dataclass
class Application:
    id: str = ""
    job: JobPosting | None = None
    profile_id: str = ""
    status: ApplicationStatus = ApplicationStatus.MATCHED
    score: int = 0
    submitted_at: datetime | None = None
    followup_due: datetime | None = None
    human_handoff: bool = False
    notes: list[str] = field(default_factory=list)

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
            followup_due=_parse_datetime(data.get("followup_due")),
            human_handoff=bool(data.get("human_handoff", False)),
            notes=list(data.get("notes", [])),
        )

    def to_mapping(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "job": self.job.to_mapping() if self.job else None,
            "profile_id": self.profile_id,
            "status": self.status.value,
            "score": self.score,
            "submitted_at": self.submitted_at.isoformat() if self.submitted_at else None,
            "followup_due": self.followup_due.isoformat() if self.followup_due else None,
            "human_handoff": self.human_handoff,
            "notes": self.notes,
        }