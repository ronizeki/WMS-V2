import React, { useMemo, useState } from 'react';
import { ArrowDownToLine, ArrowUpFromLine, Check, ClipboardList, Layers, Plus, X } from 'lucide-react';
import api from '../lib/api';
import { useApiResource, useDebounced } from '../hooks/useApi';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../components/ui/toaster';
import { PageHeader } from '../components/common/PageHeader';
import { DataTable, Pagination } from '../components/common/DataTable';
import { SearchInput, Toolbar } from '../components/common/Toolbar';
import { Button } from '../components/ui/button';
import { Card } from '../components/ui/card';
import { Tabs } from '../components/ui/tabs';
import { Field, Input, Select, Textarea, Checkbox } from '../components/ui/form';
import { Modal } from '../components/ui/modal';
import { Badge, StatusBadge } from '../components/ui/primitives';
import { ProductPicker } from '../components/common/ProductPicker';
import { formatCurrency, formatDateTime, formatQty, titleCase } from '../lib/format';
import { ADJUSTMENT_REASONS, STATUS_TONES } from '../lib/constants';

const MOVEMENT_TONES = {
  inbound_receipt: 'green',
  outbound_shipment: 'red',
  transfer_in: 'blue',
  transfer_out: 'indigo',
  adjustment_in: 'green',
  adjustment_out: 'red',
  cycle_count_adjustment: 'amber',
  damaged: 'red',
  putaway: 'slate',
};

