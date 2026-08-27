import { useMemo, useState } from 'react';
import { M3eButton } from '@m3e/react/button';
import { M3eCircularProgressIndicator } from '@m3e/react/progress-indicator';
import { M3eSelect } from '@m3e/react/select';
import { M3eOption } from '@m3e/react/option';
import { M3eFilterChip, M3eFilterChipSet } from '@m3e/react/chips';
import M3eIcon from './M3eIcon.jsx';
import { mdToHtml } from '../lib/md.js';

const SORTS = [
  { key: 'best', label: 'Best fit' },
  { key: 'score-asc', label: 'Score: low → high' },
  { key: 'company', label: 'Company A–Z' },
  { key: 'date-new', label: 'Newest first' },
  { key: 'date-old', label: 'Oldest first' },
];

function excerpt(text, max = 220) {
  if (!text) return '';
  const plain = String(text)
    .replace(/[#>*_`~\-\[\]()!]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
  return plain.length > max ? `${plain.slice(0, max).trim()}…` : plain;
}

function sortMatches(matches, sort) {
  const out = [...matches];
  const dateOf = (m) => (m.posted_at ? new Date(m.posted_at).getTime() : 0);
  switch (sort) {
    case 'score-asc':
      return out.sort((a, b) => (Number(a.score) || 0) - (Number(b.score) || 0));
    case 'company':
      return out.sort((a, b) => (a.company || '').localeCompare(b.company || ''));
    case 'date-new':
      return out.sort((a, b) => dateOf(b) - dateOf(a));
    case 'date-old':
      return out.sort((a, b) => dateOf(a) - dateOf(b));
    default:
      return out.sort((a, b) => (Number(b.score) || 0) - (Number(a.score) || 0));
  }
}

export default function MatchesList({ matches = [], applications = [], drafts = {}, onError }) {
  const [sort, setSort] = useState('best');
  const [sources, setSources] = useState(null); // null = all
  const [draftsOnly, setDraftsOnly] = useState(false);
  const [expanded, setExpanded] = useState({}); // job_id -> { detail, draft }

  const appByJob = useMemo(() => {
    const map = {};
    for (const app of applications) if (app.job_id) map[app.job_id] = app;
    return map;
  }, [applications]);

  const allSources = useMemo(
    () => Array.from(new Set(matches.map((m) => m.source).filter(Boolean))).sort(),
    [matches],
  );

  const hasDraft = (m) => {
    const d = drafts[m.job_id];
    return Boolean(d && (d.cv || d.cover_letter));
  };

  const shown = useMemo(() => {
    return sortMatches(
      matches.filter((m) => (!sources || sources.has(m.source)) && (!draftsOnly || hasDraft(m))),
      sort,
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [matches, sort, sources, draftsOnly, drafts]);

  function toggleSource(src) {
    setSources((prev) => {
      const next = new Set(prev || allSources);
      if (next.has(src)) next.delete(src);
      else next.add(src);
      return next.size === allSources.length ? null : next;
    });
  }

  function toggleExpand(id, key) {
    setExpanded((prev) => ({ ...prev, [id]: { ...prev[id], [key]: !(prev[id] && prev[id][key]) } }));
  }

  if (!matches || matches.length === 0) {
    return <div className="nores on"><span>No matches yet - run the agent first.</span></div>;
  }

  return (
    <div className="reslist">
      <div className="filters">
        <div className="fgroup">
          <span className="flabel">Sort</span>
          <M3eSelect
            className="fsort"
            onChange={(e) => setSort(e.target.value || 'best')}
          >
            {SORTS.map((s) => (
              <M3eOption key={s.key} value={s.key} selected={sort === s.key}>{s.label}</M3eOption>
            ))}
          </M3eSelect>
        </div>

        {allSources.length > 1 && (
          <M3eFilterChipSet className="fsrc">
            {allSources.map((src) => (
              <M3eFilterChip
                key={src}
                value={src}
                selected={!sources || sources.has(src)}
                onClick={() => toggleSource(src)}
              >
                {src}
              </M3eFilterChip>
            ))}
          </M3eFilterChipSet>
        )}

        <M3eFilterChip
          className="fdraft"
          value="drafts"
          selected={draftsOnly}
          onClick={() => setDraftsOnly((v) => !v)}
        >
          Has draft
        </M3eFilterChip>
      </div>

      <div className="joblist">
        {shown.map((m, i) => {
          const rank = m.rank ?? i + 1;
          const score = Number(m.score) || 0;
          const app = appByJob[m.job_id];
          const submitted = app && (app.status === 'submitted' || app.ats_confirmation);
          const draft = drafts[m.job_id];
          const exp = expanded[m.job_id] || {};
          const detailBody = (
            <>
              {m.reasons && m.reasons.length > 0 && (
                <div className="jtake">
                  {m.reasons.map((r, j) => (
                    <div key={j}>- {r}</div>
                  ))}
                </div>
              )}
              {m.research && m.research.summary && (
                <div className="research">
                  <M3eIcon name="account_balance" size={15} />
                  <span>{excerpt(m.research.summary)}</span>
                </div>
              )}
            </>
          );
          return (
            <div className="job-wrap in" key={m.job_id || i}>
              <div className={`job ${score >= 80 ? 'featured' : ''}`} style={{ '--d': `${i * 60}ms` }}>
                <div className="score-cell">
                  <div className="score-ring">
                    <M3eCircularProgressIndicator value={Math.round(score)} max={100}>
                      <span className="score-num">{Math.round(score)}</span>
                    </M3eCircularProgressIndicator>
                  </div>
                </div>

                <div className="main">
                  <div className="eyebrow-sm">
                    rank {rank}
                    {submitted && <span className="sub-badge"><M3eIcon name="check_circle" size={13} /> submitted</span>}
                    {hasDraft(m) && <span className="dr-badge"><M3eIcon name="description" size={13} /> drafted</span>}
                  </div>
                  <h3>{m.title || 'Untitled role'}</h3>
                  <div className="meta">
                    {m.company || '-'} {m.location ? `· ${m.location}` : ''}
                  </div>
                  <div className="jmeta">
                    {m.post_url && (
                      <span>
                        <M3eIcon name="link" size={16} />
                        <a href={m.post_url} target="_blank" rel="noreferrer">posting</a>
                      </span>
                    )}
                    {m.posted_at && <span>· {m.posted_at}</span>}
                  </div>

                  <div className={`detail ${exp.detail ? 'open' : ''}`}>
                    {detailBody}
                  </div>
                  {(m.reasons?.length > 0 || m.research?.summary) && (
                    <M3eButton variant="text" className="morebtn" onClick={() => toggleExpand(m.job_id, 'detail')}>
                      <M3eIcon name={exp.detail ? 'expand_less' : 'expand_more'} size={18} />
                      {exp.detail ? 'Show less' : 'Show more'}
                    </M3eButton>
                  )}

                  {hasDraft(m) && exp.draft && (
                    <div className="draftpanel">
                      {draft.cv && (
                        <div className="draft-block">
                          <div className="draft-h"><M3eIcon name="description" size={16} /> CV</div>
                          <div className="draft-body" dangerouslySetInnerHTML={{ __html: mdToHtml(draft.cv) }} />
                        </div>
                      )}
                      {draft.cover_letter && (
                        <div className="draft-block">
                          <div className="draft-h"><M3eIcon name="mail" size={16} /> Cover letter</div>
                          <div className="draft-body" dangerouslySetInnerHTML={{ __html: mdToHtml(draft.cover_letter) }} />
                        </div>
                      )}
                    </div>
                  )}
                </div>

                <div className="act">
                  {m.post_url && (
                    <M3eButton
                      variant="tonal"
                      className="openbtn"
                      onClick={() => window.open(m.post_url, '_blank', 'noreferrer')}
                    >
                      <M3eIcon name="open_in_new" size={18} /> Open Link
                    </M3eButton>
                  )}
                  {hasDraft(m) && (
                    <M3eButton
                      variant="filled"
                      className="draftbtn"
                      onClick={() => toggleExpand(m.job_id, 'draft')}
                    >
                      <M3eIcon name={exp.draft ? 'expand_less' : 'description'} size={18} />
                      {exp.draft ? 'Close Draft' : 'View Draft'}
                    </M3eButton>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
