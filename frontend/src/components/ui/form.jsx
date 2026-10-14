import React from 'react';
import { cn } from '../../lib/utils';

export const Label = React.forwardRef(({ className, children, required, ...props }, ref) => (
  <label ref={ref} className={cn('block text-sm font-medium text-slate-700', className)} {...props}>
    {children}
    {required ? <span className="ml-0.5 text-red-500">*</span> : null}
  </label>
));
Label.displayName = 'Label';

const fieldBase =
  'block w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm placeholder:text-slate-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:cursor-not-allowed disabled:bg-slate-50 disabled:text-slate-500';

export const Input = React.forwardRef(({ className, error, ...props }, ref) => (
  <input
    ref={ref}
    className={cn(fieldBase, error && 'border-red-400 focus:border-red-500 focus:ring-red-500', className)}
    {...props}
  />
));
Input.displayName = 'Input';

export const Textarea = React.forwardRef(({ className, error, rows = 3, ...props }, ref) => (
  <textarea
    ref={ref}
    rows={rows}
    className={cn(fieldBase, 'resize-y', error && 'border-red-400 focus:border-red-500 focus:ring-red-500', className)}
    {...props}
  />
));
Textarea.displayName = 'Textarea';

export const Select = React.forwardRef(({ className, error, children, ...props }, ref) => (
  <select
    ref={ref}
    className={cn(fieldBase, 'pr-8', error && 'border-red-400 focus:border-red-500 focus:ring-red-500', className)}
    {...props}
  >
    {children}
  </select>
));
Select.displayName = 'Select';

export function Checkbox({ className, label, ...props }) {
  return (
    <label className={cn('inline-flex cursor-pointer items-center gap-2 text-sm text-slate-700', className)}>
      <input
        type="checkbox"
        className="h-4 w-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500"
        {...props}
      />
      {label ? <span>{label}</span> : null}
    </label>
  );
}

export function Field({ label, required, error, hint, children, className }) {
  return (
    <div className={cn('space-y-1.5', className)}>
      {label ? <Label required={required}>{label}</Label> : null}
      {children}
      {hint && !error ? <p className="text-xs text-slate-500">{hint}</p> : null}
      {error ? <p className="text-xs text-red-600">{error}</p> : null}
    </div>
  );
}
