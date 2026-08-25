import { useState } from 'react';
import Icon from './Icon.jsx';

const WORK_OPTIONS = [
  { value: 'remote', label: 'Remote', sub: 'work from anywhere' },
  { value: 'hybrid', label: 'Hybrid', sub: 'mix of office + remote' },
  { value: 'onsite', label: 'Onsite', sub: 'at the office' },
  { value: 'any', label: 'Any', sub: 'no preference' },
];

// PrefsModal — work-type + locations + target roles. Skippable ("Any").
// Saved to localStorage; used as the /upload + /pipeline/run prefs.
export default function PrefsModal({ open, initial, onSave, onSkip }) {
  const [workType, setWorkType] = useState((initial && initial.work_type) || 'any');
  const [locations, setLocations] = useState((initial && initial.locations) || []);
  const [locInput, setLocInput] = useState('');
  const [roles, setRoles] = useState((initial && initial.target_roles) || []);
  const [roleInput, setRoleInput] = useState('');

  if (!open) return null;

  function addChip(list, setList, value) {
    const v = value.trim();
    if (v && !list.includes(v)) setList([...list, v]);
  }

  return (
    <div className="scrim on" onClick={onSkip}>
      <div
        className="modal on pfmodal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="pfTitle"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="pf-eyebrow">Before the agent runs</div>
        <h3 id="pfTitle">Tell Hireflow how to work</h3>
        <p className="pf-sub">
          These preferences shape the search. You can skip — the agent will fall back to your résumé.
        </p>

        <div className="pf-q">Work type</div>
        <div className="pfopts">
          {WORK_OPTIONS.map((opt) => (
            <button
              type="button"
              key={opt.value}
              className={`popt ${workType === opt.value ? 'sel' : ''}`}
              onClick={() => setWorkType(opt.value)}
            >
              <Icon name={workType === opt.value ? 'radio_button_checked' : 'radio_button_unchecked'} size={20} />
              <span>
                {opt.label}
                <span className="po-sub">{opt.sub}</span>
              </span>
            </button>
          ))}
        </div>

        <div className="pf-q">Preferred locations</div>
        <div className="plocs">
          {locations.map((loc, i) => (
            <span className="ploc" key={`${loc}-${i}`}>
              {loc}
              <button
                type="button"
                aria-label={`Remove ${loc}`}
                onClick={() => setLocations(locations.filter((_, j) => j !== i))}
              >
                <Icon name="close" size={14} />
              </button>
            </span>
          ))}
        </div>
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
          <button
            type="button"
            className="txtbtn"
            onClick={() => {
              addChip(locations, setLocations, locInput);
              setLocInput('');
            }}
          >
            Add
          </button>
        </div>

        <div className="pf-q">Target roles</div>
        <div className="plocs">
          {roles.map((role, i) => (
            <span className="ploc" key={`${role}-${i}`}>
              {role}
              <button
                type="button"
                aria-label={`Remove ${role}`}
                onClick={() => setRoles(roles.filter((_, j) => j !== i))}
              >
                <Icon name="close" size={14} />
              </button>
            </span>
          ))}
        </div>
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
          <button
            type="button"
            className="txtbtn"
            onClick={() => {
              addChip(roles, setRoles, roleInput);
              setRoleInput('');
            }}
          >
            Add
          </button>
        </div>

        <div className="pf-foot">
          <button type="button" className="txtbtn pf-back" onClick={onSkip}>
            Skip for now
          </button>
          <button
            type="button"
            className="filled"
            onClick={() => onSave({ work_type: workType, locations, target_roles: roles })}
          >
            Save preferences
          </button>
        </div>
      </div>
    </div>
  );
}