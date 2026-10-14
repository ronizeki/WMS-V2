import React, { useState } from 'react';
import { AlertTriangle, BarChart3, Boxes, TrendingDown, TrendingUp, Truck, Download } from 'lucide-react';
import { useApiResource } from '../hooks/useApi';
import { PageHeader } from '../components/common/PageHeader';
import { StatCard } from '../components/common/StatCard';
import { DataTable } from '../components/common/DataTable';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Tabs } from '../components/ui/tabs';
import { Select } from '../components/ui/form';
import { Badge } from '../components/ui/primitives';
import { Button } from '../components/ui/button';
import { formatCurrency, formatDateTime, formatQty, titleCase } from '../lib/format';

export default function Reports() {
  const [tab, setTab] = useState('inventory-value');
  const [warehouseId, setWarehouseId] = useState('');
  const [days, setDays] = useState(30);

  const { data: warehouses } = useApiResource('/warehouses', { page_size: 100 });

  const inventoryValue = useApiResource(tab === 'inventory-value' ? '/reports/inventory-value' : null, { warehouse_id: warehouseId || undefined });
  const movements = useApiResource(tab === 'movements' ? '/reports/stock-movements' : null, { days, warehouse_id: warehouseId || undefined });
  const fulfillment = useApiResource(tab === 'fulfillment' ? '/reports/fulfillment' : null, { days });
  const lowStock = useApiResource(tab === 'low-stock' ? '/reports/low-stock' : null, { warehouse_id: warehouseId || undefined });

  const exportCsv = (rows, filename) => {
    if (!rows || !rows.length) return;
    const headers = Object.keys(rows[0]);
    const csv = [
      headers.join(','),
      ...rows.map((row) => headers.map((h) => `"${String(row[h] ?? '').replace(/"/g, '""')}"`).join(',')),
    ].join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    link.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-6">
      <PageHeader title="Reports" description="Valuation, movement, fulfilment and replenishment insights." />

      <Card>
        <Tabs
          value={tab}
          onChange={setTab}
          tabs={[
            { value: 'inventory-value', label: 'Inventory value', icon: Boxes },
            { value: 'movements', label: 'Stock movements', icon: BarChart3 },
            { value: 'fulfillment', label: 'Fulfilment', icon: Truck },
            { value: 'low-stock', label: 'Low stock', icon: AlertTriangle },
          ]}
        />
        <div className="flex flex-wrap gap-3 p-4">
          {['inventory-value', 'movements', 'low-stock'].includes(tab) ? (
            <Select value={warehouseId} onChange={(e) => setWarehouseId(e.target.value)} className="sm:w-64">
              <option value="">All warehouses</option>
              {(warehouses || []).map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
            </Select>
          ) : null}
          {['movements', 'fulfillment'].includes(tab) ? (
            <Select value={days} onChange={(e) => setDays(Number(e.target.value))} className="sm:w-40">
              <option value={7}>Last 7 days</option>
              <option value={30}>Last 30 days</option>
              <option value={90}>Last 90 days</option>
              <option value={365}>Last year</option>
            </Select>
          ) : null}
        </div>
      </Card>

      {tab === 'inventory-value' ? (
        <div className="space-y-6">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <StatCard label="Total inventory value" value={formatCurrency(inventoryValue.data?.total_value)} icon={Boxes} tone="green" loading={inventoryValue.loading} />
            <StatCard label="Total units on hand" value={formatQty(inventoryValue.data?.total_on_hand)} icon={BarChart3} tone="blue" loading={inventoryValue.loading} />
          </div>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0">
              <CardTitle className="text-base">Value by product</CardTitle>
              <Button variant="outline" size="sm" onClick={() => exportCsv(inventoryValue.data?.by_product, 'inventory-value.csv')}>
                <Download className="mr-1.5 h-3.5 w-3.5" /> Export CSV
              </Button>
            </CardHeader>
            <CardContent className="px-0 pb-0">
              <DataTable
                columns={[
                  { key: 'sku', header: 'SKU' },
                  { key: 'product_name', header: 'Product' },
                  { key: 'on_hand', header: 'On hand', className: 'text-right', render: (r) => formatQty(r.on_hand) },
                  { key: 'average_cost', header: 'Avg cost', className: 'text-right', render: (r) => formatCurrency(r.average_cost) },
                  { key: 'value', header: 'Value', className: 'text-right', render: (r) => formatCurrency(r.value) },
                  { key: 'locations', header: 'Locations', className: 'text-right', render: (r) => r.locations },
                ]}
                rows={inventoryValue.data?.by_product}
                loading={inventoryValue.loading}
                error={inventoryValue.error}
                onRetry={inventoryValue.refetch}
                emptyTitle="No inventory value yet"
              />
            </CardContent>
          </Card>
        </div>
      ) : null}

      {tab === 'movements' ? (
        <div className="space-y-6">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <StatCard label="Entries" value={movements.data?.entry_count ?? 0} icon={BarChart3} tone="indigo" loading={movements.loading} />
            <StatCard label="Total in" value={formatQty(movements.data?.total_in)} icon={TrendingUp} tone="green" loading={movements.loading} />
            <StatCard label="Total out" value={formatQty(movements.data?.total_out)} icon={TrendingDown} tone="red" loading={movements.loading} />
          </div>

          {movements.data?.by_movement_type ? (
            <Card>
              <CardHeader><CardTitle className="text-base">By movement type</CardTitle></CardHeader>
              <CardContent className="flex flex-wrap gap-2">
                {Object.entries(movements.data.by_movement_type).map(([type, value]) => (
                  <Badge key={type} tone={Number(value.quantity) >= 0 ? 'green' : 'red'}>
                    {titleCase(type)}: {value.count} ({formatQty(value.quantity)})
                  </Badge>
                ))}
              </CardContent>
            </Card>
          ) : null}

          <Card>
            <CardHeader><CardTitle className="text-base">Recent entries</CardTitle></CardHeader>
            <CardContent className="px-0 pb-0">
              <DataTable
                columns={[
                  { key: 'created_at', header: 'When', render: (r) => formatDateTime(r.created_at) },
                  { key: 'product_name', header: 'Product', render: (r) => r.product_name || r.sku },
                  { key: 'movement_type', header: 'Type', render: (r) => titleCase(r.movement_type) },
                  { key: 'quantity', header: 'Qty', className: 'text-right', render: (r) => (<span className={Number(r.quantity) >= 0 ? 'text-emerald-600' : 'text-red-600'}>{formatQty(r.quantity)}</span>) },
                  { key: 'quantity_after', header: 'After', className: 'text-right', render: (r) => formatQty(r.quantity_after) },
                ]}
                rows={movements.data?.entries}
                loading={movements.loading}
                error={movements.error}
                onRetry={movements.refetch}
                emptyTitle="No movements in this period"
              />
            </CardContent>
          </Card>
        </div>
      ) : null}

      {tab === 'fulfillment' ? (
        <div className="space-y-6">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard label="Fulfilment rate" value={`${fulfillment.data?.fulfillment_rate ?? 0}%`} icon={TrendingUp} tone="green" loading={fulfillment.loading} />
            <StatCard label="Orders" value={fulfillment.data?.orders_total ?? 0} icon={Truck} tone="blue" loading={fulfillment.loading} />
            <StatCard label="Shipped orders" value={fulfillment.data?.orders_shipped ?? 0} icon={Truck} tone="indigo" loading={fulfillment.loading} />
            <StatCard label="In transit" value={fulfillment.data?.shipments_in_transit ?? 0} icon={Truck} tone="amber" loading={fulfillment.loading} />
          </div>
          <Card>
            <CardHeader><CardTitle className="text-base">Orders by status</CardTitle></CardHeader>
            <CardContent className="flex flex-wrap gap-2">
              {Object.entries(fulfillment.data?.orders_by_status || {}).map(([status, count]) => (
                <Badge key={status} tone="blue">{titleCase(status)}: {count}</Badge>
              ))}
              {Object.keys(fulfillment.data?.orders_by_status || {}).length === 0 ? (
                <p className="text-sm text-slate-400">No orders in this period.</p>
              ) : null}
            </CardContent>
          </Card>
        </div>
      ) : null}

      {tab === 'low-stock' ? (
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0">
            <CardTitle className="text-base">Replenishment list</CardTitle>
            <Button variant="outline" size="sm" onClick={() => exportCsv(lowStock.data?.items, 'low-stock.csv')}>
              <Download className="mr-1.5 h-3.5 w-3.5" /> Export CSV
            </Button>
          </CardHeader>
          <CardContent className="px-0 pb-0">
            <DataTable
              columns={[
                { key: 'sku', header: 'SKU' },
                { key: 'name', header: 'Product' },
                { key: 'available', header: 'Available', className: 'text-right', render: (r) => <span className="font-semibold text-amber-600">{formatQty(r.available)}</span> },
                { key: 'reorder_point', header: 'Reorder point', className: 'text-right', render: (r) => formatQty(r.reorder_point) },
                { key: 'shortfall', header: 'Shortfall', className: 'text-right', render: (r) => formatQty(r.shortfall) },
                { key: 'reorder_quantity', header: 'Suggested qty', className: 'text-right', render: (r) => formatQty(r.reorder_quantity) },
              ]}
              rows={lowStock.data?.items}
              loading={lowStock.loading}
              error={lowStock.error}
              onRetry={lowStock.refetch}
              emptyTitle="Everything is above the reorder point"
            />
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}
