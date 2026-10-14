import React, { useState } from 'react';
import { Send, MapPin, PackagePlus } from 'lucide-react';
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
import { SHIPMENT_STATUSES, STATUS_TONES } from '../lib/constants';

const SHIPPABLE = ['confirmed', 'allocated', 'picking', 'picked', 'packing', 'packed', 'partially_shipped'];

export default function Shipping() {
  const { hasPermission } = useAuth();
  const toast = useToast();
  const [status, setStatus] = useState('');
  const [page, setPage] = useState(1);
  const shipments = useApiResource('/shipments', { status: status || undefined, page, page_size: 20 });

  const [createOpen, setCreateOpen] = useState(false);
  const [form, setForm] = useState({ sales_order_id: '', carrier_name: '', tracking_reference: '', notes: '' });
  const [saving, setSaving] = useState(false);
  const { data: orders } = useApiResource('/sales-orders', { page_size: 100 });

  const shippable = (orders || []).filter((o) => SHIPPABLE.includes(o.status));

  const createShipment = async (e) => {
    e.preventDefault();
    if (!form.sales_order_id) {
      toast.error('Select an order');
      return;
    }
    setSaving(true);
    try {
      await api.post('/shipments', {
        sales_order_id: form.sales_order_id,
        carrier_name: form.carrier_name || undefined,
        tracking_reference: form.tracking_reference || undefined,
        notes: form.notes || undefined,
      });
      toast.success('Shipment created');
      setCreateOpen(false);
      setForm({ sales_order_id: '', carrier_name: '', tracking_reference: '', notes: '' });
      shipments.refetch();
    } catch (err) {
      toast.error('Could not create shipment', err.message);
    } finally {
      setSaving(false);
    }
  };

  const post = async (shipment) => {
    try {
      await api.post(`/shipments/${shipment.id}/post`, undefined, { idempotencyKey: `ship-post-${shipment.id}` });
      toast.success('Shipment posted', 'Stock has been dispatched.');
      shipments.refetch();
    } catch (e) {
      toast.error('Could not post shipment', e.message);
    }
  };

  const deliver = async (shipment) => {
    try {
      await api.post(`/shipments/${shipment.id}/deliver`);
      toast.success('Marked as delivered');
      shipments.refetch();
    } catch (e) {
      toast.error('Could not update shipment', e.message);
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Shipping"
        description="Create shipments, dispatch stock and confirm delivery."
        actions={
          hasPermission('outbound:ship') ? (
            <Button onClick={() => setCreateOpen(true)}><PackagePlus className="mr-2 h-4 w-4" />New shipment</Button>
          ) : null
        }
      />

      <Card>
        <Toolbar>
          <Select value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }} className="sm:w-56">
            <option value="">All statuses</option>
            {SHIPMENT_STATUSES.map((s) => <option key={s} value={s}>{titleCase(s)}</option>)}
          </Select>
        </Toolbar>

        <DataTable
          columns={[
            { key: 'number', header: 'Shipment', render: (r) => (<div><p className="font-medium text-slate-800">{r.number}</p><p className="text-xs text-slate-400">{r.sales_order_number}</p></div>) },
            { key: 'customer_name', header: 'Customer' },
            { key: 'carrier_name', header: 'Carrier', render: (r) => r.carrier_name || '—' },
            { key: 'tracking_reference', header: 'Tracking', render: (r) => r.tracking_reference || '—' },
            { key: 'items', header: 'Items', className: 'text-right', render: (r) => formatQty((r.lines || []).reduce((s, l) => s + Number(l.quantity || 0), 0)) },
            { key: 'status', header: 'Status', render: (r) => <StatusBadge value={r.status} tones={STATUS_TONES} /> },
            { key: 'created_at', header: 'Created', render: (r) => formatDateTime(r.created_at) },
            {
              key: 'actions',
              header: '',
              className: 'text-right',
              render: (r) =>
                hasPermission('outbound:ship') ? (
                  <div className="flex justify-end gap-1">
                    {!r.posted ? (
                      <Button size="sm" onClick={() => post(r)}><Send className="mr-1.5 h-3.5 w-3.5" />Post</Button>
                    ) : null}
                    {r.status === 'in_transit' ? (
                      <Button size="sm" variant="outline" onClick={() => deliver(r)}><MapPin className="mr-1.5 h-3.5 w-3.5" />Deliver</Button>
                    ) : null}
                  </div>
                ) : null,
            },
          ]}
          rows={shipments.data}
          loading={shipments.loading}
          error={shipments.error}
          onRetry={shipments.refetch}
          emptyTitle="No shipments"
          emptyMessage="Create a shipment for a packed order to dispatch it."
        />
        <Pagination meta={shipments.meta} onPageChange={setPage} />
      </Card>

      <Modal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        title="New shipment"
        size="md"
        footer={
          <>
            <Button variant="outline" onClick={() => setCreateOpen(false)} disabled={saving}>Cancel</Button>
            <Button form="shipment-form" type="submit" disabled={saving}>{saving ? 'Creating…' : 'Create shipment'}</Button>
          </>
        }
      >
        <form id="shipment-form" onSubmit={createShipment} className="space-y-4">
          <Field label="Order" required hint="Outstanding quantities will be added to the shipment.">
            <Select value={form.sales_order_id} onChange={(e) => setForm((f) => ({ ...f, sales_order_id: e.target.value }))} required>
              <option value="">Select order</option>
              {shippable.map((o) => (
                <option key={o.id} value={o.id}>{o.number} · {o.customer_name}</option>
              ))}
            </Select>
          </Field>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Field label="Carrier"><Input value={form.carrier_name} onChange={(e) => setForm((f) => ({ ...f, carrier_name: e.target.value }))} placeholder="e.g. JNE" /></Field>
            <Field label="Tracking reference"><Input value={form.tracking_reference} onChange={(e) => setForm((f) => ({ ...f, tracking_reference: e.target.value }))} /></Field>
          </div>
          <Field label="Notes"><Textarea value={form.notes} onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value }))} /></Field>
        </form>
      </Modal>
    </div>
  );
}
