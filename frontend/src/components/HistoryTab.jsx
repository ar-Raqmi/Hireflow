import { M3eButton } from '@m3e/react/button';
import M3eIcon from './M3eIcon.jsx';

// HistoryTab — past runs from localStorage, with a Clear history button.
// Each run stores the profile filename, prefs, timestamp and the result
// payload (matches/applications/errors) from the last completed run.
export default function HistoryTab({ history = [], onClear }) {
  return (
    <section className="results in">
      <div className="results-head">
        <div>
          <h2>Run history</h2>
          <div className="res-meta">{history.length === 0 ? 'no runs yet' : `${history.length} run${history.length === 1 ? '' : 's'} saved on this device`}</div>
        </div>
        <div className="head-actions">
          {history.length > 0 && (
            <M3eButton variant="outlined" onClick={onClear}>
              <M3eIcon name="delete" />Clear history
            </M3eButton>
          )}
        </div>
      </div>

      {history.length === 0 ? (
        <div className="hempty">
          <M3eIcon name="history" size={34} />
          <b>Past runs will appear here</b>
          Upload a résumé and run the agent — every completed run lands here, saved locally on this device.
        </div>
      ) : (
        <div>
          {history.map((run, i) => (
            <div className="hcard" key={run.ts || i}>
              <div className="h-top">
                <span className="h-file">{run.filename || 'resume'}</span>
                <span className="h-time">{new Date(run.ts).toLocaleString()}</span>
              </div>
              <div className="h-chips">
                {run.prefs && run.prefs.work_type && <span className="hchip">work: {run.prefs.work_type}</span>}
                {(run.prefs && run.prefs.locations && run.prefs.locations.length > 0) && <span className="hchip">{run.prefs.locations.join(', ')}</span>}
                {run.status && <span className="hchip">{run.status}</span>}
              </div>
              <div className="h-stats">
                <span><b>{(run.result && run.result.matches ? run.result.matches.length : 0)}</b> matches</span>
                <span><b>{(run.result && run.result.applications ? run.result.applications.length : 0)}</b> applications</span>
                {(run.result && run.result.errors && run.result.errors.length > 0) && (
                  <span className="hap"><b>{run.result.errors.length}</b> errors</span>
                )}
              </div>
              {(run.result && run.result.errors && run.result.errors.length > 0) && (
                <div className="errors-note">
                  {run.result.errors.slice(0, 3).map((e, j) => <div key={j} className="fl err">— {e}</div>)}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </section>
  );
}