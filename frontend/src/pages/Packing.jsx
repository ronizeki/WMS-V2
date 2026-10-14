import React, { useState } from 'react';
import { CheckCircle2, PackagePlus } from 'lucide-react';
import api from '../lib/api';
import { useApiResource } from '../hooks/useApi';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../components/ui/toaster';
import { PageHeader } from '../components/common/PageHeader';
import { DataTable, Pagination } from '../components/common/DataTable';
import { Toolbar } from '../components/common/Toolbar';
import { Button } from '../components/ui/button';
import { Card } from '../components/ui/card';
import { Field, Input, Select } from '../components/ui/form';
import { Modal } from '../components/ui/modal';
import { StatusBadge } from '../components/ui/primitives';
import { formatDateTime, formatQty, titleCase } from '../lib/format';
import { TASK_STATUSES, STATUS_TONES } from '../lib/constants';

export default function Packing() {
  const { hasPermission } = useAuth();
  const toast = useToast();
  const [status, setStatus] = useState('');
  const [page, setPage] = useState(1);
  const records = useApiResource('/packing', { status: status || undefined, page, page_size: 20 });

  const [createOpen, setCreateOpen] = useState(false);
  const [selectedOrder, setSelectedOrder] = useState('');
  const [saving, setSaving] = useState(false);
  const { data: pickableOrders } = useApiResource('/sales-orders', { status: 'picked', page_size: 50 });

  const [completeTarget, setCompleteTarget] = useState(null);
  const [packForm, setPackForm] = useState({ package_count: 1, total_weight_kg: '' });

  const createPacking = async (e) => {
    e.preventDefault();
    if (!selectedOrder) {
      toast.error('Select an order');
      return;
    }
    setSaving(true);
    try {
      await api.post(`/sales-orders/${selectedOrder}/packing`);
      toast.success('Packing record created');
      setCreateOpen(false);
      setSelectedOrder('');
      records.refetch();
    } catch (err) {
      toast.error('Could not create packing record', err.message);
    } finally {
      setSaving(false);
    }
  };

  const complete = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      await api.post(`/packing/${completeTarget.id}/complete`, {
        package_count: Number(packForm.package_count) || 1,
        total_weight_kg: packForm.total_weight_kg === '' ? undefined : Number(packForm.total_weight_kg),
      });
      toast.success('Packing completed');
      setCompleteTarget(null);
      records.refetch();
    } catch (err) {
      toast.error('Could not complete packing', err.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Packing"
        description="Consolidate picked stock into packages ready for dispatch."
        actions={
          hasPermission('outbound:pack') ? (
            <Button onClick={() => setCreateOpen(true)}><PackagePlus className="mr-2 h-4 w-4" />New packing</Button>
          ) : null
        }
      />

      <Card>
        <Toolbar>
          <Select value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }} className="sm:w-56">
            <option value="">All statuses</option>
            {TASK_STATUSES.map((s) => <option key={s} value={s}>{titleCase(s)}</option>)}
          </Select>
        </Toolbar>

        <DataTable
          columns={[
            { key: 'number', header: 'Packing', render: (r) => (<div><p className="font-medium text-slate-800">{r.number}</p><p className="text-xs text-slate-400">{r.sales_order_number}</p></div>) },
            { key: 'lines', header: 'Items', render: (r) => formatQty((r.lines || []).reduce((s, l) => s + Number(l.packed_qty || l.quantity || 0), 0)) },
            { key: 'package_count', header: 'Packages', render: (r) => r.package_count ?? '—' },
            { key: 'status', header: 'Status', render: (r) => <StatusBadge value={r.status} tones={STATUS_TONES} /> },
            { key: 'created_at', header: 'Created', render: (r) => formatDateTime(r.created_at) },
            {
              key: 'actions',
              header: '',
              className: 'text-right',
              render: (r) =>
                hasPermission('outbound:pack') && r.status !== 'completed' ? (
                  <Button size="sm" onClick={() => { setCompleteTarget(r); setPackForm({ package_count: 1, total_weight_kg: '' }); }}>
                    <CheckCircle2 className="mr-1.5 h-3.5 w-3.5" />Complete
                  </Button>
                ) : null,
            },
          ]}
          rows={records.data}
          loading={records.loading}
          error={records.error}
          onRetry={records.refetch}
          emptyTitle="No packing records"
          emptyMessage="Pick an order, then create a packing record."
        />
        <Pagination meta={records.meta} onPageChange={setPage} />
      </Card>

      <Modal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        title="New packing record"
        size="sm"
        footer={
          <>
            <Button variant="outline" onClick={() => setCreateOpen(false)} disabled={saving}>Cancel</Button>
            <Button form="pack-create" type="submit" disabled={saving}>{saving ? 'Creating…' : 'Create'}</Button>
          </>
        }
      >
        <form id="pack-create" onSubmit={createPacking} className="space-y-4">
          <Field label="Picked order" required hint="Only orders that have been fully picked are listed.">
            <Select value={selectedOrder} onChange={(e) => setSelectedOrder(e.target.value)} required>
              <option value="">Select order</option>
              {(pickableOrders || []).map((o) => (
                <option key={o.id} value={o.id}>{o.number} · {o.customer_name}</option>
              ))}
            </Select>
          </Field>
          {(pickableOrders || []).length === 0 ? (
            <p className="text-sm text-amber-600">No picked orders are ready for packing yet.</p>
          ) : null}
        </form>
      </Modal>

      <Modal
        open={Boolean(completeTarget)}
        onClose={() => setCompleteTarget(null)}
        title={`Complete packing — ${completeTarget?.number || ''}`}
        size="sm"
        footer={
          <>
            <Button variant="outline" onClick={() => setCompleteTarget(null)} disabled={saving}>Cancel</Button>
            <Button form="pack-form" type="submit" disabled={saving}>{saving ? 'Saving…' : 'Confirm'}</Button>
          </>
        }
      >
        <form id="pack-form" onSubmit={complete} className="space-y-4">
          <Field label="Package count" required>
            <Input type="number" min="1" value={packForm.package_count} onChange={(e) => setPackForm((f) => ({ ...f, package_count: e.target.value }))} required />
          </Field>
          <Field label="Total weight (kg)">
            <Input type="number" min="0" step="0.01" value={packForm.total_weight_kg} onChange={(e) => setPackForm((f) => ({ ...f, total_weight_kg: e.target.value }))} />
          </Field>
        </form>
      </Modal>
    </div>
  );
}
