from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

import httpx

from hireflow.config import SETTINGS
from hireflow.domain import WorkTypeClassifier


class InputPrefs:
    """Resolved user preferences for a run."""

    def __init__(
        self,
        work_type: str = "any",
        locations: list[str] | None = None,
        target_roles: list[str] | None = None,
        salary_floor: int | None = None,
    ) -> None:
        self.work_type = work_type
        self.locations = locations or []
        self.target_roles = target_roles or []
        self.salary_floor = salary_floor


class HireflowCli:
    """Thin client for the deployed Hireflow backend.

    Owns no pipeline logic — it uploads a resume and preferences to the API and
    renders whatever the agent returns.
    """

    def __init__(self, base_url: str, resume_path: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._resume_path = Path(resume_path)

    def run(self, args: argparse.Namespace) -> int:
        self._require_file()
        prefs = self._resolve_prefs(args)
        try:
            profile_id = self._upload(prefs)
        except httpx.HTTPError as exc:
            print(f"upload failed: {exc.__class__.__name__}: {exc}")
            return 1
        try:
            result = self._run_pipeline(profile_id)
        except httpx.HTTPError as exc:
            print(f"pipeline failed: {exc.__class__.__name__}: {exc}")
            return 1
        self._render(result)
        return 0

    def _require_file(self) -> None:
        if not self._resume_path.exists():
            raise SystemExit(f"resume file not found: {self._resume_path}")

    def _resolve_prefs(self, args: argparse.Namespace) -> InputPrefs:
        explicit = bool(args.work_type) or bool(args.location) or bool(args.target_role)
        if explicit:
            return self._prefs_from_args(args)
        return self._prompt_prefs()

    def _prefs_from_args(self, args: argparse.Namespace) -> InputPrefs:
        work_type = (args.work_type or "").strip().lower() or "any"
        if not WorkTypeClassifier.is_valid(work_type):
            print(f"invalid --work-type '{work_type}' (remote|hybrid|onsite|any)")
            raise SystemExit(2)
        salary = args.salary_floor
        if salary is not None and salary < 0:
            print("invalid --salary-floor (must be >= 0)")
            raise SystemExit(2)
        return InputPrefs(
            work_type=work_type,
            locations=list(args.location or []),
            target_roles=list(args.target_role or []),
            salary_floor=salary,
        )

    def _prompt_prefs(self) -> InputPrefs:
        work_type = self._prompt_work_type()
        locations = self._prompt_locations()
        target_roles = self._prompt_target_roles()
        return InputPrefs(work_type=work_type, locations=locations, target_roles=target_roles)

    def _prompt_work_type(self) -> str:
        print("\n=== Work type (your gate — hard filter) ===")
        while True:
            raw = input("remote | hybrid | onsite | any  [any]: ").strip().lower()
            if not raw:
                return "any"
            if WorkTypeClassifier.is_valid(raw):
                return raw
            print("  -> pick one of: remote, hybrid, onsite, any")

    def _prompt_locations(self) -> list[str]:
        print("\n=== Where do you want to work? (enter to skip -> anywhere) ===")
        print("  Format: City, or City/Country (e.g. Tokyo or Kuala Lumpur/My).")
        locations: list[str] = []
        while True:
            raw = input("  add location [enter] to finish: ").strip()
            if not raw:
                break
            locations.extend([part.strip() for part in raw.split(",") if part.strip()])
        return _dedupe(locations)

    def _prompt_target_roles(self) -> list[str]:
        print("\n=== Target roles (what jobs should the agent chase?) ===")
        roles: list[str] = []
        while True:
            raw = input("  add role, comma-separated ok [enter] to finish: ").strip()
            if not raw:
                break
            roles.extend([part.strip() for part in raw.split(",") if part.strip()])
        return _dedupe(roles)

    def _upload(self, prefs: InputPrefs) -> str:
        content = self._resume_path.read_bytes()
        form = {
            "work_type": prefs.work_type,
            "locations": ",".join(prefs.locations),
            "target_roles": ",".join(prefs.target_roles),
        }
        if prefs.salary_floor is not None:
            form["salary_floor"] = str(prefs.salary_floor)
        with httpx.Client(timeout=120) as client:
            response = client.post(
                f"{self._base_url}/upload",
                files={"file": (self._resume_path.name, content)},
                data=form,
            )
            response.raise_for_status()
        payload = response.json()
        if payload.get("status") != "parsed_and_stored":
            print(f"upload returned unexpected status: {payload}")
            raise SystemExit(1)
        print(f"[upload] parsed {payload['filename']} ({payload.get('pages', '?')} pages)")
        print()
        return payload["id"]

    def _run_pipeline(self, profile_id: str) -> dict[str, Any]:
        with httpx.Client(timeout=60) as client:
            response = client.post(
                f"{self._base_url}/pipeline/run", params={"profile_id": profile_id}
            )
            response.raise_for_status()
        payload = response.json()
        if payload.get("status") != "started" or not payload.get("run_id"):
            raise SystemExit(f"pipeline did not start: {payload}")
        run_id = payload["run_id"]
        print(f"\n[run] started {run_id[:8]} · streaming live progress\n")
        return self._stream_events(run_id)

    def _stream_events(self, run_id: str) -> dict[str, Any]:
        started = time.monotonic()
        result: dict[str, Any] | None = None
        event_name = ""
        with httpx.Client(timeout=None) as client:
            with client.stream(
                "GET", f"{self._base_url}/pipeline/run/{run_id}/events"
            ) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if not line:
                        continue
                    if line.startswith("event:"):
                        event_name = line[len("event:") :].strip()
                        continue
                    if not line.startswith("data:"):
                        continue
                    raw = line[len("data:") :].strip()
                    if not raw:
                        continue
                    try:
                        payload = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    if event_name == "done":
                        result = payload
                        continue
                    event_name = ""
                    if "stage" in payload:
                        elapsed = time.monotonic() - started
                        print(f"  [+{elapsed:>4.0f}s] ▶ {payload['stage']:<9} {payload.get('detail', '')}")
                        sys.stdout.flush()
        if result is None:
            raise SystemExit("pipeline finished without a done event")
        return result

    def _render(self, result: dict[str, Any]) -> None:
        print("=" * 64)
        print("  HIREFLOW · pipeline report")
        print("=" * 64)
        status = result.get("status", "completed")
        print(f"  profile {result.get('profile_id', '')[:8]} · status={status} · jobs={result.get('jobs_found', 0)}")
        matches = result.get("matches", [])
        applications = result.get("applications", [])
        needs_human = result.get("needs_human", [])
        errors = result.get("errors", [])

        if not matches:
            print("\n  no matches yet (either no jobs found or all below score 60).")
        else:
            print("\n  TOP MATCHES")
            print("  " + "-" * 60)
            for match in matches:
                print(f"  #{match['rank']:<2} {match['score']:>3}  {match['title']} @ {match['company']}")
                print(f"       {match.get('location', '')} · {match.get('source', '')}")
                print(f"       {match.get('post_url', '')}")
                for reason in match.get("reasons", [])[:3]:
                    print(f"       - {reason}")
                if match.get("research", {}).get("summary"):
                    summary = match["research"]["summary"].replace("\n", " ")[:160]
                    print(f"       research: {summary}")

        print("\n  APPLICATIONS")
        print("  " + "-" * 60)
        if not applications:
            print("   none queued (nothing scored high enough).")
        for app in applications:
            drafted = " [draft ready]" if app.get("drafted") else ""
            handoff = " [needs human]" if app.get("human_handoff") else ""
            print(f"   {app['status']:<20} {app['score']:>3}  {app['title']} @ {app['company']}{drafted}{handoff}")

        if needs_human:
            print("\n  NEEDS HUMAN")
            print("  " + "-" * 60)
            for item in needs_human:
                print(f"   {item.get('company', '')} · {item.get('title', '')} — {item.get('reason', '')}")

        if errors:
            print("\n  SOURCE NOTES (non-fatal)")
            for message in errors[:8]:
                print(f"   warning: {message}")

        print("\n  next step: go to the dashboard and approve an application.")
        print("=" * 64)


def _dedupe(values: list[str]) -> list[str]:
    seen: list[str] = []
    for value in values:
        if value not in seen:
            seen.append(value)
    return seen


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hireflow",
        description="Run the Hireflow pipeline against the deployed backend.",
    )
    parser.add_argument("resume", metavar="RESUME_FILE", help="path to your resume (.txt/.pdf/.docx)")
    parser.add_argument("--work-type", choices=["remote", "hybrid", "onsite", "any"], help="work-type gate")
    parser.add_argument("--location", action="append", help="preferred work location (repeatable, e.g. Tokyo)")
    parser.add_argument("--target-role", action="append", help="target role (repeatable)")
    parser.add_argument("--salary-floor", type=int, help="minimum expected salary floor (0..)")
    parser.add_argument("--url", default=SETTINGS.base_url, help=f"backend base URL (default: {SETTINGS.base_url})")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return HireflowCli(base_url=args.url, resume_path=args.resume).run(args)
    except KeyboardInterrupt:
        print("\n  bye")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())