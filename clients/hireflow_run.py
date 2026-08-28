
import json
import os
import subprocess
import sys
import time
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hireflow.export_html import HtmlExporter, ago, is_expired  # noqa: E402
from hireflow.config import SETTINGS  # noqa: E402

EMOJI = {
    "parse": "Reading resume",
    "audit": "Auditing ATS health",
    "search": "Searching job boards",
    "match": "Scoring matches",
    "research": "Researching companies",
    "prepare": "Drafting CV + cover letter",
    "approve": "Finalizing applications",
}


def _prompt_work_type() -> str:
    print("remote | hybrid | onsite | any  [any]:")
    while True:
        raw = input("> ").strip().lower()
        if not raw:
            return "any"
        if raw in {"remote", "hybrid", "onsite", "any"}:
            return raw
        print("  -> pick one of: remote, hybrid, onsite, any")


def _prompt_locations() -> list[str]:
    print("\nPreferred work locations (comma separated; blank = anywhere):")
    raw = input("> ").strip()
    if not raw:
        return []
    return [part.strip() for part in raw.split(",") if part.strip()]


def _upload(base: str, resume: str, work: str, locs: list[str], target: str) -> str:
    boundary = "----hl" + str(int(time.time() * 1000))
    parts: list[bytes] = []
    fields = [("work_type", work), ("locations", ",".join(locs)), ("target_roles", target)]
    for name, value in fields:
        parts.append(
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n".encode()
        )
    fname = resume.replace("\\", "/").split("/")[-1]
    with open(resume, "rb") as f:
        content = f.read()
    parts.append(
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{fname}\"\r\n"
        f"Content-Type: application/octet-stream\r\n\r\n".encode()
    )
    parts.append(content)
    parts.append(f"\r\n--{boundary}--\r\n".encode())
    body = b"".join(parts)

    req = urllib.request.Request(
        f"{base}/upload",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        payload = json.loads(resp.read().decode())
    if payload.get("status") != "parsed_and_stored":
        raise SystemExit(f"upload unexpected: {payload}")
    print(f"[upload] parsed {payload.get('filename')} ({payload.get('pages', '?')} pages)")
    print()
    return payload["id"]


def _start_run(base: str, profile_id: str, seed: int = 0, seen: list[str] | None = None) -> str:
    params = [("profile_id", profile_id), ("seed", str(seed))]
    if seen:
        params.append(("seen", ",".join(seen)))
    url = f"{base}/pipeline/run?{urllib.parse.urlencode(params)}"

    req = urllib.request.Request(
        url,
        data=b"",
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=60) as resp:
        payload = json.loads(resp.read().decode())

    if payload.get("status") != "started" or not payload.get("run_id"):
        raise SystemExit(f"pipeline did not start: {payload}")

    return payload["run_id"]


def _stream(base: str, run_id: str) -> dict:
    started = time.monotonic()
    result: dict | None = None
    resume_seq = 0
    attempts = 0
    max_attempts = 12
    while result is None and attempts <= max_attempts:
        url = f"{base}/pipeline/run/{run_id}/events"
        args = ["curl", "-sN", "--max-time", "600"]
        if resume_seq:
            args += ["-H", f"Last-Event-ID: {resume_seq}"]
        args.append(url)
        proc = subprocess.Popen(args, stdout=subprocess.PIPE, text=True)
        event = ""
        for line in proc.stdout:
            line = line.rstrip("\n")
            if not line:
                continue
            if line.startswith("event:"):
                event = line[6:].strip()
                continue
            if line.startswith("id:"):
                seq = line[3:].strip()
                if seq.isdigit():
                    resume_seq = max(resume_seq, int(seq))
                continue
            if not line.startswith("data:"):
                continue
            raw = line[5:].strip()
            if not raw:
                continue
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if event == "done":
                result = payload
                break
            event = ""
            if "stage" in payload:
                stage = payload.get("stage", "")
                detail = payload.get("detail", "") or ""
                label = EMOJI.get(stage, stage)
                elapsed = int(time.monotonic() - started)
                print(f"  [+{elapsed:>5}s] {label}  {detail}", flush=True)
        proc.wait()
        if result is not None:
            break
        attempts += 1
        if attempts <= max_attempts:
            time.sleep(2)
    if result is None:
        raise SystemExit("pipeline finished without a done event")
    return result


def _approve_top(base: str, result: dict) -> dict:
    apps = result.get("applications") or []
    targets = [a for a in apps if a.get("status") in {"drafted", "routed"}]
    if not targets:
        print("\n[approve] no drafted/routed application to submit.")
        return result
    app_id = str(targets[0].get("id", ""))
    url = f"{base}/approve?application_id={urllib.parse.quote(app_id)}"
    req = urllib.request.Request(url, data=b"", method="POST")
    with urllib.request.urlopen(req, timeout=60) as resp:
        payload = json.loads(resp.read().decode())
    for a in apps:
        if str(a.get("id", "")) == app_id:
            a["status"] = payload.get("status", "submitted")
            a["submitted_at"] = payload.get("submitted_at")
            a["ats_confirmation"] = payload.get("ats_confirmation")
    print(f"[approve] {app_id[:8]} -> {payload.get('status')} {payload.get('ats_confirmation')} {payload.get('submitted_at')}")
    return result


def _render(result: dict) -> None:
    pid = result.get("profile_id", "")
    print("\n" + "=" * 64)
    print(f"HIREFLOW REPORT · profile {str(pid)[:8]} · run {str(result.get('run_id',''))[:8]}")
    print("=" * 64)
    print("status:     ", result.get("status"))
    print("jobs_found: ", result.get("jobs_found", 0))

    matches = result.get("matches") or []
    print(f"\nTOP MATCHES ({len(matches)})")
    for m in matches[:10]:
        when = ago(m.get("posted_at"))
        if is_expired(m.get("posted_at"), SETTINGS.job_recency_days):
            when += " · ⚠ expired"
        print(f'  {m.get("score",0):>3}  {str(m.get("title",""))[:46]:<46} @ {str(m.get("company",""))[:28]:<28}')
        print(f'      loc:{str(m.get("location",""))[:30]:<30} {when:<16} url:{str(m.get("post_url",""))[:70]}')
        reasons = m.get("reasons") or []
        if reasons:
            print(f'      why: {str(reasons[0])[:110]}')

    apps = result.get("applications") or []
    print(f"\nAPPLICATIONS ({len(apps)})")
    for a in apps:
        drafted = "  [draft ready]" if a.get("drafted") else ""
        handoff = "  needs_human" if a.get("human_handoff") else ""
        submitted = f"  submitted {a.get('ats_confirmation','')}" if a.get("ats_confirmation") else ""
        print(f'  {str(a.get("id",""))[:12]}  status={a.get("status","")}  score={a.get("score","")}{handoff}  {str(a.get("title",""))[:44]}{drafted}{submitted}')

    print("\nneeds_human:", result.get("needs_human") or [])
    print("\nNext: POST /approve?application_id=<id> to submit to the sandbox ATS (confirmation in /sandbox/ats/submissions).")
    print("=" * 64)


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: python clients/hireflow_run.py <base_url> <resume> [work_type] [locations_csv] [target] [seed] [seen_csv] [approve]")
        return 2
    base = sys.argv[1].rstrip("/")
    resume = sys.argv[2]
    work = sys.argv[3] if len(sys.argv) > 3 and sys.argv[3] else "any"
    locs_raw = sys.argv[4] if len(sys.argv) > 4 else ""
    target = sys.argv[5] if len(sys.argv) > 5 else ""
    seed = int(sys.argv[6]) if len(sys.argv) > 6 and sys.argv[6].isdigit() else 0
    seen_raw = sys.argv[7] if len(sys.argv) > 7 else ""
    approve = bool(sys.argv[8]) if len(sys.argv) > 8 else False
    seen = [p.strip() for p in seen_raw.split(",") if p.strip()]
    locs = [p.strip() for p in locs_raw.split(",") if p.strip()]

    if len(sys.argv) <= 5 and not (work != "any" or locs_raw or target):
        print("\n=== Work type (your gate - hard filter) ===")
        work = _prompt_work_type()
        locs = _prompt_locations()
        print("\n=== Target roles (comma separated, blank = let the agent infer) ===")
        target = input("> ").strip()

    print(f"\nUploading {resume} -> {base}/upload")
    profile_id = _upload(base, resume, work, locs, target)

    print("\nStarting pipeline (SSE live progress) ...")
    run_id = _start_run(base, profile_id, seed=seed, seen=seen)
    print(f"run_id: {run_id}")
    print()

    result = _stream(base, run_id)
    if approve:
        result = _approve_top(base, result)
    _render(result)
    exporter = HtmlExporter()
    exporter.export(result, "result-demo.html")
    exporter.save_json(result, "result-demo.json")
    print("\n  saved: ./result-demo.html")
    print("  saved: ./result-demo.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
