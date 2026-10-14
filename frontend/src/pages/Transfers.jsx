import React, { useState } from 'react';
import { ArrowRightLeft, Check, Plus, Send, Trash2, Truck, X } from 'lucide-react';
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
import { ProductPicker } from '../components/common/ProductPicker';
import { formatDateTime, formatQty, titleCase } from '../lib/format';
import { TRANSFER_STATUSES, STATUS_TONES } from '../lib/constants';

export default function Transfers() {
  const { hasPermission } = useAuth();
  const toast = useToast();
  const [status, setStatus] = useState('');
  const [page, setPage] = useState(1);
  const transfers = useApiResource('/transfers', { status: status || undefined, page, page_size: 20 });
  const { data: warehouses } = useApiResource('/warehouses', { page_size: 100 });

  const [createOpen, setCreateOpen] = useState(false);
  const [form, setForm] = useState({
    from_warehouse_id: '', from_location_id: '',
    to_warehouse_id: '', to_location_id: '',
    notes: '', lines: [],
  });
  const [saving, setSaving] = useState(false);

  const { data: fromLocations } = useApiResource(form.from_warehouse_id ? `/warehouses/${form.from_warehouse_id}/locations` : null, { page_size: 200 });
  const { data: toLocations } = useApiResource(form.to_warehouse_id ? `/warehouses/${form.to_warehouse_id}/locations` : null, { page_size: 200 });

  const addLine = () => setForm((f) => ({ ...f, lines: [...f.lines, { product: null, requested_qty: 1 }] }));
  const setLine = (index, patch) => setForm((f) => ({ ...f, lines: f.lines.map((l, i) => (i === index ? { ...l, ...patch } : l)) }));
  const removeLine = (index) => setForm((f) => ({ ...f, lines: f.lines.filter((_, i) => i !== index) }));

  const submit = async (e) => {
    e.preventDefault();
    if (!form.from_warehouse_id || !form.from_location_id || !form.to_warehouse_id || !form.to_location_id) {
      toast.error('Missing route', 'Source and destination warehouse + location are required.');
      return;
    }
    if (form.lines.length === 0 || form.lines.some((l) => !l.product)) {
      toast.error('Add at least one product line');
      return;
    }
    setSaving(true);
    try {
      await api.post('/transfers', {
        from_warehouse_id: form.from_warehouse_id,
        from_location_id: form.from_location_id,
        to_warehouse_id: form.to_warehouse_id,
        to_location_id: form.to_location_id,
        notes: form.notes || undefined,
        lines: form.lines.map((l) => ({
          product_id: l.product.id,
          requested_qty: Number(l.requested_qty) || 0,
          unit: l.product.base_unit || 'PCS',
        })),
      });
      toast.success('Transfer created');
      setCreateOpen(false);
      transfers.refetch();
    } catch (err) {
      toast.error('Could not create transfer', err.message);
    } finally {
      setSaving(false);
    }
  };

  const action = async (transfer, path, successMessage) => {
    try {
      await api.post(`/transfers/${transfer.id}/${path}`);
      toast.success(successMessage);
      transfers.refetch();
    } catch (e) {
      toast.error('Action failed', e.message);
    }
  };

  const [receiveTarget, setReceiveTarget] = useState(null);
  const [receiveLines, setReceiveLines] = useState({});

  const openReceive = (transfer) => {
    const initial = {};
    (transfer.lines || []).forEach((l) => {
      initial[l.id] = { received_qty: l.dispatched_qty ?? l.requested_qty, damaged_qty: 0 };
    });
    setReceiveLines(initial);
    setReceiveTarget(transfer);
  };

  const receive = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      await api.post(`/transfers/${receiveTarget.id}/receive`, {
        lines: (receiveTarget.lines || []).map((l) => ({
          line_id: l.id,
          received_qty: Number(receiveLines[l.id]?.received_qty) || 0,
          damaged_qty: Number(receiveLines[l.id]?.damaged_qty) || 0,
        })),
      });
      toast.success('Transfer received');
      setReceiveTarget(null);
      transfers.refetch();
    } catch (err) {
      toast.error('Could not receive transfer', err.message);
    } finally {
      setSaving(false);
    }
  };

  const canWrite = hasPermission('transfer:write');
  const canApprove = hasPermission('transfer:approve');

  return (
    <div className="space-y-6">
      <PageHeader
        title="Stock Transfers"
        description="Move stock between warehouses and storage locations with a full audit trail."
        actions={
          canWrite ? (
            <Button onClick={() => { setForm({ from_warehouse_id: warehouses?.[0]?.id || '', from_location_id: '', to_warehouse_id: '', to_location_id: '', notes: '', lines: [] }); setCreateOpen(true); }}>
              <Plus className="mr-2 h-4 w-4" /> New transfer
            </Button>
          ) : null
        }
      />

      <Card>
        <Toolbar>
          <Select value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }} className="sm:w-56">
            <option value="">All statuses</option>
            {TRANSFER_STATUSES.map((s) => <option key={s} value={s}>{titleCase(s)}</option>)}
          </Select>
        </Toolbar>

        <DataTable
          columns={[
            { key: 'number', header: 'Transfer', render: (r) => <span className="font-medium text-slate-800">{r.number}</span> },
            {
              key: 'route',
              header: 'Route',
              render: (r) => (
                <span className="inline-flex items-center gap-1 text-slate-600">
                  {r.from_warehouse_id?.slice(0, 6)} <ArrowRightLeft className="h-3.5 w-3.5 text-slate-400" /> {r.to_warehouse_id?.slice(0, 6)}
                </span>
              ),
            },
            { key: 'lines', header: 'Lines', render: (r) => (r.lines || []).length },
            { key: 'status', header: 'Status', render: (r) => <StatusBadge value={r.status} tones={STATUS_TONES} /> },
            { key: 'created_at', header: 'Created', render: (r) => formatDateTime(r.created_at) },
            {
              key: 'actions',
              header: '',
              className: 'text-right',
              render: (r) => (
                <div className="flex justify-end gap-1">
                  {canApprove && r.status === 'requested' && r.approval_status === 'pending' ? (
                    <Button size="sm" variant="outline" onClick={() => action(r, 'approve', 'Transfer approved')}><Check className="mr-1 h-3.5 w-3.5" />Approve</Button>
                  ) : null}
                  {canWrite && ['requested', 'approved'].includes(r.status) ? (
                    <Button size="sm" onClick={() => action(r, 'dispatch', 'Transfer dispatched')}><Send className="mr-1.5 h-3.5 w-3.5" />Dispatch</Button>
                  ) : null}
                  {canWrite && r.status === 'in_transit' ? (
                    <Button size="sm" onClick={() => openReceive(r)}><Truck className="mr-1.5 h-3.5 w-3.5" />Receive</Button>
                  ) : null}
                  {canWrite && ['requested', 'approved'].includes(r.status) ? (
                    <Button size="sm" variant="ghost" className="text-red-600" onClick={() => action(r, 'cancel', 'Transfer cancelled')}><X className="h-4 w-4" /></Button>
                  ) : null}
                </div>
              ),
            },
          ]}
          rows={transfers.data}
          loading={transfers.loading}
          error={transfers.error}
          onRetry={transfers.refetch}
          emptyTitle="No transfers"
          emptyMessage="Create a transfer to move stock between locations."
        />
        <Pagination meta={transfers.meta} onPageChange={setPage} />
      </Card>

      <Modal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        title="New stock transfer"
        size="lg"
        footer={
          <>
            <Button variant="outline" onClick={() => setCreateOpen(false)} disabled={saving}>Cancel</Button>
            <Button form="transfer-form" type="submit" disabled={saving}>{saving ? 'Creating…' : 'Create transfer'}</Button>
          </>
        }
      >
        <form id="transfer-form" onSubmit={submit} className="space-y-4">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Field label="From warehouse" required>
              <Select value={form.from_warehouse_id} onChange={(e) => setForm((f) => ({ ...f, from_warehouse_id: e.target.value, from_location_id: '' }))} required>
                <option value="">Select warehouse</option>
                {(warehouses || []).map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
              </Select>
            </Field>
            <Field label="From location" required>
              <Select value={form.from_location_id} onChange={(e) => setForm((f) => ({ ...f, from_location_id: e.target.value }))} required disabled={!form.from_warehouse_id}>
                <option value="">Select location</option>
                {(fromLocations || []).map((l) => <option key={l.id} value={l.id}>{l.code}</option>)}
              </Select>
            </Field>
            <Field label="To warehouse" required>
              <Select value={form.to_warehouse_id} onChange={(e) => setForm((f) => ({ ...f, to_warehouse_id: e.target.value, to_location_id: '' }))} required>
                <option value="">Select warehouse</option>
                {(warehouses || []).map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
              </Select>
            </Field>
            <Field label="To location" required>
              <Select value={form.to_location_id} onChange={(e) => setForm((f) => ({ ...f, to_location_id: e.target.value }))} required disabled={!form.to_warehouse_id}>
                <option value="">Select location</option>
                {(toLocations || []).map((l) => <option key={l.id} value={l.id}>{l.code}</option>)}
              </Select>
            </Field>
          </div>
          <Field label="Notes"><Textarea value={form.notes} onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value }))} /></Field>
          <div>
            <div className="mb-2 flex items-center justify-between">
              <p className="text-sm font-medium text-slate-700">Lines</p>
              <Button type="button" size="sm" variant="outline" onClick={addLine}><Plus className="mr-1 h-3.5 w-3.5" />Add line</Button>
            </div>
            <div className="space-y-2">
              {form.lines.map((line, index) => (
                <div key={index} className="flex flex-wrap items-end gap-2 rounded-md bg-slate-50 p-2">
                  <div className="min-w-[220px] flex-1">
                    <ProductPicker selected={line.product} onChange={(p) => setLine(index, { product: p })} />
                  </div>
                  <Field label="Qty" className="w-24"><Input type="number" min="0" step="0.01" value={line.requested_qty} onChange={(e) => setLine(index, { requested_qty: e.target.value })} /></Field>
                  <Button type="button" variant="ghost" className="text-red-600" onClick={() => removeLine(index)}><Trash2 className="h-4 w-4" /></Button>
                </div>
              ))}
              {form.lines.length === 0 ? <p className="text-sm text-slate-400">No lines added yet.</p> : null}
            </div>
          </div>
        </form>
      </Modal>

      <Modal
        open={Boolean(receiveTarget)}
        onClose={() => setReceiveTarget(null)}
        title={`Receive transfer — ${receiveTarget?.number || ''}`}
        size="lg"
        footer={
          <>
            <Button variant="outline" onClick={() => setReceiveTarget(null)} disabled={saving}>Cancel</Button>
            <Button form="receive-form" type="submit" disabled={saving}>{saving ? 'Saving…' : 'Confirm receipt'}</Button>
          </>
        }
      >
        <form id="receive-form" onSubmit={receive} className="space-y-3">
          {(receiveTarget?.lines || []).map((line) => (
            <div key={line.id} className="rounded-md border border-slate-200 p-3">
              <p className="text-sm font-medium text-slate-700">{line.sku} — {line.product_name}</p>
              <p className="text-xs text-slate-400">Dispatched {formatQty(line.dispatched_qty ?? line.requested_qty)}</p>
              <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
                <Field label="Received qty">
                  <Input type="number" min="0" step="0.01" value={receiveLines[line.id]?.received_qty ?? ''} onChange={(e) => setReceiveLines((p) => ({ ...p, [line.id]: { ...p[line.id], received_qty: e.target.value } }))} />
                </Field>
                <Field label="Damaged qty">
                  <Input type="number" min="0" step="0.01" value={receiveLines[line.id]?.damaged_qty ?? ''} onChange={(e) => setReceiveLines((p) => ({ ...p, [line.id]: { ...p[line.id], damaged_qty: e.target.value } }))} />
                </Field>
              </div>
            </div>
          ))}
        </form>
      </Modal>
    </div>
  );
}
