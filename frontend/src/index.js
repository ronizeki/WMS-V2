import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';
import App from './App';
import reportWebVitals from './reportWebVitals';
import * as serviceWorkerRegistration from './serviceWorkerRegistration';

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);

// Register the service worker for offline app-shell support (production only).
if (process.env.REACT_APP_ENABLE_PWA !== 'false') {
  serviceWorkerRegistration.register({
    onSuccess: () => console.log('StockPilot WMS is ready for offline use.'),
    onUpdate: (registration) => {
      if (registration && registration.waiting) {
        registration.waiting.postMessage({ type: 'SKIP_WAITING' });
      }
    },
  });
}

reportWebVitals();
