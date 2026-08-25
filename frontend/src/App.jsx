import { useEffect, useRef, useState } from 'react';
import { M3eButton } from '@m3e/react/button';
import { M3eTabs, M3eTab } from '@m3e/react/tabs';
import { health, startPipeline, streamEvents } from './api.js';
import { loadPrefs, savePrefs, loadHistory, pushHistory, clearHistory, loadSeen, markSeen } from './storage.js';
import ResumeDrop from './components/ResumeDrop.jsx';
import PrefsModal from './components/PrefsModal.jsx';
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
  const runRef = useRef(null);

  useEffect(() => {
    health().catch((e) => {
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
    handleRun(parsed);
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
    const p = override || profile;
    if (!p) {
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
      const started = await startPipeline(p.id, { seed: Math.floor(Math.random() * 1000), seen });
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
            filename: p.filename || 'resume',
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
          hireflow<b>.</b>
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
                    Drop in a résumé and Hireflow takes it from there — parsing, auditing, searching,
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
                <ResumeDrop onUploaded={handleUploaded} onError={(e) => showToast(`Upload failed: ${e.message}`, 'error', 6000)} prefs={prefs} />
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
            <AgentTimeline events={events} running={running} />
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
      <Toast toast={toast} />
    </div>
  );
}