import React from 'react';
import { cn } from '../../lib/utils';

export function Table({ className, ...props }) {
  return (
    <div className="w-full overflow-x-auto">
      <table className={cn('w-full caption-bottom text-sm', className)} {...props} />
    </div>
  );
}

export function THead({ className, ...props }) {
  return <thead className={cn('[&_tr]:border-b', className)} {...props} />;
}

export function TBody({ className, ...props }) {
  return <tbody className={cn('[&_tr:last-child]:border-0', className)} {...props} />;
}

export function TR({ className, ...props }) {
  return (
    <tr
      className={cn('border-b border-slate-100 transition-colors hover:bg-slate-50/70', className)}
      {...props}
    />
  );
}

export function TH({ className, ...props }) {
  return (
    <th
      className={cn(
        'h-11 whitespace-nowrap px-4 text-left align-middle text-xs font-semibold uppercase tracking-wide text-slate-500',
        className
      )}
      {...props}
    />
  );
}

export function TD({ className, ...props }) {
  return <td className={cn('whitespace-nowrap px-4 py-3 align-middle text-slate-700', className)} {...props} />;
}