export default function Inventory() {
  const { hasPermission } = useAuth();
  const toast = useToast();
  const [tab, setTab] = useState('summary');
  const [search, setSearch] = useState('');
  const [warehouseId, setWarehouseId] = useState('');
  const [page, setPage] = useState(1);
  const debounced = useDebounced(search);

  const { data: warehouses } = useApiResource('/warehouses', { page_size: 100 });

  const commonParams = useMemo(
    () => ({ search: debounced || undefined, warehouse_id: warehouseId || undefined, page, page_size: 20 }),
    [debounced, warehouseId, page]
  );

  const summary = useApiResource(tab === 'summary' ? '/inventory/summary' : null, commonParams);
  const balances = useApiResource(tab === 'balances' ? '/inventory/balances' : null, { ...commonParams, include_zero: true });
  const adjustments = useApiResource(tab === 'adjustments' ? '/inventory/adjustments' : null, { warehouse_id: warehouseId || undefined, page, page_size: 20 });
  const ledger = useApiResource(tab === 'ledger' ? '/inventory/ledger' : null, commonParams);

  const active = { summary, balances, adjustments, ledger }[tab];

  const [adjustOpen, setAdjustOpen] = useState(false);
  const [adjustForm, setAdjustForm] = useState({
    product: null,
    warehouse_id: '',
    location_id: '',
    adjustment_type: 'increase',
    quantity: '',
    unit_cost: '',
    reason: 'other',
    reason_notes: '',
    confirmed: false,
  });
  const [saving, setSaving] = useState(false);

  const { data: locations } = useApiResource(
    adjustForm.warehouse_id ? `/warehouses/${adjustForm.warehouse_id}/locations` : null,
    { page_size: 200 }
  );

  const openAdjust = () => {
    setAdjustForm({
      product: null,
      warehouse_id: warehouses?.[0]?.id || '',
      location_id: '',
      adjustment_type: 'increase',
      quantity: '',
      unit_cost: '',
      reason: 'other',
      reason_notes: '',
      confirmed: false,
    });
    setAdjustOpen(true);
  };

  const submitAdjustment = async (event) => {
    event.preventDefault();
    if (!adjustForm.product || !adjustForm.warehouse_id || !adjustForm.location_id || !adjustForm.quantity) {
      toast.error('Missing details', 'Product, warehouse, location and quantity are required.');
      return;
    }
    setSaving(true);
    try {
      const result = await api.post('/inventory/adjustments', {
        product_id: adjustForm.product.id,
        warehouse_id: adjustForm.warehouse_id,
        location_id: adjustForm.location_id,
        adjustment_type: adjustForm.adjustment_type,
        quantity: Number(adjustForm.quantity),
        unit_cost: Number(adjustForm.unit_cost) || 0,
        reason: adjustForm.reason,
        reason_notes: adjustForm.reason_notes || undefined,
      });
      if (result.status === 'pending_approval') {
        toast.info('Adjustment submitted', 'It is awaiting approval before stock changes.');
      } else {
        toast.success('Stock adjusted');
      }
      setAdjustOpen(false);
      summary.refetch();
      balances.refetch();
      adjustments.refetch();
      ledger.refetch();
    } catch (e) {
      toast.error('Adjustment failed', e.message);
    } finally {
      setSaving(false);
    }
  };

  const reviewAdjustment = async (id, action) => {
    try {
      await api.post(`/inventory/adjustments/${id}/${action}`, action === 'reject' ? { reason: 'Rejected' } : undefined);
      toast.success(action === 'approve' ? 'Adjustment approved' : 'Adjustment rejected');
      adjustments.refetch();
      summary.refetch();
    } catch (e) {
      toast.error('Action failed', e.message);
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Inventory"
        description="Live stock positions, valuation and the immutable movement ledger."
        actions={
          hasPermission('inventory:adjust') ? (
            <Button onClick={openAdjust}>
              <Plus className="mr-2 h-4 w-4" /> Adjust stock
            </Button>
          ) : null
        }
      />

      <Card>
        <Tabs
          value={tab}
          onChange={(v) => { setTab(v); setPage(1); }}
          tabs={[
            { value: 'summary', label: 'Summary', icon: Layers },
            { value: 'balances', label: 'By location', icon: ClipboardList },
            { value: 'adjustments', label: 'Adjustments', icon: ArrowUpFromLine },
            { value: 'ledger', label: 'Ledger', icon: ArrowDownToLine },
          ]}
        />

        <Toolbar>
          {tab !== 'adjustments' ? (
            <SearchInput value={search} onChange={(v) => { setSearch(v); setPage(1); }} placeholder="Search SKU or product…" className="sm:max-w-xs" />
          ) : <div className="flex-1" />}
          <Select value={warehouseId} onChange={(e) => { setWarehouseId(e.target.value); setPage(1); }} className="sm:w-56">
            <option value="">All warehouses</option>
            {(warehouses || []).map((w) => (
              <option key={w.id} value={w.id}>{w.name}</option>
            ))}
          </Select>
        </Toolbar>

        {tab === 'summary' ? (
          <DataTable
            columns={[
              { key: 'sku', header: 'Product', render: (r) => (<div><p className="font-medium text-slate-800">{r.sku}</p><p className="text-xs text-slate-500">{r.product_name}</p></div>) },
              { key: 'on_hand', header: 'On hand', className: 'text-right', render: (r) => formatQty(r.on_hand) },
              { key: 'reserved', header: 'Reserved', className: 'text-right', render: (r) => formatQty(r.reserved) },
              { key: 'available', header: 'Available', className: 'text-right', render: (r) => <span className="font-semibold">{formatQty(r.available)}</span> },
              { key: 'reorder_point', header: 'Reorder at', className: 'text-right', render: (r) => formatQty(r.reorder_point) },
              { key: 'value', header: 'Value', className: 'text-right', render: (r) => formatCurrency(r.value) },
              { key: 'is_low_stock', header: 'Status', render: (r) => r.is_low_stock ? <Badge tone="amber">Low</Badge> : <Badge tone="green">OK</Badge> },
            ]}
            rows={summary.data}
            loading={summary.loading}
            error={summary.error}
            onRetry={summary.refetch}
            emptyTitle="No inventory yet"
            emptyMessage="Receive stock to see inventory positions."
          />
        ) : null}

        {tab === 'balances' ? (
          <DataTable
            columns={[
              { key: 'sku', header: 'Product', render: (r) => (<div><p className="font-medium text-slate-800">{r.sku}</p><p className="text-xs text-slate-500">{r.product_name}</p></div>) },
              { key: 'location_id', header: 'Location', render: (r) => r.location_code || r.location_id },
              { key: 'quantity_on_hand', header: 'On hand', className: 'text-right', render: (r) => formatQty(r.quantity_on_hand) },
              { key: 'quantity_reserved', header: 'Reserved', className: 'text-right', render: (r) => formatQty(r.quantity_reserved) },
              { key: 'quantity_available', header: 'Available', className: 'text-right', render: (r) => formatQty(r.quantity_available) },
              { key: 'quantity_damaged', header: 'Damaged', className: 'text-right', render: (r) => formatQty(r.quantity_damaged) },
              { key: 'total_value', header: 'Value', className: 'text-right', render: (r) => formatCurrency(r.total_value) },
            ]}
            rows={balances.data}
            loading={balances.loading}
            error={balances.error}
            onRetry={balances.refetch}
            emptyTitle="No stock at any location"
          />
        ) : null}

        {tab === 'adjustments' ? (
          <DataTable
            columns={[
              { key: 'number', header: 'Reference', render: (r) => <span className="font-medium text-slate-800">{r.number}</span> },
              { key: 'product_name', header: 'Product', render: (r) => (<div><p className="text-slate-700">{r.product_name}</p><p className="text-xs text-slate-400">{r.sku}</p></div>) },
              { key: 'adjustment_type', header: 'Type', render: (r) => titleCase(r.adjustment_type) },
              { key: 'quantity', header: 'Qty', className: 'text-right', render: (r) => formatQty(r.quantity) },
              { key: 'status', header: 'Status', render: (r) => <StatusBadge value={r.status} tones={STATUS_TONES} /> },
              { key: 'created_at', header: 'Created', render: (r) => formatDateTime(r.created_at) },
              {
                key: 'actions',
                header: '',
                className: 'text-right',
                render: (r) =>
                  hasPermission('inventory:approve') && !r.posted && r.status === 'pending_approval' ? (
                    <div className="flex justify-end gap-2">
                      <Button size="sm" variant="outline" onClick={() => reviewAdjustment(r.id, 'approve')}><Check className="h-4 w-4" /></Button>
                      <Button size="sm" variant="ghost" className="text-red-600" onClick={() => reviewAdjustment(r.id, 'reject')}><X className="h-4 w-4" /></Button>
                    </div>
                  ) : null,
              },
            ]}
            rows={adjustments.data}
            loading={adjustments.loading}
            error={adjustments.error}
            onRetry={adjustments.refetch}
            emptyTitle="No adjustments recorded"
          />
        ) : null}

        {tab === 'ledger' ? (
          <DataTable
            columns={[
              { key: 'created_at', header: 'When', render: (r) => formatDateTime(r.created_at) },
              { key: 'product_name', header: 'Product', render: (r) => (<div><p className="text-slate-700">{r.product_name || r.sku}</p><p className="text-xs text-slate-400">{r.reference_number || ''}</p></div>) },
              { key: 'movement_type', header: 'Type', render: (r) => <Badge tone={MOVEMENT_TONES[r.movement_type] || 'slate'}>{titleCase(r.movement_type)}</Badge> },
              { key: 'quantity', header: 'Qty', className: 'text-right', render: (r) => (<span className={Number(r.quantity) >= 0 ? 'text-emerald-600' : 'text-red-600'}>{Number(r.quantity) >= 0 ? '+' : ''}{formatQty(r.quantity)}</span>) },
              { key: 'quantity_after', header: 'Balance after', className: 'text-right', render: (r) => formatQty(r.quantity_after) },
            ]}
            rows={ledger.data}
            loading={ledger.loading}
            error={ledger.error}
            onRetry={ledger.refetch}
            emptyTitle="No stock movements yet"
          />
        ) : null}

        {active && active.meta ? <Pagination meta={active.meta} onPageChange={setPage} /> : null}
      </Card>

      <Modal
        open={adjustOpen}
        onClose={() => setAdjustOpen(false)}
        title="Adjust stock"
        description="Record a correction, damage or found stock. Every adjustment produces a ledger entry."
        size="md"
        footer={
          <>
            <Button variant="outline" onClick={() => setAdjustOpen(false)} disabled={saving}>Cancel</Button>
            <Button form="adjust-form" type="submit" disabled={saving}>{saving ? 'Posting…' : 'Post adjustment'}</Button>
          </>
        }
      >
        <form id="adjust-form" onSubmit={submitAdjustment} className="space-y-4">
          <Field label="Product" required>
            <ProductPicker selected={adjustForm.product} onChange={(p) => setAdjustForm((f) => ({ ...f, product: p }))} />
          </Field>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Field label="Warehouse" required>
              <Select
                value={adjustForm.warehouse_id}
                onChange={(e) => setAdjustForm((f) => ({ ...f, warehouse_id: e.target.value, location_id: '' }))}
                required
              >
                <option value="">Select warehouse</option>
                {(warehouses || []).map((w) => (
                  <option key={w.id} value={w.id}>{w.name}</option>
                ))}
              </Select>
            </Field>
            <Field label="Location" required>
              <Select
                value={adjustForm.location_id}
                onChange={(e) => setAdjustForm((f) => ({ ...f, location_id: e.target.value }))}
                required
                disabled={!adjustForm.warehouse_id}
              >
                <option value="">Select location</option>
                {(locations || []).map((l) => (
                  <option key={l.id} value={l.id}>{l.code}</option>
                ))}
              </Select>
            </Field>
            <Field label="Adjustment type" required>
              <Select value={adjustForm.adjustment_type} onChange={(e) => setAdjustForm((f) => ({ ...f, adjustment_type: e.target.value }))}>
                <option value="increase">Increase</option>
                <option value="decrease">Decrease</option>
                <option value="set">Set to exact quantity</option>
              </Select>
            </Field>
            <Field label="Quantity" required>
              <Input type="number" min="0" step="0.01" required value={adjustForm.quantity} onChange={(e) => setAdjustForm((f) => ({ ...f, quantity: e.target.value }))} />
            </Field>
            <Field label="Unit cost">
              <Input type="number" min="0" step="0.01" value={adjustForm.unit_cost} onChange={(e) => setAdjustForm((f) => ({ ...f, unit_cost: e.target.value }))} />
            </Field>
            <Field label="Reason" required>
              <Select value={adjustForm.reason} onChange={(e) => setAdjustForm((f) => ({ ...f, reason: e.target.value }))}>
                {ADJUSTMENT_REASONS.map((r) => (
                  <option key={r} value={r}>{titleCase(r)}</option>
                ))}
              </Select>
            </Field>
          </div>
          <Field label="Notes">
            <Textarea value={adjustForm.reason_notes} onChange={(e) => setAdjustForm((f) => ({ ...f, reason_notes: e.target.value }))} />
          </Field>
          <Checkbox
            label="I understand this directly changes on-hand stock and is recorded in the ledger."
            checked={adjustForm.confirmed}
            onChange={(e) => setAdjustForm((f) => ({ ...f, confirmed: e.target.checked }))}
          />
        </form>
      </Modal>
    </div>
  );
}
