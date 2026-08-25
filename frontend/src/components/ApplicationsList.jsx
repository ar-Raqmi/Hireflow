import Icon from './Icon.jsx';

// ApplicationsList — flat list of applications from the backend with status,
// score, drafts, and ats_confirmation. Read-only summary of what the agent
// produced; matches are actionable in MatchesList.
export default function ApplicationsList({ applications = [] }) {
  if (!applications || applications.length === 0) {
    return <div className="nores on"><span>No applications yet.</span></div>;
  }
  return (
    <div className="joblist">
      {applications.map((app) => (
        <div className="job-wrap in" key={app.id}>
          <div className="job">
            <div className="main">
              <div className="eyebrow-sm">{app.status}</div>
              <h3>{app.title || '—'}</h3>
              <div className="meta">{app.company || '—'}</div>
              {app.human_handoff && (
                <div className="gate">
                  <div className="gate-ic"><Icon name="support_agent" size={22} /></div>
                  <div className="gate-txt"><b>Needs a human</b><p>This one involves offers / salary / counter-offers.</p></div>
                </div>
              )}
              {app.drafted && (
                <div className="jmeta">
                  <span><Icon name="description" size={16} /> CV drafted</span>
                  <span><Icon name="mail" size={16} /> cover letter</span>
                </div>
              )}
              {app.ats_confirmation && (
                <div className="applied-pill"><Icon name="check_circle" size={18} /> {app.ats_confirmation}</div>
              )}
            </div>
            <div className="act">
              <span className="hint">score {app.score ?? '—'}</span>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}