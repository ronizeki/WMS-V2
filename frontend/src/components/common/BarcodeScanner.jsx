import React, { useEffect, useRef, useState } from 'react';
import { Camera, CameraOff, Keyboard } from 'lucide-react';
import { Button } from '../ui/button';
import { Field, Input } from '../ui/form';

/**
 * Barcode scanner with a mandatory manual fallback.
 * Uses the native BarcodeDetector API when available (Chrome/Android),
 * otherwise degrades to manual SKU/barcode entry — never blocks the workflow.
 */
export function BarcodeScanner({ onDetected, autoStart = true }) {
  const videoRef = useRef(null);
  const streamRef = useRef(null);
  const rafRef = useRef(null);
  const [scanning, setScanning] = useState(false);
  const [error, setError] = useState(null);
  const [manual, setManual] = useState('');
  const supported =
    typeof window !== 'undefined' &&
    'BarcodeDetector' in window &&
    typeof navigator !== 'undefined' &&
    navigator.mediaDevices?.getUserMedia;

  const stop = React.useCallback(() => {
    if (rafRef.current) cancelAnimationFrame(rafRef.current);
    rafRef.current = null;
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
    setScanning(false);
  }, []);

  const start = React.useCallback(async () => {
    setError(null);
    if (!supported) {
      setError('Camera scanning is not supported in this browser. Use manual entry below.');
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: { ideal: 'environment' } },
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
      setScanning(true);
      const detector = new window.BarcodeDetector();
      const tick = async () => {
        if (!videoRef.current || !streamRef.current) return;
        try {
          const codes = await detector.detect(videoRef.current);
          if (codes && codes.length) {
            const value = codes[0].rawValue;
            stop();
            onDetected?.(value);
            return;
          }
        } catch (e) {
          /* detection errors are non-fatal */
        }
        rafRef.current = requestAnimationFrame(tick);
      };
      rafRef.current = requestAnimationFrame(tick);
    } catch (e) {
      setError('Unable to access the camera. Check permissions or use manual entry.');
      setScanning(false);
    }
  }, [supported, onDetected, stop]);

  useEffect(() => {
    if (autoStart) start();
    return () => stop();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const submitManual = (event) => {
    event.preventDefault();
    const value = manual.trim();
    if (!value) return;
    setManual('');
    onDetected?.(value);
  };

  return (
    <div className="space-y-4">
      <div className="relative overflow-hidden rounded-lg border border-slate-200 bg-slate-900">
        <video ref={videoRef} className="h-56 w-full object-cover" muted playsInline />
        {!scanning ? (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 text-slate-300">
            <CameraOff className="h-8 w-8" />
            <p className="text-sm">Camera is off</p>
          </div>
        ) : (
          <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
            <div className="h-32 w-56 rounded-lg border-2 border-white/80 shadow-[0_0_0_9999px_rgba(15,23,42,0.45)]" />
          </div>
        )}
      </div>

      {error ? <p className="text-sm text-amber-600">{error}</p> : null}

      <div className="flex gap-2">
        {scanning ? (
          <Button variant="outline" type="button" onClick={stop} className="flex-1">
            <CameraOff className="mr-2 h-4 w-4" /> Stop camera
          </Button>
        ) : (
          <Button type="button" onClick={start} className="flex-1" disabled={!supported}>
            <Camera className="mr-2 h-4 w-4" /> Start camera
          </Button>
        )}
      </div>

      <form onSubmit={submitManual} className="space-y-2 border-t border-slate-200 pt-4">
        <Field label="Manual entry" hint="Type or paste a barcode / SKU and press Enter.">
          <div className="flex gap-2">
            <div className="relative flex-1">
              <Keyboard className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
              <Input
                autoFocus={!supported}
                value={manual}
                onChange={(e) => setManual(e.target.value)}
                placeholder="e.g. 8991002100012"
                className="pl-9"
              />
            </div>
            <Button type="submit">Look up</Button>
          </div>
        </Field>
      </form>
    </div>
  );
}

export default BarcodeScanner;
