
const PREFS_KEY = 'hireflow.prefs.v1';
const HISTORY_KEY = 'hireflow.history.v1';
const SEEN_KEY = 'hireflow.seen.v1';

function safeGet(key, fallback) {
  try {
    const raw = localStorage.getItem(key);
    return raw ? JSON.parse(raw) : fallback;
  } catch {
    return fallback;
  }
}

function safeSet(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
  }
}

export function loadPrefs() {
  return safeGet(PREFS_KEY, { work_type: 'any', locations: [], target_roles: [] });
}

export function savePrefs(prefs) {
  safeSet(PREFS_KEY, prefs);
}

export function loadHistory() {
  return safeGet(HISTORY_KEY, []);
}

export function pushHistory(run) {
  const history = loadHistory();
  history.unshift(run);
  safeSet(HISTORY_KEY, history.slice(0, 50));
}

export function clearHistory() {
  localStorage.removeItem(HISTORY_KEY);
}

export function loadSeen() {
  return safeGet(SEEN_KEY, []);
}

export function markSeen(jobs) {
  const seen = loadSeen();
  const ids = (jobs || []).map((j) => String((j && (j.id || j.job_id)) || '')).filter(Boolean);
  const merged = Array.from(new Set([...seen, ...ids]));
  safeSet(SEEN_KEY, merged.slice(-500));
  return merged;
}

const ACTIVE_RUN_KEY = 'hireflow.active_run.v1';

export function saveActiveRun(info) {
  safeSet(ACTIVE_RUN_KEY, info);
}

export function loadActiveRun() {
  return safeGet(ACTIVE_RUN_KEY, null);
}

export function clearActiveRun() {
  try {
    localStorage.removeItem(ACTIVE_RUN_KEY);
  } catch {
  }
}
