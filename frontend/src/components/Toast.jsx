import { useEffect, useState } from 'react';
import Icon from './Icon.jsx';

// Toast — bottom notification. Auto-dismisses after `ms`; message comes from
// app state (errors from the API or success confirmations).
export default function Toast({ toast }) {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (!toast) return;
    setVisible(true);
    const t = setTimeout(() => setVisible(false), toast.ms || 3500);
    return () => clearTimeout(t);
  }, [toast]);

  if (!toast) return null;
  return (
    <div className={`toast ${visible ? 'show' : ''}`} role="status">
      <Icon name={toast.icon || (toast.kind === 'error' ? 'error' : 'auto_awesome')} size={22} />
      <span>{toast.message}</span>
      <i className="toastbar" />
    </div>
  );
}