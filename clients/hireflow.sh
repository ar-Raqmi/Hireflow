#!/usr/bin/env bash

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"

if [[ -f "$ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
fi

BASE_URL="${HIREFLOW_BASE_URL:-https://hireflow-backend-296941301245.us-central1.run.app}"

for t in curl python3; do
  command -v "$t" >/dev/null 2>&1 || { echo "missing required tool: $t"; exit 1; }
done

PY="python3"
if [[ -x "$ROOT/.venv/bin/python3" ]]; then
  PY="$ROOT/.venv/bin/python3"
fi

echo
echo "  hireflow-cli · online · $BASE_URL"
echo "  (the pipeline runs on Cloud Run - nothing is computed locally)"
echo

RESUME=""
ask_file() {
  local dir="${HOME}/Downloads" rel cand
  [[ -d "$dir" ]] || dir="$HOME"
  while :; do
    printf 'Resume path [%s]: ' "$dir"
    read -r rel
    [[ -z "$rel" ]] && { printf 'no file given - aborting\n' >&2; exit 1; }
    cand="$rel"
    [[ "$rel" == /* ]] || cand="${dir}/${rel}"
    if [[ -f "$cand" ]]; then RESUME="$cand"; return; fi
    printf '  not found: %s\n' "$cand" >&2
  done
}
ask_file

WORK=""
printf '\nWork type:\n'
select w in "Remote" "Onsite" "Hybrid" "Anywhere (skip)"; do
  [[ -z "$w" ]] && continue
  case "$w" in
    Remote|remote) WORK="remote"; break;;
    Onsite|onsite) WORK="onsite"; break;;
    Hybrid)        WORK="hybrid"; break;;
    *Any*)         WORK="any";    break;;
  esac
done
echo "work_type: ${WORK:-any}"

LOCS=()
printf '\nPreferred work locations (comma separated; blank = anywhere):\n'
printf '> '
IFS= read -r line
if [[ -n "$line" ]]; then
  IFS=',' read -r -a parts <<< "$line"
  for part in "${parts[@]}"; do
    part="${part#"${part%%[![:space:]]*}"}"   # trim leading whitespace
    part="${part%"${part##*[![:space:]]}"}"    # trim trailing whitespace
    [[ -n "$part" ]] && LOCS+=("$part")
  done
fi
[[ "${#LOCS[@]}" -gt 0 ]] && echo "locations: ${LOCS[*]} (${#LOCS[@]})" || echo "locations: stay"

TARGET=""
printf '\nTarget roles (comma separated, blank = let the agent infer):\n'
printf '> '
IFS= read -r TARGET
[[ -n "$TARGET" ]] && echo "target_roles: $TARGET" || echo "target_roles: (infer from resume)"

FIELDS=(-F "file=@${RESUME}")
[[ -n "$WORK" ]] && FIELDS+=(-F "work_type=$WORK")
if [[ "${#LOCS[@]}" -gt 0 ]]; then
  FIELDS+=(-F "locations=$(IFS=,; echo "${LOCS[*]}")")
fi
[[ -n "$TARGET" ]] && FIELDS+=(-F "target_roles=$TARGET")

echo
echo "Uploading ${RESUME} → ${BASE_URL}/upload"
RESP="$(curl -sf -X POST "${BASE_URL}/upload" "${FIELDS[@]}")" || {
  echo "upload failed" >&2
  exit 1
}
echo "$RESP"
PROFILE_ID="$("$PY" -c "import json,sys;print(json.load(sys.stdin).get('id',''))" <<< "$RESP")"
[[ -n "$PROFILE_ID" ]] || { echo "no profile id in response" >&2; exit 1; }

echo
echo "Starting pipeline for profile $PROFILE_ID (SSE live progress) …"
RUN_ID="$(curl -sf -X POST "${BASE_URL}/pipeline/run?profile_id=${PROFILE_ID}" \
  | "$PY" -c "import json,sys; print(json.load(sys.stdin).get('run_id',''))")" || {
  echo "pipeline start failed" >&2
  exit 1
}
[[ -n "$RUN_ID" ]] || { echo "no run_id in pipeline response" >&2; exit 1; }
echo "run_id: $RUN_ID"

echo
echo "Streaming live progress from ${BASE_URL}/pipeline/run/${RUN_ID}/events"
echo "--------------------------------------------------------------------------------"
PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}" "$PY" - "$BASE_URL" "$RUN_ID" "$PROFILE_ID" <<'PY'
import json, subprocess, sys, time
base, run_id, pid = sys.argv[1], sys.argv[2], sys.argv[3]
started = time.monotonic()
result = None
resume_seq = 0
attempts = 0
max_attempts = 12

EMOJI = {
    "parse": "Reading resume",
    "audit": "Auditing ATS health",
    "search": "Searching job boards",
    "match": "Scoring matches",
    "research": "Researching companies",
    "prepare": "Drafting CV + cover letter",
    "approve": "Finalizing applications",
}

while result is None and attempts <= max_attempts:
    url = f"{base}/pipeline/run/{run_id}/events"
    headers = ["-H", f"Last-Event-ID: {resume_seq}"] if resume_seq else []
    proc = subprocess.Popen(
        ["curl", "-sN", "--max-time", "600"] + headers + [url],
        stdout=subprocess.PIPE,
        text=True,
    )
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
        except Exception:
            continue
        if event == "done":
            result = payload
            break
        event = ""
        if "stage" in payload:
            stage = payload.get("stage", "")
            detail = payload.get("detail", "") or ""
            emoji = EMOJI.get(stage, stage)
            elapsed = int(time.monotonic() - started)
            print(f"  [+{elapsed:>5}s] {emoji}  {detail}")
            sys.stdout.flush()
    proc.wait()
    if result is not None:
        break
    attempts += 1
    if attempts <= max_attempts:
        time.sleep(2)

if result is None:
    print("pipeline finished without a done event", file=sys.stderr)
    sys.exit(1)

print("\n" + "=" * 64)
print("HIREFLOW REPORT · profile", pid, "· run", (result.get("run_id") or "")[:8])
print("=" * 64)
print("status:     ", result.get("status"))
print("jobs_found: ", result.get("jobs_found", 0))

matches = result.get("matches") or []
print(f"\nTOP MATCHES ({len(matches)})")
for m in matches[:10]:
    print(f'  {m.get("score",0):>3}  {str(m.get("title",""))[:46]:<46} @ {str(m.get("company",""))[:28]:<28}')
    print(f'      loc:{str(m.get("location",""))[:40]:<40} url:{str(m.get("post_url",""))[:70]}')
    reasons = m.get("reasons") or []
    if reasons:
        print(f'      why: {str(reasons[0])[:110]}')

apps = result.get("applications") or []
print(f"\nAPPLICATIONS ({len(apps)})")
for a in apps:
    drafted = "  [draft ready]" if a.get("drafted") else ""
    submitted = f"  submitted {a.get('ats_confirmation','')}" if a.get("ats_confirmation") else ""
    print(f'  {str(a.get("id",""))[:12]}  status={a.get("status","")}  score={a.get("score","")}'
          f'{"  needs_human" if a.get("human_handoff") else ""}  {str(a.get("title",""))[:44]}{drafted}{submitted}')

print("\nneeds_human:", result.get("needs_human") or [])
print("\nNext: POST /approve?application_id=<id> to submit to the sandbox ATS (confirmation in /sandbox/ats/submissions).")
print("=" * 64)

try:
    from hireflow.export_html import HtmlExporter
    exporter = HtmlExporter()
    exporter.export(result, "result-demo.html")
    exporter.save_json(result, "result-demo.json")
    print("\n  saved: ./result-demo.html")
    print("  saved: ./result-demo.json")
except ImportError as exc:
    print(f"\n  (could not export result-demo.html: {exc})")
PY
