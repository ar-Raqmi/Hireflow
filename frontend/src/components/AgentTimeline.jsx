import { M3eLinearProgressIndicator } from '@m3e/react/progress-indicator';
import { M3eButton } from '@m3e/react/button';
import M3eIcon from './M3eIcon.jsx';

const STAGE_META = {
  parse: { icon: 'description', title: 'Parsing résumé' },
  audit: { icon: 'fact_check', title: 'Auditing résumé' },
  search: { icon: 'travel_explore', title: 'Searching job sources' },
  match: { icon: 'tune', title: 'Scoring fit' },
  career: { icon: 'corporate_fare', title: 'Probing career pages' },
  research: { icon: 'account_balance', title: 'Researching companies' },
  prepare: { icon: 'edit_note', title: 'Drafting application' },
  approve: { icon: 'how_to_reg', title: 'Awaiting approval' },
};

export default function AgentTimeline({ events = [], running = false, onCancel }) {
  const stages = Object.keys(STAGE_META);
  const seenSet = new Set(events.filter((e) => e && e.stage).map((e) => e.stage));

  const reachedIdx = stages.reduce(
    (acc, s, i) => (seenSet.has(s) ? i : acc),
    -1,
  );
  let furthest = -1;
  stages.forEach((s, i) => { if (seenSet.has(s) && i > furthest) furthest = i; });

  return (
    <section className="console" aria-label="Agent timeline">
      <div className="con-head">
        <div className="con-title">
          <M3eIcon name="monitoring" />Agent timeline
        </div>
        <span className={`phase-chip ${running ? 'live' : ''}`}>{running ? 'running' : 'idle'}</span>
        {running && onCancel && (
          <M3eButton className="tl-cancel" variant="tonal" size="small" onClick={onCancel}>
            <M3eIcon name="close" size={16} />Cancel
          </M3eButton>
        )}
      </div>

      <div className="segbar">
        {stages.map((s, i) => (
          <div
            key={s}
            className={`seg ${i <= furthest ? 'done' : ''} ${i === furthest + 1 && running ? 'active' : ''}`}
          />
        ))}
      </div>
      {running && <M3eLinearProgressIndicator className="con-progress" mode="indeterminate" variant="wavy" />}

      <ol className="tl">
        {stages.map((s, i) => {
          const meta = STAGE_META[s];
          const reached = i <= furthest;
          const isActive = i === furthest && running;
          const state = reached ? (isActive ? 'active' : 'done') : 'pending';
          const detail = events.filter((e) => e.stage === s).map((e) => e.detail).filter(Boolean);
          const isFailed = state === 'done' && events.some((e) => e.stage === s && /error|fail/i.test(e.detail || ''));
          return (
            <li
              key={s}
              className="ck"
              data-state={isFailed ? 'failed' : state}
              data-line={reachedIdx > i ? '1' : '0'}
              data-reach="0"
            >
              <div className="ck-rail">
                <div className="ck-node">
                  <M3eIcon name={meta.icon} size={20} />
                </div>
                <div className="ck-line"><i /></div>
              </div>
              <div className="ck-main">
                <div className="ck-head">
                  <div className="ck-tt">
                    <span className="ck-num">0{i + 1}</span>
                    <span className="ck-title">{meta.title}</span>
                  </div>
                </div>
                {detail.length > 0 && (
                  <div className="ck-status">
                    <span className="ck-detail">{detail[detail.length - 1]}</span>
                  </div>
                )}
                {detail.length > 1 && (
                  <div className="ck-feed">
                    <div className="fls">
                      {detail.map((d, j) => (
                        <div className="fl" key={j}>
                          <span className="ts">{d}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
