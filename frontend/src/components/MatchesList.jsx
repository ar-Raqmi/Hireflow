import { useState } from 'react';
import { approveApplication } from '../api.js';
import ScoreDial from './ScoreDial.jsx';
import Icon from './Icon.jsx';

// MatchesList — renders the ranked matches from the API `done` payload.
// Each card shows the real score, title, company, location, source, post_url
// and reasons. The Approve button submits to the sandbox ATS via /approve.
export default function MatchesList({ matches = [], applications = [], onApproved, onError }) {
  const [pending, setPending] = useState({});
  const [submitted, setSubmitted] = useState({});

  // Map job_id -> application for status lookup + approve (matches carry job_id).
  const appByJob = {};
  for (const app of applications) if (app.job_id) appByJob[app.job_id] = app;

  async function handleApprove(match) {
    const app = appByJob[match.job_id];
    const appId = match.application_id || (app && app.id);
    if (!appId) {
      onError?.(new Error('No application for this match — nothing to approve.'));
      return;
    }
    setPending((p) => ({ ...p, [appId]: true }));
    try {
      const res = await approveApplication(appId);
      setSubmitted((s) => ({ ...s, [appId]: res }));
      onApproved?.(res);
    } catch (err) {
      onError?.(err);
    } finally {
      setPending((p) => ({ ...p, [appId]: false }));
    }
  }

  if (!matches || matches.length === 0) {
    return (
      <div className="nores on">
        <span>No ranked matches yet — run the agent first.</span>
      </div>
    );
  }

  return (
    <div className="joblist">
      {matches.map((m, i) => {
        const app = appByJob[m.job_id];
        const appId = m.application_id || (app && app.id);
        const done = submitted[appId] || (app && (app.status === 'submitted' || app.ats_confirmation));
        const score = Number(m.score) || 0;
        return (
          <div className="job-wrap in" key={appId || i}>
            <div className={`job ${score >= 80 ? 'featured' : ''}`} style={{ '--d': `${i * 60}ms` }}>
              <div className="score-col">
                <ScoreDial score={score} />
              </div>
              <div className="main">
                <div className="eyebrow-sm">
                  {m.source || 'source'} · rank {m.rank ?? i + 1}
                </div>
                <h3>{m.title || 'Untitled role'}</h3>
                <div className="meta">
                  {m.company || '—'} {m.location ? `· ${m.location}` : ''}
                </div>
                <div className="jmeta">
                  {m.post_url && (
                    <span>
                      <Icon name="link" size={16} />
                      <a href={m.post_url} target="_blank" rel="noreferrer">posting</a>
                    </span>
                  )}
                  {m.posted_at && <span>· {m.posted_at}</span>}
                </div>
                {m.reasons && m.reasons.length > 0 && (
                  <div className="jtake">
                    {m.reasons.slice(0, 3).map((r, j) => (
                      <div key={j}>— {r}</div>
                    ))}
                  </div>
                )}
                {m.research && m.research.summary && (
                  <div className="research"><Icon name="account_balance" size={14} /> {m.research.summary}</div>
                )}
              </div>
              <div className="act">
                {done ? (
                  <button type="button" className="appliedchip" disabled>
                    <Icon name="check_circle" size={18} />
                    {submitted[appId]?.ats_confirmation || (app && app.ats_confirmation) || 'submitted'}
                  </button>
                ) : (
                  <button
                    type="button"
                    className="filled applybtn"
                    disabled={Boolean(pending[appId]) || !appId}
                    onClick={() => handleApprove(m)}
                  >
                    {pending[appId] ? 'Submitting…' : 'Approve & submit'}
                  </button>
                )}
                <div className="hint">human approval → sandbox ATS</div>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}