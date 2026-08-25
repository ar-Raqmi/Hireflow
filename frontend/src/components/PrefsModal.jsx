import { useEffect, useRef, useState } from 'react';
import { M3eButton } from '@m3e/react/button';
import { M3eDialog } from '@m3e/react/dialog';
import { M3eInputChip, M3eInputChipSet } from '@m3e/react/chips';
import { M3eSegmentedButton, M3eButtonSegment } from '@m3e/react/segmented-button';
import M3eIcon from './M3eIcon';

const WORK_OPTIONS = [
  { value: 'remote', label: 'Remote', icon: 'home_work' },
  { value: 'hybrid', label: 'Hybrid', icon: 'sync_alt' },
  { value: 'onsite', label: 'Onsite', icon: 'business_center' },
  { value: 'any', label: 'Any', icon: 'public' },
];

// PrefsModal — work-type + locations + target roles. Skippable ("Any").
// Saved to localStorage; used as the /upload + /pipeline/run prefs.
export default function PrefsModal({ open, initial, onSave, onSkip, onClose }) {
  const [workType, setWorkType] = useState((initial && initial.work_type) || 'any');
  const [locations, setLocations] = useState((initial && initial.locations) || []);
  const [locInput, setLocInput] = useState('');
  const [roles, setRoles] = useState((initial && initial.target_roles) || []);
  const [roleInput, setRoleInput] = useState('');
  const dlgRef = useRef(null);

  // M3E's native <dialog> needs to be connected to the document before
  // showModal() can run. Set `open` in an effect (post-mount) rather than as a
  // mount-time prop to avoid "not in a Document" errors.
  useEffect(() => {
    if (dlgRef.current) dlgRef.current.open = Boolean(open);
  }, [open]);

  function addChip(list, setList, value) {
    const v = value.trim();
    if (v && !list.includes(v)) setList([...list, v]);
  }

  return (
    <M3eDialog ref={dlgRef} className="pfmodal" onClosed={onClose}>
      <div className="pf-eyebrow">Before the agent runs</div>
      <h3 id="pfTitle">Tell Hireflow how to work</h3>
      <p className="pf-sub">
        These preferences shape the search. You can skip — the agent will fall back to your résumé.
      </p>

      <div className="pf-q">Work type</div>
      <M3eSegmentedButton
        onChange={(e) => {
          const seg = e.target && e.target.selected && e.target.selected[0];
          if (seg && seg.value) setWorkType(seg.value);
        }}
        className="pfopts"
      >
        {WORK_OPTIONS.map((opt) => (
          <M3eButtonSegment key={opt.value} value={opt.value} checked={workType === opt.value}>
            <M3eIcon slot="icon" name={opt.icon} />
            {opt.label}
          </M3eButtonSegment>
        ))}
      </M3eSegmentedButton>

      <div className="pf-q">Preferred locations</div>
      <M3eInputChipSet className="plocs">
        {locations.map((loc, i) => (
          <M3eInputChip
            key={`${loc}-${i}`}
            value={loc}
            removable
            removeLabel={`Remove ${loc}`}
            onRemove={() => setLocations(locations.filter((_, j) => j !== i))}
          >
            {loc}
          </M3eInputChip>
        ))}
      </M3eInputChipSet>
      <div className="pf-geo">
        <input
          placeholder="Add a city/country (e.g. Tokyo, Johor)"
          value={locInput}
          onChange={(e) => setLocInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault();
              addChip(locations, setLocations, locInput);
              setLocInput('');
            }
          }}
        />
        <M3eButton
          variant="text"
          onClick={() => {
            addChip(locations, setLocations, locInput);
            setLocInput('');
          }}
        >
          Add
        </M3eButton>
      </div>

      <div className="pf-q">Target roles</div>
      <M3eInputChipSet className="plocs">
        {roles.map((role, i) => (
          <M3eInputChip
            key={`${role}-${i}`}
            value={role}
            removable
            removeLabel={`Remove ${role}`}
            onRemove={() => setRoles(roles.filter((_, j) => j !== i))}
          >
            {role}
          </M3eInputChip>
        ))}
      </M3eInputChipSet>
      <div className="pf-geo">
        <input
          placeholder="e.g. Machine Learning Engineer"
          value={roleInput}
          onChange={(e) => setRoleInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault();
              addChip(roles, setRoles, roleInput);
              setRoleInput('');
            }
          }}
        />
        <M3eButton
          variant="text"
          onClick={() => {
            addChip(roles, setRoles, roleInput);
            setRoleInput('');
          }}
        >
          Add
        </M3eButton>
      </div>

      <div className="pf-foot">
        <M3eButton variant="text" className="pf-back" onClick={onSkip}>
          Skip for now
        </M3eButton>
        <M3eButton
          variant="filled"
          onClick={() => onSave({ work_type: workType, locations, target_roles: roles })}
        >
          Save preferences
        </M3eButton>
      </div>
    </M3eDialog>
  );
}