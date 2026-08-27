import { useEffect, useRef } from 'react';
import { M3eButton } from '@m3e/react/button';
import { M3eDialog } from '@m3e/react/dialog';
import { M3eLinearProgressIndicator } from '@m3e/react/progress-indicator';
import M3eIcon from './M3eIcon';

const SEV_LABEL = { error: 'Fix needed', warn: 'Improve', tip: 'Tip' };

export default function ResumeAuditModal({ open, audit, onRun, onClose }) {
  const dlgRef = useRef(null);

  useEffect(() => {
    if (dlgRef.current) dlgRef.current.open = Boolean(open);
  }, [open]);

  if (!audit) return null;

  const health = Number(audit.health) || 0;
  const findings = Array.isArray(audit.findings) ? audit.findings : [];

  return (
    <M3eDialog ref={dlgRef} className="pfmodal audit-modal" onClosed={onClose}>
      <div className="pf-eyebrow">Before the agent runs</div>
      <h3 id="auditTitle">Your résumé could be stronger</h3>
      <p className="pf-sub">
        The audit scored your résumé <b>{health}/100</b>. Fixing these items will
        meaningfully improve your matches before the agent starts working.
      </p>

      <div className="audit-gauge">
        <M3eLinearProgressIndicator value={health} className="audit-bar" />
        <span className="audit-health">{health}/100</span>
      </div>

      {findings.length > 0 ? (
        <ul className="audit-findings">
          {findings.slice(0, 8).map((f, i) => (
            <li key={f.id || i} className={`audit-finding sev-${f.sev || 'warn'}`}>
              <div className="af-head">
                <span className="af-sev">{SEV_LABEL[f.sev] || 'Tip'}</span>
                <span className="af-title">{f.title || 'Improvement'}</span>
              </div>
              {f.detail && <div className="af-detail">{f.detail}</div>}
            </li>
          ))}
        </ul>
      ) : (
        <p className="pf-sub">No specific findings surfaced - it just needs a polish pass.</p>
      )}

      <div className="pf-foot">
        <M3eButton variant="text" className="pf-back" onClick={onClose}>
          <M3eIcon name="edit_note" size={16} /> Reupload résumé
        </M3eButton>
        <M3eButton variant="filled" onClick={onRun}>
          Run anyway
        </M3eButton>
      </div>
    </M3eDialog>
  );
}
