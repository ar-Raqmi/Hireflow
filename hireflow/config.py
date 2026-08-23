from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()

DEFAULT_BASE_URL = "https://hireflow-backend-296941301245.us-central1.run.app"


def _env(name: str, default: str) -> str:
    return os.getenv(name, default)


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class Settings:
    project_id: str = field(default_factory=lambda: _env("GCP_PROJECT_ID", ""))
    gemini_api_key: str = field(default_factory=lambda: _env("GEMINI_API_KEY", ""))
    vertex_location: str = field(default_factory=lambda: _env("VERTEX_LOCATION", "global"))
    gemini_model: str = field(default_factory=lambda: _env("GEMINI_MODEL", "gemini-3.5-flash"))
    gemini_use_vertex: bool = field(
        default_factory=lambda: _env("GEMINI_USE_VERTEX", "").lower() in {"1", "true", "yes"}
    )
    base_url: str = field(default_factory=lambda: _env("HIREFLOW_BASE_URL", DEFAULT_BASE_URL))
    job_source_poll_hours: int = 6
    approve_threshold_auto: int = 80
    approve_threshold_draft: int = 60
    pipeline_max_jobs: int = field(default_factory=lambda: _int_env("PIPELINE_MAX_JOBS", 25))
    pipeline_max_score: int = field(default_factory=lambda: _int_env("PIPELINE_MAX_SCORE", 10))
    pipeline_max_prep: int = field(default_factory=lambda: _int_env("PIPELINE_MAX_PREP", 5))
    pipeline_max_research: int = field(
        default_factory=lambda: _int_env("PIPELINE_MAX_RESEARCH", 8)
    )
    freehire_posted_within_days: int = field(
        default_factory=lambda: _int_env("FREEHIRE_POSTED_WITHIN_DAYS", 14)
    )
    resume_parse_mode: str = field(
        default_factory=lambda: _env("RESUME_PARSE_MODE", "hybrid").strip().lower()
    )


SETTINGS = Settings()