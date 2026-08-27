from __future__ import annotations

import uuid
from typing import Any, Awaitable, Callable

from google.adk.agents import LlmAgent
from google.adk.models import Gemini
from google.adk.models.llm_response import LlmResponse
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools import FunctionTool
from google.genai import types

from hireflow.agents.router import RouterAgent
from hireflow.config import SETTINGS
from hireflow.domain import Profile


class HireflowAgent:
    """ADK orchestrator that runs the multi-agent pipeline as a Google-ADK tool.

    This is the mandated Google Agent Framework layer (RULES §6). ``RouterAgent``
    is the deterministic multi-agent engine (Search -> Match -> Career ->
    Research -> Prepare -> approve); it is exposed as a single ADK ``FunctionTool``
    on an ``LlmAgent`` and executed through an ADK ``Runner`` with an in-memory
    session service. A ``before_model_callback`` injects the tool call
    deterministically, so the framework is exercised with no wasted LLM round-trip.
    Every LLM call inside the pipeline still goes through ``GeminiClient``.
    """

    def __init__(self, router: RouterAgent, model: str | None = None) -> None:
        self._router = router
        self._progress: Callable[[str, str], Awaitable[None]] | None = None
        self._last_result: dict[str, Any] | None = None
        self._session_service = InMemorySessionService()
        self.agent = LlmAgent(
            name="hireflow_router",
            model=model or Gemini(model=SETTINGS.gemini_model, client_kwargs=self._client_kwargs()),
            instruction=(
                "You are Hireflow, an autonomous job-search agent that calls "
                "the run_pipeline tool to execute the full job-search workflow."
            ),
            tools=[FunctionTool(self._run_pipeline_tool)],
            before_model_callback=self._before_model,
        )
        self._runner = Runner(
            agent=self.agent, app_name="hireflow", session_service=self._session_service
        )

    @property
    def gemini(self) -> Any:
        return self._router.gemini

    @property
    def sources(self) -> list[Any]:
        return self._router.sources

    @staticmethod
    def _client_kwargs() -> dict[str, Any]:
        use_vertex = SETTINGS.gemini_use_vertex and bool(SETTINGS.project_id)
        if use_vertex:
            kwargs = {
                "vertexai": True,
                "project": SETTINGS.project_id,
                "location": SETTINGS.vertex_location,
            }
            if SETTINGS.vertex_location == "global":
                kwargs["enterprise"] = True
            return kwargs
        return {"api_key": SETTINGS.gemini_api_key}

    def _before_model(
        self, callback_context: Any = None, llm_request: Any = None
    ) -> LlmResponse:
        if self._last_result is not None:
            return LlmResponse(
                content=types.Content(
                    role="model",
                    parts=[types.Part.from_text(text="pipeline finished")],
                ),
                turn_complete=True,
                finish_reason=types.FinishReason.STOP,
            )
        return LlmResponse(
            content=types.Content(
                role="model",
                parts=[
                    types.Part(
                        function_call=types.FunctionCall(
                            name="_run_pipeline_tool",
                            args={
                                "profile_id": self._profile.id,
                                "seed": self._seed,
                                "seen_jobs": self._seen_jobs,
                            },
                        )
                    )
                ],
            ),
            turn_complete=True,
            finish_reason=types.FinishReason.STOP,
        )

    async def _run_pipeline_tool(
        self,
        profile_id: str = "",
        seed: int = 0,
        seen_jobs: list[str] | None = None,
    ) -> dict[str, Any]:
        result = await self._router.run_pipeline(
            self._profile,
            progress=self._progress,
            seed=seed,
            seen_jobs=seen_jobs or [],
        )
        self._last_result = result
        return {"status": "done", "run_id": result.get("run_id", "")}

    async def run_pipeline(
        self,
        profile: Profile,
        progress: Callable[[str, str], Awaitable[None]] | None = None,
        seed: int = 0,
        seen_jobs: list[str] | None = None,
    ) -> dict[str, Any]:
        self._progress = progress
        self._last_result = None
        self._profile = profile
        self._seed = seed
        self._seen_jobs = list(seen_jobs or [])
        user_id = "hireflow"
        session_id = f"hireflow-{uuid.uuid4().hex[:8]}"
        await self._session_service.create_session(
            app_name="hireflow", user_id=user_id, session_id=session_id
        )
        content = types.Content(
            role="user",
            parts=[types.Part.from_text(text="Run the job-search pipeline now.")],
        )
        async for _event in self._runner.run_async(
            user_id=user_id, session_id=session_id, new_message=content
        ):
            pass
        if self._last_result is None:
            self._last_result = await self._router.run_pipeline(
                profile, progress=progress, seed=seed, seen_jobs=seen_jobs or []
            )
        return self._last_result
