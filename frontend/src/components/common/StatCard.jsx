import React from 'react';
import { cn } from '../../lib/utils';

export function StatCard({ label, value, sublabel, icon: Icon, tone = 'blue', loading }) {
  const tones = {
    blue: 'bg-blue-50 text-blue-600',
    green: 'bg-emerald-50 text-emerald-600',
    amber: 'bg-amber-50 text-amber-600',
    red: 'bg-red-50 text-red-600',
    purple: 'bg-purple-50 text-purple-600',
    indigo: 'bg-indigo-50 text-indigo-600',
  };
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-center justify-between">
        <p className="text-sm font-medium text-slate-500">{label}</p>
        {Icon ? (
          <span className={cn('rounded-lg p-2', tones[tone] || tones.blue)}>
            <Icon className="h-4 w-4" />
          </span>
        ) : null}
      </div>
      <p className="mt-3 text-2xl font-semibold tracking-tight text-slate-900">
        {loading ? <span className="inline-block h-7 w-20 animate-pulse rounded bg-slate-200" /> : value}
      </p>
      {sublabel ? <p className="mt-1 text-xs text-slate-500">{sublabel}</p> : null}
    </div>
  );
}
