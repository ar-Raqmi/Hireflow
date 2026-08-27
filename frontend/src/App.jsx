import { useEffect, useRef, useState } from 'react';
import { M3eButton } from '@m3e/react/button';
import { M3eTabs, M3eTab } from '@m3e/react/tabs';
import { health, startPipeline, streamEvents, fetchRunStatus, cancelPipeline } from './api.js';
import {
  loadPrefs, savePrefs, loadHistory, pushHistory, clearHistory, loadSeen, markSeen,
  saveActiveRun, loadActiveRun, clearActiveRun,
} from './storage.js';
import ResumeDrop from './components/ResumeDrop.jsx';
import PrefsModal from './components/PrefsModal.jsx';
import ResumeAuditModal from './components/ResumeAuditModal.jsx';
import AgentTimeline from './components/AgentTimeline.jsx';
import MatchesList from './components/MatchesList.jsx';
import HistoryTab from './components/HistoryTab.jsx';
import Toast from './components/Toast.jsx';
import M3eIcon from './components/M3eIcon.jsx';

const VIEWS = [
  { key: 'agent', label: 'Agent run', icon: 'monitoring' },
  { key: 'results', label: 'Results', icon: 'work' },
  { key: 'history', label: 'History', icon: 'history' },
];

export default function App() {
  const [prefs, setPrefs] = useState(() => loadPrefs());
  const [prefsOpen, setPrefsOpen] = useState(true);
  const [profile, setProfile] = useState(null);
  const [running, setRunning] = useState(false);
  const [events, setEvents] = useState([]);
  const [result, setResult] = useState(null);
  const [matches, setMatches] = useState([]);
  const [applications, setApplications] = useState([]);
  const [history, setHistory] = useState(() => loadHistory());
  const [toast, setToast] = useState(null);
  const [view, setView] = useState('agent');
  const [audit, setAudit] = useState(null);
  const runRef = useRef(null);

  useEffect(() => {
    health().catch((e) => {
      showToast(`Backend unreachable: ${e.message}`, 'error');
    });
    const active = loadActiveRun();
    if (active && active.runId) resumeRun(active);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function showToast(message, kind = 'info', ms) {
    setToast({ message, kind, ms, ts: Date.now() });
  }

  function resetRunState() {
    setRunning(true);
    setEvents([]);
    setResult(null);
    setMatches([]);
    setApplications([]);
    setView('agent');
  }

  function applyResult(res, p) {
    setResult(res);
    const m = res.matches || [];
    const a = res.applications || res.application_records || [];
    setMatches(m);
    setApplications(a);
    clearActiveRun();
    if (res.status === 'cancelled') {
      setRunning(false);
      showToast('Run cancelled - agent stopped');
      return;
    }
    markSeen(m);
    const historyEntry = {
      ts: Date.now(),
      filename: (p && p.filename) || 'resume',
      prefs,
      status: res.status || 'completed',
      result: res,
    };
    pushHistory(historyEntry);
    setHistory(loadHistory());
    if (res.status === 'error' || (res.errors && res.errors.length > 0)) {
      showToast((res.detail || (res.errors && res.errors[0])) || 'Run finished with errors', 'error', 6000);
    } else {
      showToast(`Run complete - ${m.length} matches, ${a.length} applications`);
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
      setAudit(parsed.audit || { health: 0, findings: [] });
      showToast('Résumé parsed, but it could be improved before the run', 'warn', 7000);
      return;
    }
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
      const started = await startPipeline(p.id, { seed: Math.floor(Math.random() * 1000), seen });
      runId = started.run_id;
      if (!runId) throw new Error('Pipeline did not return a run_id');
      runRef.current = runId;
      saveActiveRun({
        runId,
        profile: { id: p.id, filename: p.filename, target_roles: p.target_roles },
      });
      showToast('Agent run started');
      await streamRun(runId, p);
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
          const badge = v.key === 'results' ? matchCount : 0;
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
                    Drop in a résumé and Hireflow takes it from there - parsing, auditing, searching,
                    ranking and tailoring. You only approve.
                  </p>
                  <M3eButton
                    variant="filled"
                    className="runbtn"
                    disabled={!profile || running}
                    onClick={() => handleRun()}
                  >
                    {running && <M3eIcon name="progress_activity" size={18} className="spin" />}
                    {!running && <M3eIcon name="play_arrow" size={18} />}
                    {running ? 'Running…' : profile ? 'Run the agent' : 'Upload a résumé to start'}
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
                    {running ? 'agent still running…' : matchCount === 0 ? 'run the agent to see matches' : `${matchCount} matches from the live pipeline`}
                  </div>
                </div>
              </div>
              <MatchesList matches={matches} applications={applications} drafts={result?.drafts || {}} onError={(e) => showToast(e.message, 'error', 6000)} />
            </section>
          </div>
        </main>
      )}

      {view === 'history' && (
        <main>
          <div className="wrap">
            <HistoryTab history={history} onClear={handleClearHistory} />
          </div>
        </main>
      )}

      <footer>
        <span>Created by ar-Raqmi and Izaaz</span>
      </footer>

      <PrefsModal open={prefsOpen} initial={prefs} onSave={handlePrefsSave} onSkip={handlePrefsSkip} onClose={() => setPrefsOpen(false)} />
      <ResumeAuditModal open={!!audit} audit={audit} onRun={handleRunAnyway} onClose={() => setAudit(null)} />
      <Toast toast={toast} />
    </div>
  );
}
