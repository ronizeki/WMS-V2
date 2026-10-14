import React from 'react';
import { cn } from '../../lib/utils';

export function Tabs({ tabs, value, onChange, className }) {
  return (
    <div className={cn('flex flex-wrap gap-1 border-b border-slate-200', className)} role="tablist">
      {tabs.map((tab) => {
        const active = tab.value === value;
        const Icon = tab.icon;
        return (
          <button
            key={tab.value}
            type="button"
            role="tab"
            aria-selected={active}
            onClick={() => onChange(tab.value)}
            className={cn(
              '-mb-px inline-flex items-center gap-2 border-b-2 px-4 py-2.5 text-sm font-medium transition',
              active
                ? 'border-blue-600 text-blue-700'
                : 'border-transparent text-slate-500 hover:border-slate-300 hover:text-slate-700'
            )}
          >
            {Icon ? <Icon className="h-4 w-4" /> : null}
            {tab.label}
            {tab.count !== undefined ? (
              <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600">{tab.count}</span>
            ) : null}
          </button>
        );
      })}
    </div>
  );
}
