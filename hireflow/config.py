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


def _float_env(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
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
    resume_audit_enabled: bool = field(
        default_factory=lambda: _env("RESUME_AUDIT_ENABLED", "true").lower()
        in {"1", "true", "yes"}
    )
    resume_health_block: int = field(
        default_factory=lambda: _int_env("RESUME_HEALTH_BLOCK", 60)
    )
    query_expansion: bool = field(
        default_factory=lambda: _env("QUERY_EXPANSION", "true").lower() in {"1", "true", "yes"}
    )
    expansion_terms: int = field(
        default_factory=lambda: _int_env("QUERY_EXPANSION_TERMS", 6)
    )
    job_recency_days: int = field(
        default_factory=lambda: _int_env("JOB_RECENCY_DAYS", 14)
    )
    diversity_max_same_company: int = field(
        default_factory=lambda: _int_env("DIVERSITY_MAX_SAME_COMPANY", 2)
    )
    use_unverified_sources: bool = field(
        default_factory=lambda: _env("USE_UNVERIFIED_SOURCES", "").lower() in {"1", "true", "yes"}
    )
    freehire_sources: list[str] = field(
        default_factory=lambda: [
            part.strip()
            for part in os.getenv("FREEHIRE_SOURCES", "seek,mycareersfuture").split(",")
            if part.strip()
        ]
    )
    web_search_endpoint: str = field(
        default_factory=lambda: _env(
            "WEB_SEARCH_ENDPOINT", "https://lite.duckduckgo.com/lite/"
        )
    )
    web_fetch_enabled: bool = field(
        default_factory=lambda: _env("WEB_FETCH", "true").lower() in {"1", "true", "yes"}
    )
    web_fetch_timeout: float = field(
        default_factory=lambda: _float_env("WEB_FETCH_TIMEOUT", 12.0)
    )
    web_discovery_enabled: bool = field(
        default_factory=lambda: _env("WEB_DISCOVERY", "true").lower()
        in {"1", "true", "yes"}
    )
    web_discovery_max_links: int = field(
        default_factory=lambda: _int_env("WEB_DISCOVERY_MAX_LINKS", 8)
    )
    web_discovery_companies: list[str] = field(
        default_factory=lambda: [
            part.strip()
            for part in os.getenv("WEB_DISCOVERY_COMPANIES", "").split(",")
            if part.strip()
        ]
    )
    career_source_enabled: bool = field(
        default_factory=lambda: _env("CAREER_SOURCE_ENABLED", "true").lower()
        in {"1", "true", "yes"}
    )
    career_source_max_companies: int = field(
        default_factory=lambda: _int_env("CAREER_SOURCE_MAX_COMPANIES", 5)
    )
    career_source_max_per_company: int = field(
        default_factory=lambda: _int_env("CAREER_SOURCE_MAX_PER_COMPANY", 8)
    )
    semantic_search: bool = field(
        default_factory=lambda: _env("SEMANTIC_SEARCH", "").lower() in {"1", "true", "yes"}
    )
    embedding_model: str = field(
        default_factory=lambda: _env("EMBEDDING_MODEL", "gemini-embedding-001")
    )
    playwright_enabled: bool = field(
        default_factory=lambda: _env("HIREFLOW_PLAYWRIGHT", "").lower() in {"1", "true", "yes"}
    )
    playwright_spa_urls: list[str] = field(
        default_factory=lambda: [
            part.strip()
            for part in os.getenv("PLAYWRIGHT_SPA_URLS", "").split(",")
            if part.strip()
        ]
    )
    jobstreet_enabled: bool = field(
        default_factory=lambda: _env("JOBSTREET_ENABLED", "true").lower()
        in {"1", "true", "yes"}
    )
    sandbox_ats_file: str = field(
        default_factory=lambda: _env("SANDBOX_ATS_FILE", "sandbox_ats.json")
    )


ATS_BOARDS: dict[str, list[str]] = {
    "greenhouse": ["gitlab"],
    "ashby": ["notion"],
}

JSONLD_COMPANY_URLS: list[str] = [
    "https://www.greenhouse.io/careers",
]


SETTINGS = Settings()
