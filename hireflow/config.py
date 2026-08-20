from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Settings:
    project_id: str = field(default_factory=lambda: os.getenv("GCP_PROJECT_ID", ""))
    gemini_api_key: str = field(default_factory=lambda: os.getenv("GEMINI_API_KEY", ""))
    vertex_location: str = field(default_factory=lambda: os.getenv("VERTEX_LOCATION", "us-central1"))
    gemini_model: str = field(default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-3.5-flash"))
    gemini_use_vertex: bool = field(default_factory=lambda: os.getenv("GEMINI_USE_VERTEX", "").lower() in {"1", "true", "yes"})
    firestore_collection_profiles: str = "profiles"
    firestore_collection_jobs: str = "jobs"
    firestore_collection_applications: str = "applications"
    firestore_collection_events: str = "events"
    job_source_poll_hours: int = 6
    approve_threshold_auto: int = 80
    approve_threshold_draft: int = 60


SETTINGS = Settings()