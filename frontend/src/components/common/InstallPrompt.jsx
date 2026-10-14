import React, { useEffect, useState } from 'react';
import { Download, X } from 'lucide-react';
import { Button } from '../ui/button';

/** Install prompt for the PWA (Chrome/Edge/Android with beforeinstallprompt). */
export function InstallPrompt() {
  const [deferred, setDeferred] = useState(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const handler = (event) => {
      event.preventDefault();
      setDeferred(event);
      setVisible(true);
    };
    window.addEventListener('beforeinstallprompt', handler);
    const installed = () => setVisible(false);
    window.addEventListener('appinstalled', installed);
    return () => {
      window.removeEventListener('beforeinstallprompt', handler);
      window.removeEventListener('appinstalled', installed);
    };
  }, []);

  if (!visible || !deferred) return null;

  const install = async () => {
    deferred.prompt();
    await deferred.userChoice;
    setDeferred(null);
    setVisible(false);
  };

  return (
    <div className="flex items-center gap-3 border-b border-blue-200 bg-blue-50 px-4 py-2 text-sm text-blue-800">
      <Download className="h-4 w-4" />
      <span className="flex-1">Install StockPilot WMS on your device for faster access and offline support.</span>
      <Button size="sm" onClick={install}>
        Install
      </Button>
      <button type="button" onClick={() => setVisible(false)} aria-label="Dismiss">
        <X className="h-4 w-4" />
      </button>
    </div>
  );
}

export default InstallPrompt;
