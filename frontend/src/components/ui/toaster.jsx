import React, { createContext, useCallback, useContext, useMemo, useState } from 'react';
import { AlertTriangle, CheckCircle2, Info, X, XCircle } from 'lucide-react';
import { cn } from '../../lib/utils';

const ToastContext = createContext(null);

const VARIANTS = {
  success: { icon: CheckCircle2, className: 'border-emerald-200 bg-emerald-50 text-emerald-800', iconClass: 'text-emerald-500' },
  error: { icon: XCircle, className: 'border-red-200 bg-red-50 text-red-800', iconClass: 'text-red-500' },
  warning: { icon: AlertTriangle, className: 'border-amber-200 bg-amber-50 text-amber-800', iconClass: 'text-amber-500' },
  info: { icon: Info, className: 'border-blue-200 bg-blue-50 text-blue-800', iconClass: 'text-blue-500' },
};

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);

  const dismiss = useCallback((id) => {
    setToasts((list) => list.filter((t) => t.id !== id));
  }, []);

  const toast = useCallback(
    ({ title, description, variant = 'info', duration = 4000 }) => {
      const id = Math.random().toString(36).slice(2);
      setToasts((list) => [...list, { id, title, description, variant }]);
      if (duration) setTimeout(() => dismiss(id), duration);
      return id;
    },
    [dismiss]
  );

  const value = useMemo(
    () => ({
      toast,
      success: (title, description) => toast({ title, description, variant: 'success' }),
      error: (title, description) => toast({ title, description, variant: 'error', duration: 6000 }),
      info: (title, description) => toast({ title, description, variant: 'info' }),
      warning: (title, description) => toast({ title, description, variant: 'warning' }),
      dismiss,
    }),
    [toast, dismiss]
  );

  return (
    <ToastContext.Provider value={value}>
      {children}
      <Toaster toasts={toasts} onDismiss={dismiss} />
    </ToastContext.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error('useToast must be used within a ToastProvider');
  return ctx;
}

export function Toaster({ toasts = [], onDismiss = () => {} }) {
  if (!toasts.length) return null;
  return (
    <div className="pointer-events-none fixed bottom-4 right-4 z-[100] flex w-full max-w-sm flex-col gap-2">
      {toasts.map((t) => {
        const config = VARIANTS[t.variant] || VARIANTS.info;
        const Icon = config.icon;
        return (
          <div
            key={t.id}
            className={cn(
              'pointer-events-auto flex items-start gap-3 rounded-lg border px-4 py-3 shadow-lg',
              config.className
            )}
            role="status"
          >
            <Icon className={cn('mt-0.5 h-5 w-5 shrink-0', config.iconClass)} />
            <div className="flex-1 text-sm">
              <p className="font-medium">{t.title}</p>
              {t.description ? <p className="mt-0.5 opacity-90">{t.description}</p> : null}
            </div>
            <button type="button" onClick={() => onDismiss(t.id)} className="opacity-60 hover:opacity-100">
              <X className="h-4 w-4" />
            </button>
          </div>
        );
      })}
    </div>
  );
}
