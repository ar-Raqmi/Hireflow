import { useEffect } from 'react';
import { M3eSnackbar } from '@m3e/react/snackbar';

// Toast — bottom notification. Auto-dismisses after `ms`; message comes from
// app state (errors from the API or success confirmations). Presented via the
// M3E snackbar (imperative M3eSnackbar.open).
export default function Toast({ toast }) {
  useEffect(() => {
    if (!toast) return;
    M3eSnackbar.open(toast.message, { duration: toast.ms || 3500 });
    return () => M3eSnackbar.dismiss();
  }, [toast]);

  return null;
}