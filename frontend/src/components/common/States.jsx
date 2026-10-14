import React from 'react';
import { AlertCircle, Inbox, RefreshCw } from 'lucide-react';
import { Button } from '../ui/button';
import { Spinner } from '../ui/primitives';

export function LoadingState({ label = 'Loading…', className = '' }) {
  return (
    <div className={`flex flex-col items-center justify-center gap-3 py-16 text-slate-500 ${className}`}>
      <Spinner className="h-6 w-6 text-blue-600" />
      <p className="text-sm">{label}</p>
    </div>
  );
}

export function EmptyState({ title = 'Nothing here yet', message, icon: Icon = Inbox, action }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-16 text-center">
      <div className="rounded-full bg-slate-100 p-3">
        <Icon className="h-6 w-6 text-slate-400" />
      </div>
      <div>
        <p className="font-medium text-slate-700">{title}</p>
        {message ? <p className="mt-1 max-w-md text-sm text-slate-500">{message}</p> : null}
      </div>
      {action}
    </div>
  );
}

export function ErrorState({ error, onRetry }) {
  const message = error?.message || 'Something went wrong while loading this data.';
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-16 text-center">
      <div className="rounded-full bg-red-50 p-3">
        <AlertCircle className="h-6 w-6 text-red-500" />
      </div>
      <div>
        <p className="font-medium text-slate-700">Could not load data</p>
        <p className="mt-1 max-w-md text-sm text-slate-500">{message}</p>
      </div>
      {onRetry ? (
        <Button variant="outline" size="sm" onClick={onRetry}>
          <RefreshCw className="mr-2 h-4 w-4" /> Try again
        </Button>
      ) : null}
    </div>
  );
}
