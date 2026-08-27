import { useEffect, useRef } from 'react';
import { M3eButton } from '@m3e/react/button';
import { M3eDialog } from '@m3e/react/dialog';
import M3eIcon from './M3eIcon';

export default function NewJobsModal({ open, notice, onView, onClose }) {
  const dlgRef = useRef(null);

  useEffect(() => {
    if (dlgRef.current) dlgRef.current.open = Boolean(open && notice);
  }, [open, notice]);

  if (!notice) return null;

  return (
    <M3eDialog ref={dlgRef} className="pfmodal newjobs-modal" onClosed={onClose}>
      <div className="pf-eyebrow">While you were away</div>
      <h3>{notice.count} new job{notice.count === 1 ? '' : 's'} found</h3>
      <p className="pf-sub">
        The agent re-checked the job sources since your last visit and found{' '}
        <b>{notice.count}</b> new role{notice.count === 1 ? '' : 's'} that match your profile -
        ranked on top for you.
      </p>
      <div className="pf-foot">
        <M3eButton variant="outlined" onClick={onClose}>
          Later
        </M3eButton>
        <M3eButton variant="filled" onClick={onView}>
          <M3eIcon name="work" size={16} /> View new jobs
        </M3eButton>
      </div>
    </M3eDialog>
  );
}
