import React from 'react';
import { createRoot } from 'react-dom/client';
import { M3eTheme } from '@m3e/react/theme';
import App from './App.jsx';
import './index.css';

createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <M3eTheme color="#8F4100" scheme="light" motion="expressive">
      <App />
    </M3eTheme>
  </React.StrictMode>,
);
