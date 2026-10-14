import React, { useState } from 'react';
import { Check, ClipboardCheck, Play, Plus, X } from 'lucide-react';
import api from '../lib/api';
import { useApiResource } from '../hooks/useApi';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../components/ui/toaster';
import { PageHeader } from '../components/common/PageHeader';
import { DataTable, Pagination } from '../components/common/DataTable';
import { Toolbar } from '../components/common/Toolbar';
import { Button } from '../components/ui/button';
import { Card } from '../components/ui/card';
import { Field, Input, Select, Textarea } from '../components/ui/form';
import { Modal } from '../components/ui/modal';
import { StatusBadge } from '../components/ui/primitives';
import { formatDateTime, formatQty, titleCase } from '../lib/format';
import { CYCLE_COUNT_STATUSES, STATUS_TONES } from '../lib/constants';

export default function Stocktake() {
  const { hasPermission } = useAuth();
  const toast = useToast();
  const [status, setStatus] = useState('');
  const [page, setPage] = useState(1);
  const counts = useApiResource('/cycle-counts', { status: status || undefined, page, page_size: 20 });
  const { data: warehouses } = useApiResource('/warehouses', { page_size: 100 });

  const [createOpen, setCreateOpen] = useState(false);
  const [form, setForm] = useState({ warehouse_id: '', location_id: '', count_type: 'location', notes: '' });
  const [saving, setSaving] = useState(false);
  const { data: locations } = useApiResource(form.warehouse_id ? `/warehouses/${form.warehouse_id}/locations` : null, { page_size: 200 });

  const [countTarget, setCountTarget] = useState(null);
  const [counted, setCounted] = useState({});

  const submit = async (e) => {
    e.preventDefault();
    if (!form.warehouse_id) {
      toast.error('Select a warehouse');
      return;
    }
    setSaving(true);
    try {
      const created = await api.post('/cycle-counts', {
        warehouse_id: form.warehouse_id,
        location_id: form.location_id || undefined,
        count_type: form.count_type,
        notes: form.notes || undefined,
      });
      toast.success('Cycle count created', `${(created.lines || []).length} line(s) to count`);
      setCreateOpen(false);
      counts.refetch();
    } catch (err) {
      toast.error('Could not create cycle count', err.message);
    } finally {
      setSaving(false);
    }
  };

  const action = async (count, path, message) => {
    try {
      await api.post(`/cycle-counts/${count.id}/${path}`);
      toast.success(message);
      counts.refetch();
    } catch (err) {
      toast.error('Action failed', err.message);
    }
  };

  const openCount = (count) => {
    const initial = {};
    (count.lines || []).forEach((l) => {
      initial[l.id] = l.counted_qty ?? l.system_qty;
    });
    setCounted(initial);
    setCountTarget(count);
  };

  const submitCount = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      await api.post(`/cycle-counts/${countTarget.id}/count`, {
        lines: (countTarget.lines || []).map((l) => ({
          line_id: l.id,
          counted_qty: Number(counted[l.id]) || 0,
        })),
      });
      toast.success('Count submitted', 'Awaiting approval.');
      setCountTarget(null);
      counts.refetch();
    } catch (err) {
      toast.error('Could not submit count', err.message);
    } finally {
      setSaving(false);
    }
  };

  const canWrite = hasPermission('stocktake:write');
  const canApprove = hasPermission('stocktake:approve');

  return (
    <div className="space-y-6">
      <PageHeader
        title="Stocktake"
        description="Count physical stock, capture variances and post adjustments on approval."
        actions={
          canWrite ? (
            <Button onClick={() => { setForm({ warehouse_id: warehouses?.[0]?.id || '', location_id: '', count_type: 'location', notes: '' }); setCreateOpen(true); }}>
              <Plus className="mr-2 h-4 w-4" /> New cycle count
            </Button>
          ) : null
        }
      />

      <Card>
        <Toolbar>
          <Select value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }} className="sm:w-56">
            <option value="">All statuses</option>
            {CYCLE_COUNT_STATUSES.map((s) => <option key={s} value={s}>{titleCase(s)}</option>)}
          </Select>
        </Toolbar>

        <DataTable
          columns={[
            { key: 'number', header: 'Count', render: (r) => <span className="font-medium text-slate-800">{r.number}</span> },
            { key: 'count_type', header: 'Scope', render: (r) => titleCase(r.count_type) },
            { key: 'lines', header: 'Lines', render: (r) => (r.lines || []).length },
            {
              key: 'variance',
              header: 'Variance',
              className: 'text-right',
              render: (r) => {
                const totalVariance = (r.lines || []).reduce((s, l) => s + Number(l.variance_qty || 0), 0);
                return <span className={totalVariance < 0 ? 'text-red-600' : totalVariance > 0 ? 'text-emerald-600' : ''}>{formatQty(totalVariance)}</span>;
              },
            },
            { key: 'status', header: 'Status', render: (r) => <StatusBadge value={r.status} tones={STATUS_TONES} /> },
            { key: 'created_at', header: 'Created', render: (r) => formatDateTime(r.created_at) },
            {
              key: 'actions',
              header: '',
              className: 'text-right',
              render: (r) => (
                <div className="flex justify-end gap-1">
                  {canWrite && r.status === 'draft' ? (
                    <Button size="sm" variant="outline" onClick={() => action(r, 'start', 'Counting started')}><Play className="mr-1.5 h-3.5 w-3.5" />Start</Button>
                  ) : null}
                  {canWrite && ['draft', 'in_progress'].includes(r.status) ? (
                    <Button size="sm" onClick={() => openCount(r)}><ClipboardCheck className="mr-1.5 h-3.5 w-3.5" />Enter count</Button>
                  ) : null}
                  {canApprove && r.status === 'pending_approval' ? (
                    <>
                      <Button size="sm" onClick={() => action(r, 'approve', 'Count approved')}><Check className="mr-1 h-3.5 w-3.5" />Approve</Button>
                      <Button size="sm" variant="ghost" className="text-red-600" onClick={() => action(r, 'reject', 'Count rejected')}><X className="h-4 w-4" /></Button>
                    </>
                  ) : null}
                </div>
              ),
            },
          ]}
          rows={counts.data}
          loading={counts.loading}
          error={counts.error}
          onRetry={counts.refetch}
          emptyTitle="No cycle counts"
          emptyMessage="Create a cycle count to reconcile physical stock with system records."
        />
        <Pagination meta={counts.meta} onPageChange={setPage} />
      </Card>

      <Modal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        title="New cycle count"
        description="Lines are generated from current on-hand balances for the chosen scope."
        size="md"
        footer={
          <>
            <Button variant="outline" onClick={() => setCreateOpen(false)} disabled={saving}>Cancel</Button>
            <Button form="cc-form" type="submit" disabled={saving}>{saving ? 'Creating…' : 'Create'}</Button>
          </>
        }
      >
        <form id="cc-form" onSubmit={submit} className="space-y-4">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Field label="Warehouse" required>
              <Select value={form.warehouse_id} onChange={(e) => setForm((f) => ({ ...f, warehouse_id: e.target.value, location_id: '' }))} required>
                <option value="">Select warehouse</option>
                {(warehouses || []).map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
              </Select>
            </Field>
            <Field label="Location" hint="Leave blank to count the whole warehouse.">
              <Select value={form.location_id} onChange={(e) => setForm((f) => ({ ...f, location_id: e.target.value }))} disabled={!form.warehouse_id}>
                <option value="">All locations</option>
                {(locations || []).map((l) => <option key={l.id} value={l.id}>{l.code}</option>)}
              </Select>
            </Field>
            <Field label="Count type">
              <Select value={form.count_type} onChange={(e) => setForm((f) => ({ ...f, count_type: e.target.value }))}>
                <option value="location">Location</option>
                <option value="products">Products</option>
                <option value="full">Full</option>
              </Select>
            </Field>
          </div>
          <Field label="Notes"><Textarea value={form.notes} onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value }))} /></Field>
        </form>
      </Modal>

      <Modal
        open={Boolean(countTarget)}
        onClose={() => setCountTarget(null)}
        title={`Enter count — ${countTarget?.number || ''}`}
        size="lg"
        footer={
          <>
            <Button variant="outline" onClick={() => setCountTarget(null)} disabled={saving}>Cancel</Button>
            <Button form="count-form" type="submit" disabled={saving}>{saving ? 'Saving…' : 'Submit count'}</Button>
          </>
        }
      >
        <form id="count-form" onSubmit={submitCount} className="space-y-3">
          {(countTarget?.lines || []).map((line) => {
            const variance = (Number(counted[line.id]) || 0) - Number(line.system_qty || 0);
            return (
              <div key={line.id} className="flex flex-wrap items-end gap-3 rounded-md border border-slate-200 p-3">
                <div className="min-w-[200px] flex-1">
                  <p className="text-sm font-medium text-slate-700">{line.sku} — {line.product_name}</p>
                  <p className="text-xs text-slate-400">System: {formatQty(line.system_qty)}</p>
                </div>
                <Field label="Counted qty" className="w-32">
                  <Input type="number" min="0" step="0.01" value={counted[line.id] ?? ''} onChange={(e) => setCounted((p) => ({ ...p, [line.id]: e.target.value }))} />
                </Field>
                <div className="w-24 pb-2 text-right text-sm">
                  <span className={variance < 0 ? 'text-red-600' : variance > 0 ? 'text-emerald-600' : 'text-slate-400'}>
                    {variance > 0 ? '+' : ''}{formatQty(variance)}
                  </span>
                </div>
              </div>
            );
          })}
        </form>
      </Modal>
    </div>
  );
}
