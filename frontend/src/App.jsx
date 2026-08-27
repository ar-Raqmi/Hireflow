import { useEffect, useRef, useState } from 'react';
import { M3eButton } from '@m3e/react/button';
import { M3eTabs, M3eTab } from '@m3e/react/tabs';
import { health, startPipeline, streamEvents, fetchRunStatus, cancelPipeline } from './api.js';
import {
  loadPrefs, savePrefs, loadPrefsUnset, loadHistory, pushHistory, clearHistory, loadSeen, markSeen,
  saveActiveRun, loadActiveRun, clearActiveRun,
  loadPool, savePool, clearPool, loadLastView, saveLastView, MAX_POOL,
  loadProfile, saveProfile, clearProfile, shouldAutoCheck, loadLastCheck, saveLastCheck,
  loadDrafts, saveDrafts, mergeDrafts,
} from './storage.js';
import ResumeDrop from './components/ResumeDrop.jsx';
import PrefsModal from './components/PrefsModal.jsx';
import ResumeAuditModal from './components/ResumeAuditModal.jsx';
import AgentTimeline from './components/AgentTimeline.jsx';
import MatchesList from './components/MatchesList.jsx';
import HistoryTab from './components/HistoryTab.jsx';
import NewJobsModal from './components/NewJobsModal.jsx';
import Toast from './components/Toast.jsx';
import M3eIcon from './components/M3eIcon.jsx';

const VIEWS = [
  { key: 'agent', label: 'Agent run', icon: 'monitoring' },
  { key: 'results', label: 'Results', icon: 'work' },
  { key: 'history', label: 'History', icon: 'history' },
];

function mergePool(pool, incoming) {
  const byId = new Map();
  for (const m of pool) {
    const id = String((m && (m.job_id || m.id)) || '');
    if (id) byId.set(id, { ...m, isNew: false });
  }
  const prevSeen = new Set(pool.map((m) => String((m && (m.job_id || m.id)) || '')).filter(Boolean));
  for (const m of incoming) {
    const id = String((m && (m.job_id || m.id)) || '');
    if (!id) continue;
    byId.set(id, { ...m, isNew: !prevSeen.has(id) });
  }
  return [...byId.values()]
    .sort((a, b) => (Number(b.score) || 0) - (Number(a.score) || 0))
    .slice(0, MAX_POOL);
}

