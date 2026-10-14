import React, { useState } from 'react';
import { Play, CheckCircle2 } from 'lucide-react';
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

export default function Picking() {
  const { hasPermission } = useAuth();
  const toast = useToast();
  const [status, setStatus] = useState('');
  const [page, setPage] = useState(1);
  const tasks = useApiResource('/picking', { status: status || undefined, page, page_size: 20 });

  const [active, setActive] = useState(null);
  const [picked, setPicked] = useState({});
  const [saving, setSaving] = useState(false);

  const startTask = async (task) => {
    try {
      const updated = await api.post(`/picking/${task.id}/start`);
      toast.success('Picking started', updated.number);
      tasks.refetch();
    } catch (e) {
      toast.error('Could not start task', e.message);
    }
  };

  const openComplete = (task) => {
    const initial = {};
    (task.lines || []).forEach((l) => {
      initial[l.id] = { picked_qty: l.quantity, discrepancy_qty: 0, notes: '' };
    });
    setPicked(initial);
    setActive(task);
  };

  const complete = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      await api.post(`/picking/${active.id}/complete`, {
        lines: (active.lines || []).map((l) => ({
          line_id: l.id,
          picked_qty: Number(picked[l.id]?.picked_qty) || 0,
          discrepancy_qty: Number(picked[l.id]?.discrepancy_qty) || 0,
          notes: picked[l.id]?.notes || undefined,
        })),
      });
      toast.success('Picking completed');
      setActive(null);
      tasks.refetch();
    } catch (err) {
      toast.error('Could not complete picking', err.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Picking"
        description="Work the pick list, scan locations and confirm picked quantities."
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
            { key: 'number', header: 'Task', render: (r) => (<div><p className="font-medium text-slate-800">{r.number}</p><p className="text-xs text-slate-400">{r.sales_order_number}</p></div>) },
            { key: 'lines', header: 'Lines', render: (r) => (r.lines || []).length },
            { key: 'priority', header: 'Priority', render: (r) => titleCase(r.priority) },
            { key: 'status', header: 'Status', render: (r) => <StatusBadge value={r.status} tones={STATUS_TONES} /> },
            { key: 'created_at', header: 'Created', render: (r) => formatDateTime(r.created_at) },
            {
              key: 'actions',
              header: '',
              className: 'text-right',
              render: (r) =>
                hasPermission('outbound:pick') && !['completed', 'cancelled'].includes(r.status) ? (
                  r.status === 'pending' ? (
                    <Button size="sm" variant="outline" onClick={() => startTask(r)}><Play className="mr-1.5 h-3.5 w-3.5" />Start</Button>
                  ) : (
                    <Button size="sm" onClick={() => openComplete(r)}><CheckCircle2 className="mr-1.5 h-3.5 w-3.5" />Complete</Button>
                  )
                ) : null,
            },
          ]}
          rows={tasks.data}
          loading={tasks.loading}
          error={tasks.error}
          onRetry={tasks.refetch}
          emptyTitle="No picking tasks"
          emptyMessage="Allocate a sales order to generate picking work."
        />
        <Pagination meta={tasks.meta} onPageChange={setPage} />
      </Card>

      <Modal
        open={Boolean(active)}
        onClose={() => setActive(null)}
        title={`Complete picking — ${active?.number || ''}`}
        size="lg"
        footer={
          <>
            <Button variant="outline" onClick={() => setActive(null)} disabled={saving}>Cancel</Button>
            <Button form="pick-form" type="submit" disabled={saving}>{saving ? 'Saving…' : 'Confirm pick'}</Button>
          </>
        }
      >
        <form id="pick-form" onSubmit={complete} className="space-y-3">
          {(active?.lines || []).map((line) => (
            <div key={line.id} className="rounded-md border border-slate-200 p-3">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-slate-700">{line.sku} — {line.product_name}</p>
                  <p className="text-xs text-slate-400">Location {line.location_id} · required {formatQty(line.quantity)}</p>
                </div>
              </div>
              <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-3">
                <Field label="Picked qty">
                  <Input
                    type="number"
                    min="0"
                    step="0.01"
                    value={picked[line.id]?.picked_qty ?? ''}
                    onChange={(e) => setPicked((p) => ({ ...p, [line.id]: { ...p[line.id], picked_qty: e.target.value } }))}
                  />
                </Field>
                <Field label="Discrepancy">
                  <Input
                    type="number"
                    min="0"
                    step="0.01"
                    value={picked[line.id]?.discrepancy_qty ?? ''}
                    onChange={(e) => setPicked((p) => ({ ...p, [line.id]: { ...p[line.id], discrepancy_qty: e.target.value } }))}
                  />
                </Field>
                <Field label="Notes">
                  <Input
                    value={picked[line.id]?.notes ?? ''}
                    onChange={(e) => setPicked((p) => ({ ...p, [line.id]: { ...p[line.id], notes: e.target.value } }))}
                  />
                </Field>
              </div>
            </div>
          ))}
        </form>
      </Modal>
    </div>
  );
}
