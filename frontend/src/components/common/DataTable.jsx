import React from 'react';
import { Table, TBody, TD, TH, THead, TR } from '../ui/table';
import { Skeleton } from '../ui/primitives';
import { EmptyState, ErrorState } from './States';
import { Button } from '../ui/button';

export function DataTable({
  columns,
  rows,
  loading,
  error,
  onRetry,
  emptyTitle,
  emptyMessage,
  emptyAction,
  keyField = 'id',
  onRowClick,
  skeletonRows = 6,
}) {
  if (error) return <ErrorState error={error} onRetry={onRetry} />;

  if (loading && (!rows || rows.length === 0)) {
    return (
      <div className="space-y-2 p-4">
        {Array.from({ length: skeletonRows }).map((_, i) => (
          <Skeleton key={i} className="h-10 w-full" />
        ))}
      </div>
    );
  }

  if (!rows || rows.length === 0) {
    return <EmptyState title={emptyTitle} message={emptyMessage} action={emptyAction} />;
  }

  return (
    <Table>
      <THead>
        <TR className="hover:bg-transparent">
          {columns.map((col) => (
            <TH key={col.key} className={col.className} style={col.style}>
              {col.header}
            </TH>
          ))}
        </TR>
      </THead>
      <TBody>
        {rows.map((row, index) => (
          <TR
            key={row[keyField] ?? index}
            onClick={onRowClick ? () => onRowClick(row) : undefined}
            className={onRowClick ? 'cursor-pointer' : undefined}
          >
            {columns.map((col) => (
              <TD key={col.key} className={col.className} style={col.style}>
                {col.render ? col.render(row) : row[col.key]}
              </TD>
            ))}
          </TR>
        ))}
      </TBody>
    </Table>
  );
}

export function Pagination({ meta, onPageChange }) {
  if (!meta || !meta.total) return null;
  const { page = 1, page_size: pageSize = 20, total = 0, total_pages: totalPages = 1 } = meta;
  const from = (page - 1) * pageSize + 1;
  const to = Math.min(page * pageSize, total);
  return (
    <div className="flex flex-col items-center justify-between gap-3 border-t border-slate-200 px-4 py-3 text-sm text-slate-500 sm:flex-row">
      <p>
        Showing <span className="font-medium text-slate-700">{from}</span>–
        <span className="font-medium text-slate-700">{to}</span> of{' '}
        <span className="font-medium text-slate-700">{total}</span>
      </p>
      <div className="flex items-center gap-2">
        <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => onPageChange(page - 1)}>
          Previous
        </Button>
        <span className="px-2">
          Page {page} of {totalPages || 1}
        </span>
        <Button
          variant="outline"
          size="sm"
          disabled={page >= (totalPages || 1)}
          onClick={() => onPageChange(page + 1)}
        >
          Next
        </Button>
      </div>
    </div>
  );
}
