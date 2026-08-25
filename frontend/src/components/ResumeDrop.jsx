import { useRef, useState } from 'react';
import { M3eButton } from '@m3e/react/button';
import { M3eChip, M3eChipSet } from '@m3e/react/chips';
import { M3eCircularProgressIndicator } from '@m3e/react/progress-indicator';
import { uploadResume } from '../api.js';
import M3eIcon from './M3eIcon.jsx';

// ResumeDrop — the hero dropzone. Drag-drop or browse → uploads the file to
// the REAL /upload endpoint (via uploadResume). Shows parsed fields returned
// by the backend (skills, years, residence) once upload completes.
export default function ResumeDrop({ onUploaded, onError, prefs }) {
  const inputRef = useRef(null);
  const [dragging, setDragging] = useState(false);
  const [file, setFile] = useState(null);
  const [busy, setBusy] = useState(false);
  const [profile, setProfile] = useState(null);

  async function handleFile(f) {
    if (!f) return;
    setFile(f);
    setBusy(true);
    try {
      const parsed = await uploadResume({
        file: f,
        work_type: (prefs && prefs.work_type) || 'any',
        locations: (prefs && prefs.locations) || [],
        target_roles: (prefs && prefs.target_roles) || [],
      });
      setProfile(parsed);
      onUploaded?.(parsed);
    } catch (err) {
      onError?.(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div
      className={`dz ${dragging ? 'dragging' : ''} ${file ? 'has-file' : ''}`}
      role="button"
      tabIndex={0}
      aria-label="Drop your resume here or press Enter to browse files"
      onClick={() => inputRef.current && inputRef.current.click()}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') inputRef.current && inputRef.current.click();
      }}
      onDragOver={(e) => {
        e.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragging(false);
        const f = e.dataTransfer.files && e.dataTransfer.files[0];
        if (f) handleFile(f);
      }}
    >
      <div className="dz-inner">
        {!file && (
          <div className="dz-empty">
            <div className="dz-badge">
              <M3eIcon name="upload_file" size={36} />
            </div>
            <div className="dz-title">Drop your résumé here</div>
            <div className="dz-sub">PDF, DOCX or TXT — parsed &amp; audited by the live agent</div>
            <M3eButton variant="tonal" className="browse" onClick={(e) => { e.stopPropagation(); inputRef.current && inputRef.current.click(); }}>
              browse files
            </M3eButton>
            <div className="dz-note">uploaded to the Hireflow backend</div>
          </div>
        )}
        {file && (
          <div className="dz-file">
            <div className="file-row">
              <div className="file-ic">
                <M3eIcon name="description" size={22} />
              </div>
              <div>
                <div className="file-name">{file.name}</div>
                <div className="file-sub">{busy ? <span className="busy-row"><M3eCircularProgressIndicator size={16} /> uploading…</span> : (profile ? 'parsed & stored' : '')}</div>
              </div>
              <div className="file-btns">
                <M3eButton variant="text" onClick={(e) => { e.stopPropagation(); inputRef.current && inputRef.current.click(); }}>
                  Replace
                </M3eButton>
              </div>
            </div>
            {profile && (
              <div className="parsed-summary">
                {profile.skills && profile.skills.length > 0 && (
                  <div className="skills">
                    <M3eChipSet>
                      {profile.skills.slice(0, 8).map((s, i) => (
                        <M3eChip key={i} className="sk">{s}</M3eChip>
                      ))}
                    </M3eChipSet>
                  </div>
                )}
                <div className="parsed-meta">
                  {Number(profile.years_experience) > 0 && <span>{profile.years_experience} yrs exp</span>}
                  {profile.residence && <span>📍 {profile.residence}</span>}
                  {profile.work_type && <span>work: {profile.work_type}</span>}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
      <input
        ref={inputRef}
        type="file"
        accept=".pdf,.docx,.txt"
        style={{ display: 'none' }}
        onChange={(e) => handleFile(e.target.files && e.target.files[0])}
      />
    </div>
  );
}