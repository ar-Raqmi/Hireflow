import { useEffect } from 'react';
import { M3eSnackbar } from '@m3e/react/snackbar';

export default function Toast({ toast }) {
  useEffect(() => {
    if (!toast) return;
    M3eSnackbar.open(toast.message, { duration: toast.ms || 3500 });
    return () => M3eSnackbar.dismiss();
  }, [toast]);

  return null;
}