export default function App() {
  const [prefs, setPrefs] = useState(() => loadPrefs());
  const [prefsOpen, setPrefsOpen] = useState(() => loadPrefsUnset());
  const [profile, setProfile] = useState(() => loadProfile());
  const [running, setRunning] = useState(false);
  const [events, setEvents] = useState([]);
  const [result, setResult] = useState(null);
  const [matches, setMatches] = useState([]);
  const [newCount, setNewCount] = useState(0);
  const [applications, setApplications] = useState([]);
  const [history, setHistory] = useState(() => loadHistory());
  const [toast, setToast] = useState(null);
  const [view, setView] = useState(() => loadLastView());
  const [audit, setAudit] = useState(null);
  const [newJobsNotice, setNewJobsNotice] = useState(null);
  const runRef = useRef(null);

  useEffect(() => {
    health().catch((e) => {
      showToast(`Backend unreachable: ${e.message}`, 'error');
    });
    const active = loadActiveRun();
    if (active && active.runId) {
      resumeRun(active);
      return;
    }
    if (shouldAutoCheck()) {
      const p = loadProfile();
      if (p) {
        restoreCachedPool();
        handleRun({ ...p, isAuto: true });
        return;
      }
    }
    restoreCachedPool();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function restoreCachedPool() {
    let pool = loadPool();
    let drafts = loadDrafts();
    if ((!pool || pool.length === 0) || (!drafts || Object.keys(drafts).length === 0)) {
      const h = loadHistory();
      const last = h[0];
      if (last && last.result && last.result.matches && last.result.matches.length > 0) {
        if (!pool || pool.length === 0) {
          pool = last.result.matches.map((m) => ({ ...m, isNew: Boolean(m.isNew) }));
          savePool(pool);
        }
        if (!drafts || Object.keys(drafts).length === 0) {
          drafts = last.result.drafts || {};
          saveDrafts(drafts);
        }
      }
    }
    if (pool && pool.length > 0) {
      setResult({ status: 'completed', matches: pool, drafts });
      setMatches(pool);
      setNewCount(pool.filter((m) => m.isNew).length);
      setApplications((pool[0] && pool[0]._applications) || []);
    }
  }

  useEffect(() => {
    saveLastView(view);
  }, [view]);

  function showToast(message, kind = 'info', ms) {
    setToast({ message, kind, ms, ts: Date.now() });
  }

  function resetRunState() {
    setRunning(true);
    setEvents([]);
    setResult(null);
    setMatches([]);
    setNewCount(0);
    setApplications([]);
    setView('agent');
  }

  function applyResult(res, p) {
    setResult(res);
    const prevSeen = new Set(loadSeen().map(String));
    const a = res.applications || res.application_records || [];
    const fresh = (res.matches || []).filter((m) => {
      const id = String((m && (m.job_id || m.id)) || '');
      return id !== '' && !prevSeen.has(id);
    }).length;
    const merged = mergePool(loadPool(), res.matches || []);
    const tagged = merged.map((m) => ({ ...m, _applications: a }));
    setMatches(tagged);
    setNewCount(fresh);
    setApplications(a);
    savePool(tagged);
    mergeDrafts(res.drafts);
    clearActiveRun();
    if (res.status === 'cancelled') {
      setRunning(false);
      showToast('Run cancelled - agent stopped');
      return;
    }
    markSeen(res.matches || []);
    const historyEntry = {
      ts: Date.now(),
      filename: (p && p.filename) || 'resume',
      prefs,
      status: res.status || 'completed',
      new_matches: fresh,
      result: res,
    };
    pushHistory(historyEntry);
    setHistory(loadHistory());
    if (res.status === 'error' || (res.errors && res.errors.length > 0)) {
      showToast((res.detail || (res.errors && res.errors[0])) || 'Run finished with errors', 'error', 6000);
    } else if (fresh > 0) {
      showToast(`Run complete - ${fresh} new since your last check, ${a.length} applications`);
      setNewJobsNotice({ count: fresh, matches: tagged });
    } else {
      showToast(`No new jobs since your last check - ${merged.length} saved matches`, 'info');
    }
    setRunning(false);
  }

  async function streamRun(runId, p) {
    runRef.current = runId;
    await streamEvents(runId, {
      onEvent: (ev) => {
        if (runRef.current === runId) setEvents((prev) => [...prev, ev]);
      },
      onDone: (res) => {
        if (runRef.current !== runId) return;
        applyResult(res, p);
      },
      onError: (err) => {
        if (runRef.current !== runId) return;
        showToast(`Stream error: ${err.message}`, 'error', 6000);
        setRunning(false);
      },
    });
  }

  async function resumeRun(active) {
    let info = null;
    try {
      info = await fetchRunStatus(active.runId);
    } catch {
      setRunning(false);
      showToast('Backend unreachable - run will resume when it is back', 'error', 6000);
      return;
    }
    if (!info || !info.exists) {
      clearActiveRun();
      setRunning(false);
      showToast('Previous run is no longer available', 'info');
      return;
    }
    const p = active.profile || null;
    if (p) setProfile(p);
    if (info.done) {
      applyResult(info.result || { status: 'completed', run_id: active.runId }, p);
      return;
    }
    resetRunState();
    showToast('Resuming previous agent run');
    await streamRun(active.runId, p);
  }

  function handleUploaded(parsed) {
    setProfile(parsed);
    setAudit(null);
    if (parsed && parsed.status === 'needs_improvement') {
      saveProfile(parsed);
      setAudit(parsed.audit || { health: 0, findings: [] });
      showToast('Résumé parsed, but it could be improved before the run', 'warn', 7000);
      return;
    }
    saveProfile(parsed);
    showToast(`Résumé parsed - ${parsed.skills ? parsed.skills.length : 0} skills extracted`);
    handleRun(parsed);
  }

  function handleUploadRejected(parsed) {
    setProfile(null);
    setAudit(null);
    showToast(
      parsed && parsed.reason ? `Not a résumé: ${parsed.reason}` : 'That file does not look like a résumé',
      'error',
      8000,
    );
  }

  function handleRunAnyway() {
    setAudit(null);
    handleRun();
  }

  function handleNewResume() {
    setAudit(null);
    setProfile(null);
    clearProfile();
    clearPool();
    setMatches([]);
    setNewCount(0);
    setApplications([]);
    setResult(null);
    setView('agent');
    showToast('Résumé cleared - upload a new one to start');
  }

  function handlePrefsSave(p) {
    setPrefs(p);
    savePrefs(p);
    setPrefsOpen(false);
    showToast('Preferences saved');
    if (profile) handleRun();
  }

  function handlePrefsSkip() {
    setPrefsOpen(false);
    showToast('Using résumé defaults');
    if (profile) handleRun();
  }

  function handleViewTab(key) {
    if (key === 'settings') {
      setPrefsOpen(true);
      return;
    }
    setView(key);
  }

  async function handleRun(override) {
    if (running) {
      showToast('A run is already in progress', 'error');
      return;
    }
    const p = override || profile;
    if (!p) {
      showToast('Upload a résumé first', 'error');
      return;
    }
    resetRunState();

    let runId = null;
    try {
      const seen = loadSeen();
      const started = await startPipeline(p.id, {
        seed: Math.floor(Math.random() * 1000),
        seen,
        profile: p,
      });
      runId = started.run_id;
      if (!runId) throw new Error('Pipeline did not return a run_id');
      runRef.current = runId;
      saveActiveRun({
        runId,
        profile: { id: p.id, filename: p.filename, target_roles: p.target_roles },
      });
      showToast(p.isAuto ? 'Checking for new jobs since your last visit…' : 'Agent run started');
      await streamRun(runId, p);
      saveLastCheck();
    } catch (err) {
      showToast(`Failed to start run: ${err.message}`, 'error', 6000);
      setRunning(false);
    }
  }

  async function handleCancel() {
    const runId = runRef.current;
    if (!runId) return;
    try {
      await cancelPipeline(runId);
    } catch (err) {
      showToast(`Cancel failed: ${err.message}`, 'error', 6000);
      return;
    }
    clearActiveRun();
    setRunning(false);
    showToast('Cancelling…');
  }

  function handleClearHistory() {
    clearHistory();
    setHistory([]);
    showToast('History cleared');
  }

  function handleNewJobsView() {
    const notice = newJobsNotice;
    setNewJobsNotice(null);
    setView('results');
  }

  function restoreRun(run) {
    const pool = loadPool();
    const res = run.result || { status: 'completed', matches: [], applications: [] };
    const tagged = (res.matches || []).map((m) => ({ ...m, isNew: Boolean(m.isNew) }));
    setResult({ ...res, drafts: res.drafts || loadDrafts() });
    setMatches(pool.length > 0 ? pool : tagged);
    setNewCount((pool.length > 0 ? pool : tagged).filter((m) => m.isNew).length);
    setApplications(res.applications || res.application_records || []);
    setRunning(false);
    setView('results');
    showToast(`Restored run from ${new Date(run.ts || Date.now()).toLocaleString()}`);
  }

  const matchCount = matches.length;

  return (
    <div className="app">
      <header className="topbar wrap">
        <div className="logo">
          Hireflow<b>.</b>
        </div>
      </header>

      <M3eTabs variant="secondary" className="wrap viewtabs" onChange={(e) => handleViewTab(e.target?.selectedTab?.getAttribute('data-view') || view)}>
        {VIEWS.map((v) => {
          const badge = v.key === 'results' ? (newCount > 0 ? newCount : matchCount) : 0;
          return (
            <M3eTab
              key={v.key}
              data-view={v.key}
              selected={view === v.key}
            >
              <M3eIcon slot="icon" name={v.icon} size={16} />
              {v.label}
              {badge > 0 && <span className="vbadge">{badge}</span>}
            </M3eTab>
          );
        })}
        <M3eTab
          key="settings"
          data-view="settings"
          selected={false}
        >
          <M3eIcon slot="icon" name="tune" size={16} />
          Settings
        </M3eTab>
      </M3eTabs>

      {view === 'agent' && (
        <main>
          <div className="wrap">
            <section className={`hero ${profile ? 'gone' : ''}`}>
              <div className="hero-grid">
                <div>
                  <div className="eyebrow">Autonomous job-search agent</div>
                  <h1>
                    The job hunt,<br />
                    <span className="accent">running itself.</span>
                  </h1>
                  <p className="sub">
                    Drop in a résumé and Hireflow watches from there - parsing, auditing, searching,
                    researching and tailoring. Come back any time to see what's new. You only approve.
                  </p>
                  <M3eButton
                    variant="filled"
                    className="runbtn"
                    disabled={!profile || running}
                    onClick={() => handleRun()}
                  >
                    {running && <M3eIcon name="progress_activity" size={18} className="spin" />}
                    {!running && <M3eIcon name="play_arrow" size={18} />}
                    {running ? 'Running…' : profile ? (matchCount > 0 ? 'Check for new jobs' : 'Run the agent') : 'Upload a résumé to start'}
                  </M3eButton>
                </div>
                <ResumeDrop onUploaded={handleUploaded} onRejected={handleUploadRejected} onError={(e) => showToast(`Upload failed: ${e.message}`, 'error', 6000)} prefs={prefs} />
              </div>
            </section>
            {profile && (
              <div className="profile-strip">
                <span className="filechip">
                  <M3eIcon name="description" size={15} />
                  <span className="fc-name">{profile.filename || profile.id}</span>
                </span>
                {profile.target_roles && profile.target_roles.length > 0 && (
                  <span className="hchip">{profile.target_roles.slice(0, 3).join(', ')}</span>
                )}
                <M3eButton variant="filled" className="runbtn-strip" disabled={running} onClick={() => handleRun()}>
                  {running && <M3eIcon name="progress_activity" size={16} className="spin" />}
                  {!running && <M3eIcon name="refresh" size={16} />}
                  {running ? 'Running…' : 'Check for new jobs'}
                </M3eButton>
                <M3eButton variant="text" className="newresume" onClick={handleNewResume}>
                  <M3eIcon name="note_add" size={16} /> New résumé
                </M3eButton>
              </div>
            )}
            <AgentTimeline events={events} running={running} onCancel={running ? handleCancel : undefined} />
            {result && (result.errors && result.errors.length > 0) && (
              <div className="riskbanner high">
                <M3eIcon name="warning" size={28} />
                <div className="rb-txt">
                  <b>Backend reported {result.errors.length} error{result.errors.length === 1 ? '' : 's'}:</b>{' '}
                  {result.errors.slice(0, 4).join(' · ')}
                </div>
              </div>
            )}
          </div>
        </main>
      )}

      {view === 'results' && (
        <main>
          <div className="wrap">
            <section className="results in">
              <div className="results-head">
                <div>
                  <h2>Results</h2>
                  <div className="res-meta">
                    {running ? 'agent still running…' : matchCount === 0 ? 'run the agent to see matches' : newCount > 0 ? `${newCount} new since your last check · ${matchCount} saved matches` : `${matchCount} saved matches (top ${MAX_POOL})`}
                  </div>
                </div>
              </div>
              <MatchesList matches={matches} applications={applications} drafts={result?.drafts || {}} newCount={newCount} onError={(e) => showToast(e.message, 'error', 6000)} />
            </section>
          </div>
        </main>
      )}

      {view === 'history' && (
        <main>
          <div className="wrap">
            <HistoryTab history={history} onClear={handleClearHistory} onRestore={restoreRun} />
          </div>
        </main>
      )}

      <footer>
        <span>Created by ar-Raqmi and Izaaz</span>
      </footer>

      <PrefsModal open={prefsOpen} initial={prefs} onSave={handlePrefsSave} onSkip={handlePrefsSkip} onClose={() => setPrefsOpen(false)} />
      <ResumeAuditModal open={!!audit} audit={audit} onRun={handleRunAnyway} onClose={() => setAudit(null)} />
      <NewJobsModal open={!!newJobsNotice} notice={newJobsNotice} onView={handleNewJobsView} onClose={() => setNewJobsNotice(null)} />
      <Toast toast={toast} />
    </div>
  );
}
