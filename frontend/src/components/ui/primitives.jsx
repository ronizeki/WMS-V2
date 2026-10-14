import React from 'react';
import { cn } from '../../lib/utils';

/**
 * A minimal, dependency-free UI primitive set styled with Tailwind.
 * Kept intentionally small so every module can share the same look & feel.
 */

export function Spinner({ className }) {
  return (
    <span
      className={cn(
        'inline-block h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent',
        className
      )}
      role="status"
      aria-label="loading"
    />
  );
}

export function Badge({ tone = 'slate', className, children, ...props }) {
  const tones = {
    slate: 'bg-slate-100 text-slate-700 ring-slate-200',
    blue: 'bg-blue-50 text-blue-700 ring-blue-200',
    green: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
    amber: 'bg-amber-50 text-amber-700 ring-amber-200',
    red: 'bg-red-50 text-red-700 ring-red-200',
    indigo: 'bg-indigo-50 text-indigo-700 ring-indigo-200',
    purple: 'bg-purple-50 text-purple-700 ring-purple-200',
  };
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset',
        tones[tone] || tones.slate,
        className
      )}
      {...props}
    >
      {children}
    </span>
  );
}

export function StatusBadge({ value, tones, labels }) {
  if (value === undefined || value === null || value === '') {
    return <span className="text-slate-400">—</span>;
  }
  const tone = (tones || {})[value] || 'slate';
  const label = (labels || {})[value] || String(value).replace(/[_-]/g, ' ');
  return <Badge tone={tone}>{label.charAt(0).toUpperCase() + label.slice(1)}</Badge>;
}

export function Skeleton({ className }) {
  return <div className={cn('animate-pulse rounded-md bg-slate-200', className)} />;
}
