#!/usr/bin/env bash
# hireflow.sh — thin ONLINE client for the deployed Hireflow pipeline.
# Prompts for resume + prefs, uploads to Cloud Run, runs the pipeline
# server-side, prints the full report. Nothing is computed locally.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ -f "$HERE/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$HERE/.env"
  set +a
fi

BASE_URL="${HIREFLOW_BASE_URL:-https://hireflow-backend-296941301245.us-central1.run.app}"

for t in curl python3; do
  command -v "$t" >/dev/null 2>&1 || { echo "missing required tool: $t"; exit 1; }
done

echo
echo "  hireflow-cli · online · $BASE_URL"
echo "  (the pipeline runs on Cloud Run — nothing is computed locally)"
echo

# --- 1. resume file ---
RESUME=""
ask_file() {
  local dir="${HOME}/Downloads" rel cand
  [[ -d "$dir" ]] || dir="$HOME"
  while :; do
    printf 'Resume path [%s]: ' "$dir"
    read -r rel
    [[ -z "$rel" ]] && { printf 'no file given — aborting\n' >&2; exit 1; }
    cand="$rel"
    [[ "$rel" == /* ]] || cand="${dir}/${rel}"
    if [[ -f "$cand" ]]; then RESUME="$cand"; return; fi
    printf '  not found: %s\n' "$cand" >&2
  done
}
ask_file

# --- 2. work type (menu) ---
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

# --- 3. locations ---
LOCS=()
printf '\nPreferred work locations (comma separated; blank = anywhere):\n'
printf '> '
IFS= read -r line
if [[ -n "$line" ]]; then
  while IFS= read -r part; do
    part="${part#"${part%%[![:space:]]*}"}"   # trim leading whitespace
    part="${part%"${part##*[![:space:]]}"}"    # trim trailing whitespace
    [[ -n "$part" ]] && LOCS+=("$part")
  done < <(printf '%s' "$line" | tr ',' '\n')
fi
[[ "${#LOCS[@]}" -gt 0 ]] && echo "locations: ${LOCS[*]} (${#LOCS[@]})" || echo "locations: any"

# --- 4. target roles (optional) ---
TARGET=""
printf '\nTarget roles (comma separated, blank = let the agent infer):\n'
printf '> '
IFS= read -r TARGET
[[ -n "$TARGET" ]] && echo "target_roles: $TARGET" || echo "target_roles: (infer from resume)"

# --- upload + run pipeline ---
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
PROFILE_ID="$(python3 -c "import json,sys;print(json.load(sys.stdin).get('id',''))" <<< "$RESP")"
[[ -n "$PROFILE_ID" ]] || { echo "no profile id in response" >&2; exit 1; }

echo
echo "Running pipeline for profile $PROFILE_ID …"
RESULT="$(curl -s -X POST "${BASE_URL}/pipeline/run?profile_id=${PROFILE_ID}")"

TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT
printf '%s' "$RESULT" > "$TMP"

python3 - "$TMP" "$BASE_URL" "$PROFILE_ID" <<'PY'
import json, sys
path, base, pid = sys.argv[1], sys.argv[2], sys.argv[3]
with open(path) as f:
    data = f.read()
try:
    r = json.loads(data)
except Exception:
    print("RAW RESPONSE (not JSON):")
    print(data[:3000])
    sys.exit(1)

print("=" * 64)
print("HIREFLOW REPORT · profile", pid)
print("=" * 64)
print("status:     ", r.get("status"))
print("jobs_found: ", r.get("jobs_found", 0))

matches = r.get("matches") or []
print(f"\nTOP MATCHES ({len(matches)})")
for m in matches[:10]:
    job = m.get("job", {})
    print(f'  {m.get("score",0):>3}  {str(job.get("title",""))[:46]:<46} @ {str(job.get("company",""))[:28]:<28}')
    print(f'      loc:{str(job.get("location",""))[:40]:<40} url:{str(job.get("post_url",""))[:70]}')
    reasons = m.get("reasons") or []
    if reasons:
        print(f'      why: {str(reasons[0])[:110]}')

apps = r.get("applications") or []
print(f"\nAPPLICATIONS ({len(apps)})")
for a in apps:
    job = a.get("job") or {}
    jt = str(job.get("title", ""))[:44]
    print(f'  {str(a.get("id",""))[:12]}  status={a.get("status","")}  score={a.get("score","")}'
          f'{"  needs_human" if a.get("human_handoff") else ""}  {jt}')

print("\nneeds_human:", r.get("needs_human") or [])
print("\nNext: POST /approve?application_id=<id> to act on a drafted app.")
print("=" * 64)
PY