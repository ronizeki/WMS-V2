import React, { useMemo, useState } from 'react';
import { Eye, MoreHorizontal, Package, Plus, Trash2, Users, X, Check, Layers } from 'lucide-react';
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
import { Modal, ConfirmDialog } from '../components/ui/modal';
import { DropdownItem, DropdownMenu } from '../components/ui/dropdown';
import { StatusBadge } from '../components/ui/primitives';
import { ProductPicker } from '../components/common/ProductPicker';
import { formatCurrency, formatDate, formatQty, titleCase } from '../lib/format';
import { SO_STATUSES, STATUS_TONES } from '../lib/constants';

const PRIORITIES = ['low', 'medium', 'high', 'urgent'];

export default function Orders() {
  const { hasPermission } = useAuth();
  const toast = useToast();
  const [status, setStatus] = useState('');
  const [page, setPage] = useState(1);

  const { data: warehouses } = useApiResource('/warehouses', { page_size: 100 });
  const { data: customers, refetch: refetchCustomers } = useApiResource('/customers', { page_size: 200 });
  const orders = useApiResource('/sales-orders', { status: status || undefined, page, page_size: 20 });

  const [createOpen, setCreateOpen] = useState(false);
  const [form, setForm] = useState({ customer_id: '', warehouse_id: '', priority: 'medium', requested_ship_date: '', reference: '', notes: '', lines: [] });
  const [saving, setSaving] = useState(false);

  const [detail, setDetail] = useState(null);
  const { data: detailData } = useApiResource(detail ? `/sales-orders/${detail.id}` : null);

  const [confirmCancel, setConfirmCancel] = useState(null);

  const [customerOpen, setCustomerOpen] = useState(false);
  const [customerForm, setCustomerForm] = useState({ name: '', code: '', email: '', phone: '', address: '', city: '' });

  const openCreate = () => {
    setForm({ customer_id: '', warehouse_id: warehouses?.[0]?.id || '', priority: 'medium', requested_ship_date: '', reference: '', notes: '', lines: [] });
    setCreateOpen(true);
  };

  const addLine = () => setForm((f) => ({ ...f, lines: [...f.lines, { product: null, ordered_qty: 1, unit_price: 0 }] }));
  const setLine = (index, patch) => setForm((f) => ({ ...f, lines: f.lines.map((l, i) => (i === index ? { ...l, ...patch } : l)) }));
  const removeLine = (index) => setForm((f) => ({ ...f, lines: f.lines.filter((_, i) => i !== index) }));

  const total = useMemo(
    () => form.lines.reduce((sum, l) => sum + (Number(l.ordered_qty) || 0) * (Number(l.unit_price) || 0), 0),
    [form.lines]
  );

  const submit = async (e) => {
    e.preventDefault();
    if (!form.customer_id || !form.warehouse_id) {
      toast.error('Missing details', 'Customer and warehouse are required.');
      return;
    }
    if (form.lines.length === 0 || form.lines.some((l) => !l.product)) {
      toast.error('Add at least one product line');
      return;
    }
    setSaving(true);
    try {
      await api.post('/sales-orders', {
        customer_id: form.customer_id,
        warehouse_id: form.warehouse_id,
        priority: form.priority,
        requested_ship_date: form.requested_ship_date || undefined,
        reference: form.reference || undefined,
        notes: form.notes || undefined,
        lines: form.lines.map((l) => ({
          product_id: l.product.id,
          ordered_qty: Number(l.ordered_qty) || 0,
          unit_price: Number(l.unit_price) || 0,
          unit: l.product.base_unit || 'PCS',
        })),
      });
      toast.success('Sales order created');
      setCreateOpen(false);
      orders.refetch();
    } catch (err) {
      toast.error('Could not create order', err.message);
    } finally {
      setSaving(false);
    }
  };

  const run = async (order, action, successMessage) => {
    try {
      await api.post(`/sales-orders/${order.id}/${action}`);
      toast.success(successMessage);
      orders.refetch();
      if (detail?.id === order.id) setDetail({ ...order, _refresh: Date.now() });
    } catch (err) {
      toast.error('Action failed', err.message);
    }
  };

  const createCustomer = async (e) => {
    e.preventDefault();
    try {
      await api.post('/customers', {
        name: customerForm.name,
        code: customerForm.code || undefined,
        email: customerForm.email || undefined,
        phone: customerForm.phone || undefined,
        address: customerForm.address || undefined,
        city: customerForm.city || undefined,
      });
      toast.success('Customer created');
      setCustomerForm({ name: '', code: '', email: '', phone: '', address: '', city: '' });
      refetchCustomers();
    } catch (err) {
      toast.error('Could not create customer', err.message);
    }
  };

  const order = detailData || detail;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Sales Orders"
        description="Capture customer demand, reserve stock and drive fulfilment."
        actions={
          hasPermission('outbound:write') ? (
            <>
              <Button variant="outline" onClick={() => setCustomerOpen(true)}>
                <Users className="mr-2 h-4 w-4" /> Customers
              </Button>
              <Button onClick={openCreate}>
                <Plus className="mr-2 h-4 w-4" /> New order
              </Button>
            </>
          ) : null
        }
      />

      <Card>
        <Toolbar>
          <Select value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }} className="sm:w-56">
            <option value="">All statuses</option>
            {SO_STATUSES.map((s) => <option key={s} value={s}>{titleCase(s)}</option>)}
          </Select>
        </Toolbar>

        <DataTable
          columns={[
            {
              key: 'number',
              header: 'Order',
              render: (r) => (
                <div>
                  <p className="font-medium text-slate-800">{r.number}</p>
                  <p className="text-xs text-slate-400">{r.reference || '—'}</p>
                </div>
              ),
            },
            { key: 'customer_name', header: 'Customer' },
            { key: 'total_amount', header: 'Value', className: 'text-right', render: (r) => formatCurrency(r.total_amount) },
            { key: 'priority', header: 'Priority', render: (r) => titleCase(r.priority) },
            { key: 'status', header: 'Status', render: (r) => <StatusBadge value={r.status} tones={STATUS_TONES} /> },
            { key: 'created_at', header: 'Created', render: (r) => formatDate(r.created_at) },
            {
              key: 'actions',
              header: '',
              className: 'text-right',
              render: (r) => (
                <div className="flex justify-end gap-1">
                  <Button variant="ghost" size="sm" onClick={() => setDetail(r)}>
                    <Eye className="h-4 w-4" />
                  </Button>
                  {hasPermission('outbound:write') ? (
                    <DropdownMenu
                      trigger={
                        <button type="button" className="rounded-md p-1.5 text-slate-400 hover:bg-slate-100">
                          <MoreHorizontal className="h-4 w-4" />
                        </button>
                      }
                    >
                      {['draft', 'pending'].includes(r.status) ? (
                        <DropdownItem icon={Check} onClick={() => run(r, 'confirm', 'Order confirmed')}>Confirm order</DropdownItem>
                      ) : null}
                      {!['cancelled', 'shipped', 'closed'].includes(r.status) && hasPermission('outbound:pick') ? (
                        <DropdownItem icon={Layers} onClick={() => run(r, 'allocate', 'Stock reserved for order')}>Allocate stock</DropdownItem>
                      ) : null}
                      {!['cancelled', 'shipped'].includes(r.status) ? (
                        <DropdownItem icon={X} className="text-red-600" onClick={() => setConfirmCancel(r)}>Cancel order</DropdownItem>
                      ) : null}
                    </DropdownMenu>
                  ) : null}
                </div>
              ),
            },
          ]}
          rows={orders.data}
          loading={orders.loading}
          error={orders.error}
          onRetry={orders.refetch}
          emptyTitle="No sales orders"
          emptyMessage="Create a sales order to begin fulfilment."
          emptyAction={hasPermission('outbound:write') ? <Button onClick={openCreate}><Plus className="mr-2 h-4 w-4" />New order</Button> : null}
        />
        <Pagination meta={orders.meta} onPageChange={setPage} />
      </Card>

      {/* Create order */}
      <Modal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        title="New sales order"
        size="lg"
        footer={
          <>
            <Button variant="outline" onClick={() => setCreateOpen(false)} disabled={saving}>Cancel</Button>
            <Button form="so-form" type="submit" disabled={saving}>{saving ? 'Creating…' : `Create order · ${formatCurrency(total)}`}</Button>
          </>
        }
      >
        <form id="so-form" onSubmit={submit} className="space-y-4">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Field label="Customer" required>
              <Select value={form.customer_id} onChange={(e) => setForm((f) => ({ ...f, customer_id: e.target.value }))} required>
                <option value="">Select customer</option>
                {(customers || []).map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </Select>
            </Field>
            <Field label="Warehouse" required>
              <Select value={form.warehouse_id} onChange={(e) => setForm((f) => ({ ...f, warehouse_id: e.target.value }))} required>
                <option value="">Select warehouse</option>
                {(warehouses || []).map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
              </Select>
            </Field>
            <Field label="Priority">
              <Select value={form.priority} onChange={(e) => setForm((f) => ({ ...f, priority: e.target.value }))}>
                {PRIORITIES.map((p) => <option key={p} value={p}>{titleCase(p)}</option>)}
              </Select>
            </Field>
            <Field label="Requested ship date"><Input type="date" value={form.requested_ship_date} onChange={(e) => setForm((f) => ({ ...f, requested_ship_date: e.target.value }))} /></Field>
            <Field label="Reference"><Input value={form.reference} onChange={(e) => setForm((f) => ({ ...f, reference: e.target.value }))} placeholder="PO / invoice no." /></Field>
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
                    <ProductPicker selected={line.product} onChange={(p) => setLine(index, { product: p, unit_price: p.selling_price || 0 })} />
                  </div>
                  <Field label="Qty" className="w-24"><Input type="number" min="0" step="0.01" value={line.ordered_qty} onChange={(e) => setLine(index, { ordered_qty: e.target.value })} /></Field>
                  <Field label="Unit price" className="w-32"><Input type="number" min="0" step="0.01" value={line.unit_price} onChange={(e) => setLine(index, { unit_price: e.target.value })} /></Field>
                  <Button type="button" variant="ghost" className="text-red-600" onClick={() => removeLine(index)}><Trash2 className="h-4 w-4" /></Button>
                </div>
              ))}
              {form.lines.length === 0 ? <p className="text-sm text-slate-400">No lines added yet.</p> : null}
            </div>
          </div>
        </form>
      </Modal>

      {/* Order detail */}
      <Modal open={Boolean(detail)} onClose={() => setDetail(null)} title={order?.number ? `Order ${order.number}` : 'Order'} size="lg">
        {order ? (
          <div className="space-y-5">
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
              <Info label="Customer" value={order.customer_name} />
              <Info label="Status" value={<StatusBadge value={order.status} tones={STATUS_TONES} />} />
              <Info label="Priority" value={titleCase(order.priority)} />
              <Info label="Value" value={formatCurrency(order.total_amount)} />
            </div>
            {order.requested_ship_date ? <Info label="Requested ship date" value={formatDate(order.requested_ship_date)} /> : null}

            <div>
              <p className="mb-2 text-sm font-medium text-slate-700">Lines</p>
              <div className="overflow-hidden rounded-md border border-slate-200">
                <table className="w-full text-sm">
                  <thead className="bg-slate-50 text-xs uppercase text-slate-500">
                    <tr>
                      <th className="px-3 py-2 text-left">Product</th>
                      <th className="px-3 py-2 text-right">Ordered</th>
                      <th className="px-3 py-2 text-right">Reserved</th>
                      <th className="px-3 py-2 text-right">Picked</th>
                      <th className="px-3 py-2 text-right">Packed</th>
                      <th className="px-3 py-2 text-right">Shipped</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {(order.lines || []).map((l) => (
                      <tr key={l.id}>
                        <td className="px-3 py-2"><span className="font-medium text-slate-700">{l.sku}</span> {l.product_name}</td>
                        <td className="px-3 py-2 text-right">{formatQty(l.ordered_qty)}</td>
                        <td className="px-3 py-2 text-right">{formatQty(l.reserved_qty)}</td>
                        <td className="px-3 py-2 text-right">{formatQty(l.picked_qty)}</td>
                        <td className="px-3 py-2 text-right">{formatQty(l.packed_qty)}</td>
                        <td className="px-3 py-2 text-right">{formatQty(l.shipped_qty)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {(order.picking_tasks || []).length ? (
              <div>
                <p className="mb-1 text-sm font-medium text-slate-700">Picking tasks</p>
                <ul className="space-y-1 text-sm text-slate-600">
                  {order.picking_tasks.map((t) => (
                    <li key={t.id} className="flex items-center justify-between">
                      <span>{t.number}</span>
                      <StatusBadge value={t.status} tones={STATUS_TONES} />
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}

            {(order.shipments || []).length ? (
              <div>
                <p className="mb-1 text-sm font-medium text-slate-700">Shipments</p>
                <ul className="space-y-1 text-sm text-slate-600">
                  {order.shipments.map((s) => (
                    <li key={s.id} className="flex items-center justify-between">
                      <span>{s.number} {s.tracking_reference ? `· ${s.tracking_reference}` : ''}</span>
                      <StatusBadge value={s.status} tones={STATUS_TONES} />
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
          </div>
        ) : null}
      </Modal>

      <ConfirmDialog
        open={Boolean(confirmCancel)}
        onClose={() => setConfirmCancel(null)}
        onConfirm={async () => { await run(confirmCancel, 'cancel', 'Order cancelled'); setConfirmCancel(null); }}
        title="Cancel order"
        message={`Cancel ${confirmCancel?.number}? Any reserved stock will be released.`}
        confirmLabel="Cancel order"
        destructive
      />

      <Modal open={customerOpen} onClose={() => setCustomerOpen(false)} title="Customers" size="md">
        <form onSubmit={createCustomer} className="space-y-3">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <Field label="Name" required><Input value={customerForm.name} onChange={(e) => setCustomerForm((f) => ({ ...f, name: e.target.value }))} required /></Field>
            <Field label="Code"><Input value={customerForm.code} onChange={(e) => setCustomerForm((f) => ({ ...f, code: e.target.value }))} /></Field>
            <Field label="Email"><Input type="email" value={customerForm.email} onChange={(e) => setCustomerForm((f) => ({ ...f, email: e.target.value }))} /></Field>
            <Field label="Phone"><Input value={customerForm.phone} onChange={(e) => setCustomerForm((f) => ({ ...f, phone: e.target.value }))} /></Field>
            <Field label="City"><Input value={customerForm.city} onChange={(e) => setCustomerForm((f) => ({ ...f, city: e.target.value }))} /></Field>
            <Field label="Address"><Input value={customerForm.address} onChange={(e) => setCustomerForm((f) => ({ ...f, address: e.target.value }))} /></Field>
          </div>
          <Button type="submit" size="sm"><Plus className="mr-2 h-4 w-4" />Add customer</Button>
        </form>
        <div className="mt-4 divide-y divide-slate-100 border-t border-slate-200">
          {(customers || []).length === 0 ? (
            <p className="py-4 text-sm text-slate-400">No customers yet.</p>
          ) : (
            (customers || []).map((c) => (
              <div key={c.id} className="flex items-center justify-between py-2">
                <div>
                  <p className="text-sm font-medium text-slate-700">{c.name}</p>
                  <p className="text-xs text-slate-400">{[c.email, c.phone, c.city].filter(Boolean).join(' · ') || '—'}</p>
                </div>
                <Package className="h-4 w-4 text-slate-300" />
              </div>
            ))
          )}
        </div>
      </Modal>
    </div>
  );
}

function Info({ label, value }) {
  return (
    <div>
      <p className="text-xs uppercase tracking-wide text-slate-400">{label}</p>
      <div className="mt-0.5 text-sm text-slate-700">{value || '—'}</div>
    </div>
  );
}
