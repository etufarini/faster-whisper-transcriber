/*
 * main.tsx
 * Mount the native application with React lifecycle checks enabled in development.
 */
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './app/App';
import './style.css';
createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
