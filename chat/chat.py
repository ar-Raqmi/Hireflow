#!/usr/bin/env python
"""Interactive terminal chat against Hireflow's Gemini client.

Reuses the exact config and client the pipeline uses, so it proves the
credentials / model / region / billing actually work before a full run.

Usage:
    python -m chat.chat            # uses .env (Vertex or API key)
    python -m chat.chat --model gemini-3.5-flash
    python -m chat.chat --json     # starts in a JSON-output test mode
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hireflow.config import SETTINGS  # noqa: E402
from hireflow.tools.gemini import GeminiClient  # noqa: E402


class ChatSession:
    def __init__(self, client: GeminiClient, json_mode: bool = False) -> None:
        self._client = client
        self._json_mode = json_mode
        self._mode = getattr(client, "mode", "unknown")

    def _header(self) -> None:
        transport = "Vertex AI" if self._mode == "vertex" else "Gemini API"
        print("=" * 56)
        print(f"  Hireflow chat · {transport} · {self._client._model}")
        print(f"  project={SETTINGS.project_id or 'n/a'} location={SETTINGS.vertex_location}")
        print("  type a prompt, 'json' toggles JSON test, 'exit' to quit")
        print("=" * 56)

    async def run(self) -> None:
        self._header()
        while True:
            try:
                prompt = input(">>> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nbye")
                return
            if not prompt:
                continue
            if prompt.lower() in {"exit", "quit", "q"}:
                print("bye")
                return
            if prompt.lower() == "json":
                self._json_mode = not self._json_mode
                print(f"[json mode {'ON' if self._json_mode else 'OFF'}]")
                continue
            if prompt.lower() in {"help", "h"}:
                print("commands: json (toggle), exit/quit/q, anything else is sent to the model")
                continue
            await self._roundtrip(prompt)

    async def _roundtrip(self, prompt: str) -> None:
        if self._json_mode:
            prompt = (
                'Return ONLY JSON, no prose: {"greeting": str, "model_checked": bool, "note": str}. '
                f"Base the greeting on: {prompt}"
            )
        print("…", flush=True)
        try:
            text = await self._client.generate(prompt)
        except Exception as exc:
            print(f"ERROR: {exc.__class__.__name__}: {str(exc)[:400]}")
            return
        print("-" * 56)
        print(text)
        print("-" * 56)


def build_client(model: str | None) -> GeminiClient:
    client = GeminiClient(model=model)
    if SETTINGS.gemini_use_vertex:
        client.mode = "vertex"
    else:
        client.mode = "gemini_api"
    return client


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Terminal chat against the Hireflow Gemini client.")
    parser.add_argument("--model", help=f"model to use (default {SETTINGS.gemini_model})")
    parser.add_argument("--json", action="store_true", help="start in JSON-output test mode")
    args = parser.parse_args(argv)

    try:
        client = build_client(args.model)
    except Exception as exc:
        print(f"failed to build Gemini client: {exc.__class__.__name__}: {exc}")
        return 1

    import asyncio

    asyncio.run(ChatSession(client, json_mode=args.json).run())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
