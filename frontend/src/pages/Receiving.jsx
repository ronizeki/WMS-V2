import React, { useMemo, useState } from 'react';
import { Check, PackageCheck, Plus, Send, Trash2, X } from 'lucide-react';
import api from '../lib/api';
import { useApiResource } from '../hooks/useApi';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../components/ui/toaster';
import { PageHeader } from '../components/common/PageHeader';
import { DataTable, Pagination } from '../components/common/DataTable';
import { Button } from '../components/ui/button';
import { Card } from '../components/ui/card';
import { Tabs } from '../components/ui/tabs';
import { Field, Input, Select, Textarea } from '../components/ui/form';
import { Modal, ConfirmDialog } from '../components/ui/modal';
import { StatusBadge } from '../components/ui/primitives';
import { ProductPicker } from '../components/common/ProductPicker';
import { formatCurrency, formatDateTime, formatQty } from '../lib/format';
import { STATUS_TONES } from '../lib/constants';

export default function Receiving() {
  const { hasPermission } = useAuth();
  const toast = useToast();
  const [tab, setTab] = useState('po');
  const [page, setPage] = useState(1);

  const { data: warehouses } = useApiResource('/warehouses', { page_size: 100 });
  const { data: suppliers } = useApiResource('/suppliers', { page_size: 200 });
  const { data: poOptions } = useApiResource('/purchase-orders', { page_size: 100 });

  const pos = useApiResource(tab === 'po' ? '/purchase-orders' : null, { page, page_size: 20 });
  const receipts = useApiResource(tab === 'receipts' ? '/goods-receipts' : null, { page, page_size: 20 });
  const putaway = useApiResource(tab === 'putaway' ? '/putaway' : null, { page, page_size: 20 });

  const active = { po: pos, receipts, putaway }[tab];

  // ---- create PO
  const [poOpen, setPoOpen] = useState(false);
  const [poForm, setPoForm] = useState({ supplier_id: '', warehouse_id: '', expected_date: '', notes: '', lines: [] });
  const [savingPo, setSavingPo] = useState(false);

  const addPoLine = () => setPoForm((f) => ({ ...f, lines: [...f.lines, { product: null, ordered_qty: 1, unit_cost: 0 }] }));
  const setPoLine = (index, patch) =>
    setPoForm((f) => ({ ...f, lines: f.lines.map((l, i) => (i === index ? { ...l, ...patch } : l)) }));
  const removePoLine = (index) => setPoForm((f) => ({ ...f, lines: f.lines.filter((_, i) => i !== index) }));

  const submitPo = async (e) => {
    e.preventDefault();
    if (!poForm.supplier_id || !poForm.warehouse_id || poForm.lines.length === 0 || poForm.lines.some((l) => !l.product)) {
      toast.error('Missing details', 'Supplier, warehouse and at least one product line are required.');
      return;
    }
    setSavingPo(true);
    try {
      await api.post('/purchase-orders', {
        supplier_id: poForm.supplier_id,
        warehouse_id: poForm.warehouse_id,
        expected_date: poForm.expected_date || undefined,
        notes: poForm.notes || undefined,
        lines: poForm.lines.map((l) => ({
          product_id: l.product.id,
          ordered_qty: Number(l.ordered_qty) || 0,
          unit_cost: Number(l.unit_cost) || 0,
          unit: l.product.base_unit || 'PCS',
        })),
      });
      toast.success('Purchase order created');
      setPoOpen(false);
      setPoForm({ supplier_id: '', warehouse_id: '', expected_date: '', notes: '', lines: [] });
      pos.refetch();
    } catch (err) {
      toast.error('Could not create purchase order', err.message);
    } finally {
      setSavingPo(false);
    }
  };

  const poAction = async (id, action) => {
    try {
      await api.post(`/purchase-orders/${id}/${action}`);
      toast.success(`Purchase order ${action === 'approve' ? 'approved' : 'cancelled'}`);
      pos.refetch();
    } catch (err) {
      toast.error('Action failed', err.message);
    }
  };

  // ---- create receipt
  const [receiptOpen, setReceiptOpen] = useState(false);
  const [receiptMode, setReceiptMode] = useState('po');
  const [receiptForm, setReceiptForm] = useState({ purchase_order_id: '', warehouse_id: '', notes: '', lines: [] });
  const [savingReceipt, setSavingReceipt] = useState(false);

  const openReceipt = () => {
    setReceiptForm({ purchase_order_id: '', warehouse_id: warehouses?.[0]?.id || '', notes: '', lines: [] });
    setReceiptMode('po');
    setReceiptOpen(true);
  };

  const addReceiptLine = () => setReceiptForm((f) => ({ ...f, lines: [...f.lines, { product: null, received_qty: 1, unit_cost: 0, damaged_qty: 0 }] }));
  const setReceiptLine = (index, patch) =>
    setReceiptForm((f) => ({ ...f, lines: f.lines.map((l, i) => (i === index ? { ...l, ...patch } : l)) }));
  const removeReceiptLine = (index) => setReceiptForm((f) => ({ ...f, lines: f.lines.filter((_, i) => i !== index) }));

  const submitReceipt = async (e) => {
    e.preventDefault();
    if (!receiptForm.warehouse_id) {
      toast.error('Warehouse required');
      return;
    }
    if (receiptMode === 'po' && !receiptForm.purchase_order_id) {
      toast.error('Select a purchase order');
      return;
    }
    if (receiptMode === 'manual' && (receiptForm.lines.length === 0 || receiptForm.lines.some((l) => !l.product))) {
      toast.error('Add at least one product line');
      return;
    }
    setSavingReceipt(true);
    try {
      const payload = {
        warehouse_id: receiptForm.warehouse_id,
        notes: receiptForm.notes || undefined,
      };
      if (receiptMode === 'po') {
        payload.purchase_order_id = receiptForm.purchase_order_id;
      } else {
        payload.lines = receiptForm.lines.map((l) => ({
          product_id: l.product.id,
          expected_qty: Number(l.received_qty) || 0,
          received_qty: Number(l.received_qty) || 0,
          damaged_qty: Number(l.damaged_qty) || 0,
          unit_cost: Number(l.unit_cost) || 0,
          unit: l.product.base_unit || 'PCS',
        }));
      }
      const created = await api.post('/goods-receipts', payload);
      toast.success('Goods receipt created');
      setReceiptOpen(false);
      receipts.refetch();
      // Offer to post immediately
      setPostTarget(created);
    } catch (err) {
      toast.error('Could not create receipt', err.message);
    } finally {
      setSavingReceipt(false);
    }
  };

  const [postTarget, setPostTarget] = useState(null);
  const [posting, setPosting] = useState(false);
  const postReceipt = async () => {
    setPosting(true);
    try {
      await api.post(`/goods-receipts/${postTarget.id}/post`, undefined, {
        idempotencyKey: `grn-post-${postTarget.id}`,
      });
      toast.success('Receipt posted', 'Stock is now on hand at the receiving location.');
      setPostTarget(null);
      receipts.refetch();
    } catch (err) {
      toast.error('Could not post receipt', err.message);
    } finally {
      setPosting(false);
    }
  };

  // ---- putaway
  const [putawayTarget, setPutawayTarget] = useState(null);
  const [putawayForm, setPutawayForm] = useState({ to_location_id: '', quantity: '' });
  const { data: putawayLocations } = useApiResource(
    putawayTarget ? `/warehouses/${putawayTarget.warehouse_id}/locations` : null,
    { page_size: 200 }
  );

  const completePutaway = async (e) => {
    e.preventDefault();
    try {
      await api.post(`/putaway/${putawayTarget.id}/complete`, {
        to_location_id: putawayForm.to_location_id,
        quantity: putawayForm.quantity === '' ? undefined : Number(putawayForm.quantity),
      });
      toast.success('Putaway completed');
      setPutawayTarget(null);
      putaway.refetch();
    } catch (err) {
      toast.error('Could not complete putaway', err.message);
    }
  };

  const selectedPo = useMemo(
    () => (poOptions || []).find((p) => p.id === receiptForm.purchase_order_id),
    [poOptions, receiptForm.purchase_order_id]
  );

  return (
    <div className="space-y-6">
      <PageHeader
        title="Receiving"
        description="Raise purchase orders, receive goods into stock and complete putaway."
        actions={
          hasPermission('inbound:write') ? (
            <>
              {tab === 'po' ? <Button onClick={() => { setPoForm({ supplier_id: '', warehouse_id: warehouses?.[0]?.id || '', expected_date: '', notes: '', lines: [] }); setPoOpen(true); }}><Plus className="mr-2 h-4 w-4" />New purchase order</Button> : null}
              {tab === 'receipts' ? <Button onClick={openReceipt}><Plus className="mr-2 h-4 w-4" />New receipt</Button> : null}
            </>
          ) : null
        }
      />

      <Card>
        <Tabs
          value={tab}
          onChange={(v) => { setTab(v); setPage(1); }}
          tabs={[
            { value: 'po', label: 'Purchase orders' },
            { value: 'receipts', label: 'Goods receipts' },
            { value: 'putaway', label: 'Putaway' },
          ]}
        />

        {tab === 'po' ? (
          <DataTable
            columns={[
              { key: 'number', header: 'PO', render: (r) => <span className="font-medium text-slate-800">{r.number}</span> },
              { key: 'supplier_name', header: 'Supplier' },
              { key: 'total_amount', header: 'Total', className: 'text-right', render: (r) => formatCurrency(r.total_amount) },
              { key: 'status', header: 'Status', render: (r) => <StatusBadge value={r.status} tones={STATUS_TONES} /> },
              { key: 'expected_date', header: 'Expected', render: (r) => formatDateTime(r.expected_date) },
              {
                key: 'actions',
                header: '',
                className: 'text-right',
                render: (r) =>
                  hasPermission('inbound:approve') && ['pending', 'draft'].includes(r.status) ? (
                    <div className="flex justify-end gap-1">
                      <Button size="sm" variant="outline" onClick={() => poAction(r.id, 'approve')}><Check className="mr-1 h-3.5 w-3.5" />Approve</Button>
                      <Button size="sm" variant="ghost" className="text-red-600" onClick={() => poAction(r.id, 'cancel')}><X className="h-4 w-4" /></Button>
                    </div>
                  ) : null,
              },
            ]}
            rows={pos.data}
            loading={pos.loading}
            error={pos.error}
            onRetry={pos.refetch}
            emptyTitle="No purchase orders"
            emptyMessage="Create a purchase order to start expecting stock."
          />
        ) : null}

        {tab === 'receipts' ? (
          <DataTable
            columns={[
              { key: 'number', header: 'Receipt', render: (r) => <span className="font-medium text-slate-800">{r.number}</span> },
              { key: 'purchase_order_number', header: 'PO', render: (r) => r.purchase_order_number || '—' },
              { key: 'supplier_name', header: 'Supplier', render: (r) => r.supplier_name || '—' },
              { key: 'status', header: 'Status', render: (r) => <StatusBadge value={r.status} tones={STATUS_TONES} /> },
              {
                key: 'lines',
                header: 'Lines',
                render: (r) => (r.lines || []).length,
              },
              {
                key: 'actions',
                header: '',
                className: 'text-right',
                render: (r) =>
                  hasPermission('inbound:write') && !r.posted ? (
                    <Button size="sm" onClick={() => setPostTarget(r)}><Send className="mr-1.5 h-3.5 w-3.5" />Post</Button>
                  ) : null,
              },
            ]}
            rows={receipts.data}
            loading={receipts.loading}
            error={receipts.error}
            onRetry={receipts.refetch}
            emptyTitle="No goods receipts"
            emptyMessage="Create a receipt to bring stock into the warehouse."
          />
        ) : null}

        {tab === 'putaway' ? (
          <DataTable
            columns={[
              { key: 'number', header: 'Task', render: (r) => <span className="font-medium text-slate-800">{r.number}</span> },
              { key: 'product_name', header: 'Product', render: (r) => (<div><p className="text-slate-700">{r.product_name}</p><p className="text-xs text-slate-400">{r.sku}</p></div>) },
              { key: 'quantity', header: 'Qty', className: 'text-right', render: (r) => formatQty(r.quantity) },
              { key: 'putaway_qty', header: 'Put away', className: 'text-right', render: (r) => formatQty(r.putaway_qty) },
              { key: 'status', header: 'Status', render: (r) => <StatusBadge value={r.status} tones={STATUS_TONES} /> },
              {
                key: 'actions',
                header: '',
                className: 'text-right',
                render: (r) =>
                  hasPermission('inbound:write') && r.status !== 'completed' ? (
                    <Button size="sm" onClick={() => { setPutawayTarget(r); setPutawayForm({ to_location_id: '', quantity: r.quantity }); }}>
                      <PackageCheck className="mr-1.5 h-3.5 w-3.5" />Put away
                    </Button>
                  ) : null,
              },
            ]}
            rows={putaway.data}
            loading={putaway.loading}
            error={putaway.error}
            onRetry={putaway.refetch}
            emptyTitle="No putaway tasks"
            emptyMessage="Posting a receipt with auto-putaway enabled creates tasks here."
          />
        ) : null}

        {active?.meta ? <Pagination meta={active.meta} onPageChange={setPage} /> : null}
      </Card>

      {/* Create PO */}
      <Modal
        open={poOpen}
        onClose={() => setPoOpen(false)}
        title="New purchase order"
        size="lg"
        footer={
          <>
            <Button variant="outline" onClick={() => setPoOpen(false)} disabled={savingPo}>Cancel</Button>
            <Button form="po-form" type="submit" disabled={savingPo}>{savingPo ? 'Creating…' : 'Create PO'}</Button>
          </>
        }
      >
        <form id="po-form" onSubmit={submitPo} className="space-y-4">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Field label="Supplier" required>
              <Select value={poForm.supplier_id} onChange={(e) => setPoForm((f) => ({ ...f, supplier_id: e.target.value }))} required>
                <option value="">Select supplier</option>
                {(suppliers || []).map((s) => (
                  <option key={s.id} value={s.id}>{s.name}</option>
                ))}
              </Select>
            </Field>
            <Field label="Warehouse" required>
              <Select value={poForm.warehouse_id} onChange={(e) => setPoForm((f) => ({ ...f, warehouse_id: e.target.value }))} required>
                <option value="">Select warehouse</option>
                {(warehouses || []).map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
              </Select>
            </Field>
            <Field label="Expected date"><Input type="date" value={poForm.expected_date} onChange={(e) => setPoForm((f) => ({ ...f, expected_date: e.target.value }))} /></Field>
          </div>
          <Field label="Notes"><Textarea value={poForm.notes} onChange={(e) => setPoForm((f) => ({ ...f, notes: e.target.value }))} /></Field>

          <div>
            <div className="mb-2 flex items-center justify-between">
              <p className="text-sm font-medium text-slate-700">Order lines</p>
              <Button type="button" size="sm" variant="outline" onClick={addPoLine}><Plus className="mr-1 h-3.5 w-3.5" />Add line</Button>
            </div>
            <div className="space-y-2">
              {poForm.lines.map((line, index) => (
                <div key={index} className="flex flex-wrap items-end gap-2 rounded-md bg-slate-50 p-2">
                  <div className="min-w-[220px] flex-1">
                    <ProductPicker selected={line.product} onChange={(p) => setPoLine(index, { product: p, unit_cost: p.cost_price || 0 })} />
                  </div>
                  <Field label="Qty" className="w-24"><Input type="number" min="0" step="0.01" value={line.ordered_qty} onChange={(e) => setPoLine(index, { ordered_qty: e.target.value })} /></Field>
                  <Field label="Unit cost" className="w-28"><Input type="number" min="0" step="0.01" value={line.unit_cost} onChange={(e) => setPoLine(index, { unit_cost: e.target.value })} /></Field>
                  <Button type="button" variant="ghost" className="text-red-600" onClick={() => removePoLine(index)}><Trash2 className="h-4 w-4" /></Button>
                </div>
              ))}
              {poForm.lines.length === 0 ? <p className="text-sm text-slate-400">No lines added yet.</p> : null}
            </div>
          </div>
        </form>
      </Modal>

      {/* Create receipt */}
      <Modal
        open={receiptOpen}
        onClose={() => setReceiptOpen(false)}
        title="New goods receipt"
        size="lg"
        footer={
          <>
            <Button variant="outline" onClick={() => setReceiptOpen(false)} disabled={savingReceipt}>Cancel</Button>
            <Button form="receipt-form" type="submit" disabled={savingReceipt}>{savingReceipt ? 'Creating…' : 'Create receipt'}</Button>
          </>
        }
      >
        <form id="receipt-form" onSubmit={submitReceipt} className="space-y-4">
          <div className="flex gap-2">
            <Button type="button" size="sm" variant={receiptMode === 'po' ? 'default' : 'outline'} onClick={() => setReceiptMode('po')}>From purchase order</Button>
            <Button type="button" size="sm" variant={receiptMode === 'manual' ? 'default' : 'outline'} onClick={() => setReceiptMode('manual')}>Manual lines</Button>
          </div>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Field label="Warehouse" required>
              <Select value={receiptForm.warehouse_id} onChange={(e) => setReceiptForm((f) => ({ ...f, warehouse_id: e.target.value }))} required>
                <option value="">Select warehouse</option>
                {(warehouses || []).map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
              </Select>
            </Field>
            {receiptMode === 'po' ? (
              <Field label="Purchase order" required>
                <Select value={receiptForm.purchase_order_id} onChange={(e) => setReceiptForm((f) => ({ ...f, purchase_order_id: e.target.value }))} required>
                  <option value="">Select PO</option>
                  {(poOptions || []).filter((p) => ['pending', 'approved', 'partially_received'].includes(p.status)).map((p) => (
                    <option key={p.id} value={p.id}>{p.number} · {p.supplier_name}</option>
                  ))}
                </Select>
              </Field>
            ) : null}
          </div>

          {receiptMode === 'po' ? (
            <div className="rounded-md bg-slate-50 p-3">
              <p className="text-sm font-medium text-slate-700">Outstanding lines</p>
              {selectedPo ? (
                <ul className="mt-2 space-y-1 text-sm text-slate-600">
                  {(selectedPo.lines || []).map((l) => (
                    <li key={l.id} className="flex justify-between">
                      <span>{l.sku} — {l.product_name}</span>
                      <span>{formatQty(Number(l.ordered_qty) - Number(l.received_qty))} outstanding</span>
                    </li>
                  ))}
                  {(selectedPo.lines || []).length === 0 ? <li className="text-slate-400">No lines on this PO.</li> : null}
                </ul>
              ) : (
                <p className="mt-1 text-sm text-slate-400">Select a purchase order to see what is outstanding.</p>
              )}
            </div>
          ) : (
            <div>
              <div className="mb-2 flex items-center justify-between">
                <p className="text-sm font-medium text-slate-700">Receipt lines</p>
                <Button type="button" size="sm" variant="outline" onClick={addReceiptLine}><Plus className="mr-1 h-3.5 w-3.5" />Add line</Button>
              </div>
              <div className="space-y-2">
                {receiptForm.lines.map((line, index) => (
                  <div key={index} className="flex flex-wrap items-end gap-2 rounded-md bg-slate-50 p-2">
                    <div className="min-w-[200px] flex-1">
                      <ProductPicker selected={line.product} onChange={(p) => setReceiptLine(index, { product: p, unit_cost: p.cost_price || 0 })} />
                    </div>
                    <Field label="Received" className="w-24"><Input type="number" min="0" step="0.01" value={line.received_qty} onChange={(e) => setReceiptLine(index, { received_qty: e.target.value })} /></Field>
                    <Field label="Damaged" className="w-24"><Input type="number" min="0" step="0.01" value={line.damaged_qty} onChange={(e) => setReceiptLine(index, { damaged_qty: e.target.value })} /></Field>
                    <Field label="Unit cost" className="w-28"><Input type="number" min="0" step="0.01" value={line.unit_cost} onChange={(e) => setReceiptLine(index, { unit_cost: e.target.value })} /></Field>
                    <Button type="button" variant="ghost" className="text-red-600" onClick={() => removeReceiptLine(index)}><Trash2 className="h-4 w-4" /></Button>
                  </div>
                ))}
                {receiptForm.lines.length === 0 ? <p className="text-sm text-slate-400">No lines added yet.</p> : null}
              </div>
            </div>
          )}
          <Field label="Notes"><Textarea value={receiptForm.notes} onChange={(e) => setReceiptForm((f) => ({ ...f, notes: e.target.value }))} /></Field>
        </form>
      </Modal>

      <ConfirmDialog
        open={Boolean(postTarget)}
        onClose={() => setPostTarget(null)}
        onConfirm={postReceipt}
        title="Post goods receipt"
        message={`Post ${postTarget?.number}? This increases on-hand stock and cannot be undone.`}
        confirmLabel="Post receipt"
        loading={posting}
      />

      {/* Putaway complete */}
      <Modal
        open={Boolean(putawayTarget)}
        onClose={() => setPutawayTarget(null)}
        title={`Put away — ${putawayTarget?.sku || ''}`}
        size="sm"
        footer={
          <>
            <Button variant="outline" onClick={() => setPutawayTarget(null)}>Cancel</Button>
            <Button form="putaway-form" type="submit">Complete</Button>
          </>
        }
      >
        <form id="putaway-form" onSubmit={completePutaway} className="space-y-4">
          <Field label="Destination location" required>
            <Select value={putawayForm.to_location_id} onChange={(e) => setPutawayForm((f) => ({ ...f, to_location_id: e.target.value }))} required>
              <option value="">Select location</option>
              {(putawayLocations || []).filter((l) => l.location_type !== 'receiving').map((l) => (
                <option key={l.id} value={l.id}>{l.code}</option>
              ))}
            </Select>
          </Field>
          <Field label="Quantity" hint={`Task quantity: ${formatQty(putawayTarget?.quantity)}`}>
            <Input type="number" min="0" step="0.01" value={putawayForm.quantity} onChange={(e) => setPutawayForm((f) => ({ ...f, quantity: e.target.value }))} />
          </Field>
        </form>
      </Modal>
    </div>
  );
}
