import React from 'react';
import { createRoot } from 'react-dom/client';
import { M3eTheme } from '@m3e/react/theme';
import App from './App.jsx';
import './index.css';

// Hireflow's ember brand color (#8F4100) is the Material 3 primary. M3eTheme
// derives the full dynamic palette (primary/secondary/tertiary + containers)
// from it and applies it to every descendant M3E component, so the whole app
// is correctly colored with one value. "expressive" motion is the M3E animated
// feel.
createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <M3eTheme color="#8F4100" scheme="light" motion="expressive">
      <App />
    </M3eTheme>
  </React.StrictMode>,
);