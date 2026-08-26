// api.js — the single place the frontend talks to the REAL Hireflow backend.
// Base URL: VITE_HIREFLOW_API (the deployed `.run.app` URL, no trailing slash).
// When unset and served by the Vite dev server, `/api/...` is proxied to the
// backend by vite.config.js. Every function returns real API data — nothing is
// mocked or hardcoded.

function resolveBase() {
  if (import.meta.env.VITE_HIREFLOW_API) {
    return import.meta.env.VITE_HIREFLOW_API.replace(/\/$/, '');
  }
  // Dev server proxies /api -> backend (see vite.config.js proxy).
  return '/api';
}

const BASE = resolveBase();

console.log('Hireflow API BASE:', BASE);
console.log('VITE_HIREFLOW_API:', import.meta.env.VITE_HIREFLOW_API);

async function jsonRequest(res, context) {
  let body;
  try {
    body = await res.json();
  } catch {
    body = null;
  }
  if (!res.ok) {
    const detail = body && (body.detail || body.error || body.message);
    const err = new Error(`${context}: ${res.status} ${res.statusText}${detail ? ` — ${detail}` : ''}`);
    err.status = res.status;
    err.payload = body;
    throw err;
  }
  return body;
}

export async function health() {
  const res = await fetch(`${BASE}/health`);
  return jsonRequest(res, 'health check');
}

// upload — multipart resume file + preferences. Returns the parsed Profile.
// Pass AbortSignal (via `signal`) to cancel the in-flight upload.
export async function uploadResume({ file, work_type, locations, target_roles, salary_floor, signal }) {
  const form = new FormData();
  form.append('file', file);
  form.append('work_type', work_type || 'any');
  form.append('locations', (locations || []).join(','));
  form.append('target_roles', (target_roles || []).join(','));
  if (salary_floor) form.append('salary_floor', String(salary_floor));
  const res = await fetch(`${BASE}/upload`, { method: 'POST', body: form, signal });
  return jsonRequest(res, 'resume upload');
}

// startPipeline — POST /pipeline/run?profile_id=...&seed=...&seen=...
export async function startPipeline(profileId, { seed = 0, seen = [] } = {}) {
  const qs = new URLSearchParams({ profile_id: profileId, seed: String(seed) });
  if (seen && seen.length) qs.set('seen', seen.join(','));
  const res = await fetch(`${BASE}/pipeline/run?${qs.toString()}`, { method: 'POST' });
  return jsonRequest(res, 'start pipeline');
}

// fetchRunStatus — GET /pipeline/run/{runId} → {exists, done, status, result}.
// Used on app mount to resume a run after a refresh.
export async function fetchRunStatus(runId) {
  const res = await fetch(`${BASE}/pipeline/run/${encodeURIComponent(runId)}`);
  return jsonRequest(res, 'pipeline status');
}

// cancelPipeline — POST /pipeline/run/{runId}/cancel → stops the background
// task so the backend stops doing work for an abandoned run.
export async function cancelPipeline(runId) {
  const res = await fetch(`${BASE}/pipeline/run/${encodeURIComponent(runId)}/cancel`, { method: 'POST' });
  return jsonRequest(res, 'cancel pipeline');
}

// streamEvents — consume the SSE stream for a run. Calls onEvent(data) for
// each `data:` line and onDone(result) on the final `event: done`. Handles
// `id:` lines for resume via Last-Event-ID. Uses fetch + ReadableStream so it
// works from both the dev proxy and the deployed origin.
export async function streamEvents(runId, { onEvent, onDone, onError } = {}) {
  let lastId = 0;
  let done = false;
  let dataLines = '';
  const parseFrame = (raw) => {
    let event = 'message';
    dataLines = '';
    for (const line of raw.split('\n')) {
      if (line.startsWith('event:')) event = line.slice(6).trim();
      else if (line.startsWith('id:')) {
        const v = parseInt(line.slice(3).trim(), 10);
        if (!Number.isNaN(v)) lastId = v;
      } else if (line.startsWith('data:')) {
        const val = line.slice(5).trim();
        dataLines += dataLines ? `\n${val}` : val;
      }
    }
    if (!dataLines) return;
    let payload;
    try {
      payload = JSON.parse(dataLines);
    } catch {
      return;
    }
    if (event === 'done') {
      done = true;
      onDone?.(payload);
    } else {
      onEvent?.(payload);
    }
  };
  while (!done) {
    const headers = {};
    if (lastId > 0) headers['Last-Event-ID'] = String(lastId);
    let res;
    try {
      res = await fetch(`${BASE}/pipeline/run/${runId}/events`, { headers });
    } catch (err) {
      onError?.(err);
      return;
    }
    if (!res.ok || !res.body) {
      onError?.(new Error(`SSE stream failed (${res.status} ${res.statusText})`));
      return;
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    try {
      while (!done) {
        const { value, done: streamDone } = await reader.read();
        if (streamDone) break;
        buffer += decoder.decode(value, { stream: true });
        let idx;
        // SSE frames are separated by a blank line.
        while ((idx = buffer.indexOf('\n\n')) !== -1) {
          const raw = buffer.slice(0, idx);
          buffer = buffer.slice(idx + 2);
          parseFrame(raw);
        }
      }
      if (done) await reader.cancel().catch(() => {});
    } catch (err) {
      onError?.(err);
      return;
    }
  }
}