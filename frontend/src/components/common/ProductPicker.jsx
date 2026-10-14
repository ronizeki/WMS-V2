import React, { useEffect, useRef, useState } from 'react';
import { ScanLine, Search } from 'lucide-react';
import api from '../../lib/api';
import { useApiResource, useDebounced } from '../../hooks/useApi';
import { Button } from '../ui/button';
import { Input } from '../ui/form';
import { Modal } from '../ui/modal';
import { Spinner } from '../ui/primitives';
import { BarcodeScanner } from './BarcodeScanner';
import { useToast } from '../ui/toaster';
import { cn } from '../../lib/utils';

/**
 * Searchable product selector with an optional barcode-scan fallback.
 * Emits the full product object so callers can prefill SKU, unit and price.
 */
export function ProductPicker({ selected, onChange, placeholder = 'Select a product…', disabled, className }) {
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState('');
  const [scanOpen, setScanOpen] = useState(false);
  const ref = useRef(null);
  const debounced = useDebounced(search, 300);

  const { data, loading } = useApiResource(open ? '/products' : null, {
    search: debounced || undefined,
    page_size: 8,
  });

  useEffect(() => {
    if (!open) return undefined;
    const onClick = (event) => {
      if (ref.current && !ref.current.contains(event.target)) setOpen(false);
    };
    document.addEventListener('mousedown', onClick);
    return () => document.removeEventListener('mousedown', onClick);
  }, [open]);

  const pick = (product) => {
    onChange?.(product);
    setOpen(false);
    setSearch('');
  };

  const handleScan = async (code) => {
    try {
      const product = await api.get('/products/lookup', { code });
      onChange?.(product);
      toast.success('Product found', `${product.sku} — ${product.name}`);
      setScanOpen(false);
      setOpen(false);
    } catch (e) {
      toast.error('No match', e.status === 404 ? 'No product matches that barcode or SKU.' : e.message);
    }
  };

  return (
    <div ref={ref} className={cn('relative', className)}>
      <div className="flex gap-2">
        <button
          type="button"
          disabled={disabled}
          onClick={() => setOpen((v) => !v)}
          className={cn(
            'flex h-10 flex-1 items-center justify-between rounded-md border border-slate-300 bg-white px-3 text-left text-sm shadow-sm transition hover:border-slate-400 disabled:cursor-not-allowed disabled:bg-slate-50',
            !selected && 'text-slate-400'
          )}
        >
          <span className="truncate">
            {selected ? (
              <>
                <span className="font-medium text-slate-700">{selected.sku}</span>
                <span className="text-slate-500"> — {selected.name}</span>
              </>
            ) : (
              placeholder
            )}
          </span>
          <Search className="ml-2 h-4 w-4 shrink-0 text-slate-400" />
        </button>
        <Button type="button" variant="outline" onClick={() => setScanOpen(true)} disabled={disabled} title="Scan barcode">
          <ScanLine className="h-4 w-4" />
        </Button>
      </div>

      {open ? (
        <div className="absolute z-30 mt-1 w-full overflow-hidden rounded-lg border border-slate-200 bg-white shadow-lg">
          <div className="border-b border-slate-100 p-2">
            <Input
              autoFocus
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search by SKU, name or barcode…"
            />
          </div>
          <div className="max-h-64 overflow-y-auto">
            {loading ? (
              <div className="flex items-center gap-2 px-3 py-3 text-sm text-slate-500">
                <Spinner /> Searching…
              </div>
            ) : (data || []).length ? (
              (data || []).map((product) => (
                <button
                  key={product.id}
                  type="button"
                  onClick={() => pick(product)}
                  className="flex w-full items-center justify-between px-3 py-2 text-left text-sm hover:bg-slate-50"
                >
                  <span>
                    <span className="font-medium text-slate-700">{product.sku}</span>
                    <span className="ml-2 text-slate-500">{product.name}</span>
                  </span>
                  <span className="text-xs text-slate-400">{product.base_unit}</span>
                </button>
              ))
            ) : (
              <p className="px-3 py-3 text-sm text-slate-400">No products found.</p>
            )}
          </div>
        </div>
      ) : null}

      <Modal open={scanOpen} onClose={() => setScanOpen(false)} title="Scan barcode" size="sm">
        <BarcodeScanner onDetected={handleScan} />
      </Modal>
    </div>
  );
}

export default ProductPicker;
