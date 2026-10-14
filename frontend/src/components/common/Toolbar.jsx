import React from 'react';
import { Search } from 'lucide-react';
import { Input } from '../ui/form';
import { cn } from '../../lib/utils';

export function SearchInput({ value, onChange, placeholder = 'Search…', className }) {
  return (
    <div className={cn('relative', className)}>
      <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
      <Input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="pl-9"
      />
    </div>
  );
}

export function Toolbar({ children, className }) {
  return (
    <div className={cn('flex flex-col gap-3 border-b border-slate-200 p-4 sm:flex-row sm:items-center', className)}>
      {children}
    </div>
  );
}
