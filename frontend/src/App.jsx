import { useEffect, useRef, useState } from 'react';
import { health, startPipeline, streamEvents } from './api.js';
import { loadPrefs, savePrefs, loadHistory, pushHistory, clearHistory, loadSeen, markSeen } from './storage.js';
import ResumeDrop from './components/ResumeDrop.jsx';
import PrefsModal from './components/PrefsModal.jsx';
import AgentTimeline from './components/AgentTimeline.jsx';
import MatchesList from './components/MatchesList.jsx';
import ApplicationsList from './components/ApplicationsList.jsx';
import HistoryTab from './components/HistoryTab.jsx';
import Toast from './components/Toast.jsx';
import Icon from './components/Icon.jsx';

const VIEWS = [
  { key: 'agent', label: 'Agent run', icon: 'monitoring' },
  { key: 'matches', label: 'Ranked matches', icon: 'work' },
  { key: 'applications', label: 'Applications', icon: 'description' },
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
  const [apiUp, setApiUp] = useState(null);
  const runRef = useRef(null);

  useEffect(() => {
    health()
      .then((h) => setApiUp(h && h.status === 'ok'))
      .catch((e) => {
        setApiUp(false);
        showToast(`Backend unreachable: ${e.message}`, 'error');
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function showToast(message, kind = 'info', ms) {
    setToast({ message, kind, ms, ts: Date.now() });
  }

  function handleUploaded(parsed) {
    setProfile(parsed);
    showToast(`Résumé parsed — ${parsed.skills ? parsed.skills.length : 0} skills extracted`);
  }

  function handlePrefsSave(p) {
    setPrefs(p);
    savePrefs(p);
    setPrefsOpen(false);
    showToast('Preferences saved');
  }

  function handlePrefsSkip() {
    setPrefsOpen(false);
    showToast('Using résumé defaults');
  }

  async function handleRun() {
    if (!profile) {
      showToast('Upload a résumé first', 'error');
      return;
    }
    setRunning(true);
    setEvents([]);
    setResult(null);
    setMatches([]);
    setApplications([]);
    setView('agent');

    let runId = null;
    try {
      const seen = loadSeen();
      const started = await startPipeline(profile.id, { seed: Math.floor(Math.random() * 1000), seen });
      runId = started.run_id;
      if (!runId) throw new Error('Pipeline did not return a run_id');
      runRef.current = runId;
      showToast('Agent run started');

      await streamEvents(runId, {
        onEvent: (ev) => setEvents((prev) => [...prev, ev]),
        onDone: (res) => {
          setResult(res);
          const m = res.matches || [];
          const a = res.applications || res.application_records || [];
          setMatches(m);
          setApplications(a);
          markSeen(m);
          const historyEntry = {
            ts: Date.now(),
            filename: profile.filename || 'resume',
            prefs,
            status: res.status || 'completed',
            result: res,
          };
          pushHistory(historyEntry);
          setHistory(loadHistory());
          if (res.status === 'error' || (res.errors && res.errors.length > 0)) {
            showToast((res.detail || (res.errors && res.errors[0])) || 'Run finished with errors', 'error', 6000);
          } else {
            showToast(`Run complete — ${m.length} matches, ${a.length} applications`);
          }
          setRunning(false);
        },
        onError: (err) => {
          showToast(`Stream error: ${err.message}`, 'error', 6000);
          setRunning(false);
        },
      });
    } catch (err) {
      showToast(`Failed to start run: ${err.message}`, 'error', 6000);
      setRunning(false);
    }
  }

  function handleApproved(res) {
    showToast(`Submitted — ${res.ats_confirmation}`, 'success');
  }

  function handleClearHistory() {
    clearHistory();
    setHistory([]);
    showToast('History cleared');
  }

  const matchCount = matches.length;
  const appCount = applications.length;

  return (
    <div className="app">
      <header className="topbar wrap">
        <div className="logo">
          hireflow<b>.</b>
        </div>
        <div className="top-actions">
          <span className="pill">
            <span className={`dot ${running ? 'running' : apiUp === false ? 'failed' : apiUp === true ? 'done' : ''}`} />
            {running ? 'Agent running' : apiUp === false ? 'backend offline' : apiUp === true ? 'Agent idle' : 'connecting…'}
          </span>
          <button type="button" className="pill prefschip" onClick={() => setPrefsOpen(true)}>
            <Icon name="tune" size={16} />
            {prefs.work_type}
            {prefs.locations.length > 0 ? ` · ${prefs.locations.join(', ')}` : ''}
          </button>
        </div>
      </header>

      <nav className="wrap viewtabs" aria-label="Views">
        {VIEWS.map((v) => {
          const badge = v.key === 'matches' ? matchCount : v.key === 'applications' ? appCount : 0;
          return (
            <button
              type="button"
              key={v.key}
              className={`vtab ${view === v.key ? 'active' : ''}`}
              onClick={() => setView(v.key)}
            >
              <Icon name={v.icon} size={16} />
              {v.label}
              {badge > 0 && <span className="vbadge">{badge}</span>}
            </button>
          );
        })}
      </nav>

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
                    Drop in a résumé and Hireflow takes it from there — parsing, auditing, searching,
                    ranking and tailoring. You only approve.
                  </p>
                  <button type="button" className="filled runbtn" onClick={handleRun} disabled={!profile || running}>
                    <Icon name={running ? 'progress_activity' : 'play_arrow'} size={18} />
                    {running ? 'Running…' : profile ? 'Run the agent' : 'Upload a résumé to start'}
                  </button>
                </div>
                <ResumeDrop onUploaded={handleUploaded} onError={(e) => showToast(`Upload failed: ${e.message}`, 'error', 6000)} prefs={prefs} />
              </div>
            </section>
            {profile && (
              <div className="profile-strip">
                <span className="filechip">
                  <Icon name="description" size={15} />
                  <span className="fc-name">{profile.filename || profile.id}</span>
                </span>
                {profile.target_roles && profile.target_roles.length > 0 && (
                  <span className="hchip">{profile.target_roles.slice(0, 3).join(', ')}</span>
                )}
              </div>
            )}
            <AgentTimeline events={events} running={running} />
            {result && (result.errors && result.errors.length > 0) && (
              <div className="riskbanner high">
                <Icon name="warning" size={28} />
                <div className="rb-txt">
                  <b>Backend reported {result.errors.length} error{result.errors.length === 1 ? '' : 's'}:</b>{' '}
                  {result.errors.slice(0, 4).join(' · ')}
                </div>
              </div>
            )}
          </div>
        </main>
      )}

      {view === 'matches' && (
        <main>
          <div className="wrap">
            <section className="results in">
              <div className="results-head">
                <div>
                  <h2>Ranked matches</h2>
                  <div className="res-meta">
                    {running ? 'agent still running…' : matchCount === 0 ? 'run the agent to see matches' : `${matchCount} matches from the live pipeline`}
                  </div>
                </div>
              </div>
              <MatchesList matches={matches} applications={applications} onApproved={handleApproved} onError={(e) => showToast(e.message, 'error', 6000)} />
            </section>
          </div>
        </main>
      )}

      {view === 'applications' && (
        <main>
          <div className="wrap">
            <section className="results in">
              <div className="results-head">
                <div>
                  <h2>Applications</h2>
                  <div className="res-meta">{appCount === 0 ? 'no applications yet' : `${appCount} from the live pipeline`}</div>
                </div>
              </div>
              <ApplicationsList applications={applications} />
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
        <span>hireflow — Vite + React frontend wired to the live backend</span>
        <span>every number from the API</span>
      </footer>

      <PrefsModal open={prefsOpen} initial={prefs} onSave={handlePrefsSave} onSkip={handlePrefsSkip} />
      <Toast toast={toast} />
    </div>
  );
}