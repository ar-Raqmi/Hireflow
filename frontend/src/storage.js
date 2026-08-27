
const PREFS_KEY = 'hireflow.prefs.v1';
const HISTORY_KEY = 'hireflow.history.v1';
const SEEN_KEY = 'hireflow.seen.v1';
const POOL_KEY = 'hireflow.pool.v1';
const DRAFTS_KEY = 'hireflow.drafts.v1';
const VIEW_KEY = 'hireflow.view.v1';
const PROFILE_KEY = 'hireflow.profile.v1';
const LAST_CHECK_KEY = 'hireflow.last_check.v1';
export const MAX_POOL = 50;
export const AUTO_CHECK_MINUTES = 24 * 60;
export const AUTO_CHECK_MAX_MINUTES = 48 * 60;

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

export function loadPrefsUnset() {
  return localStorage.getItem(PREFS_KEY) === null;
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

export function loadPool() {
  return safeGet(POOL_KEY, []);
}

export function savePool(pool) {
  safeSet(POOL_KEY, pool.slice(0, MAX_POOL));
}

export function loadDrafts() {
  return safeGet(DRAFTS_KEY, {});
}

export function saveDrafts(drafts) {
  safeSet(DRAFTS_KEY, drafts || {});
}

export function mergeDrafts(drafts) {
  const merged = { ...loadDrafts(), ...(drafts || {}) };
  saveDrafts(merged);
  return merged;
}

export function loadLastView() {
  return safeGet(VIEW_KEY, 'agent');
}

export function saveLastView(view) {
  safeSet(VIEW_KEY, view);
}

export function loadProfile() {
  return safeGet(PROFILE_KEY, null);
}

export function saveProfile(profile) {
  safeSet(PROFILE_KEY, profile);
}

export function clearProfile() {
  try {
    localStorage.removeItem(PROFILE_KEY);
  } catch {
  }
}

export function loadLastCheck() {
  const v = safeGet(LAST_CHECK_KEY, 0);
  return Number(v) || 0;
}

export function saveLastCheck(ts = Date.now()) {
  safeSet(LAST_CHECK_KEY, ts);
}

export function shouldAutoCheck() {
  const profile = loadProfile();
  if (!profile) return false;
  const elapsed = Date.now() - loadLastCheck();
  if (elapsed < AUTO_CHECK_MINUTES * 60 * 1000) return false;
  if (elapsed > AUTO_CHECK_MAX_MINUTES * 60 * 1000) return false;
  return true;
}
