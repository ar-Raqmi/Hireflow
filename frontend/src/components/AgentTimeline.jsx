import Icon from './Icon.jsx';

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

// AgentTimeline — renders the SSE live stages as a vertical timeline.
// `events` is the ordered list of {seq, stage, detail} frames streamed from
// the backend; `running` drives the "active/paused" ring states.
export default function AgentTimeline({ events = [], running = false }) {
  const stages = Object.keys(STAGE_META);
  const seen = events.filter((e) => e && e.stage).map((e) => e.stage);

  // Determine the latest stage the agent reached.
  const lastIdx = stages.reduce((acc, s, i) => (seen.includes(s) ? i : acc), -1);

  return (
    <section className="console" aria-label="Agent timeline">
      <div className="con-head">
        <div className="con-title">
          <Icon name="monitoring" />Agent timeline
        </div>
        <span className={`phase-chip ${running ? 'live' : ''}`}>{running ? 'running' : 'idle'}</span>
      </div>

      <div className="segbar">
        {stages.map((s, i) => (
          <div
            key={s}
            className={`seg ${i <= lastIdx ? 'done' : ''} ${i === lastIdx + 1 && running ? 'active' : ''}`}
          />
        ))}
      </div>

      <ol className="tl">
        {stages.map((s, i) => {
          const meta = STAGE_META[s];
          const state = i < lastIdx ? 'done' : i === lastIdx ? (running ? 'active' : 'done') : 'pending';
          const detail = events.filter((e) => e.stage === s).map((e) => e.detail).filter(Boolean);
          const isFailed = state === 'done' && i === lastIdx && events.some((e) => e.stage === s && /error|fail/i.test(e.detail || ''));
          return (
            <li
              key={s}
              className="ck"
              data-state={isFailed ? 'failed' : state}
              data-line={i < lastIdx ? '1' : '0'}
              data-reach="0"
            >
              <div className="ck-rail">
                <div className="ck-node">
                  <Icon name={meta.icon} size={20} />
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