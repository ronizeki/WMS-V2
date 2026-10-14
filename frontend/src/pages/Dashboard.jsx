import React from 'react';
import {
  AlertTriangle,
  ArrowDownToLine,
  ArrowUpFromLine,
  Boxes,
  Building2,
  ClipboardList,
  Package,
  ShoppingCart,
  Truck,
  Wallet,
} from 'lucide-react';
import { Link } from 'react-router-dom';
import { useApiResource } from '../hooks/useApi';
import { PageHeader } from '../components/common/PageHeader';
import { StatCard } from '../components/common/StatCard';
import { ErrorState, LoadingState } from '../components/common/States';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge, StatusBadge } from '../components/ui/primitives';
import { DataTable } from '../components/common/DataTable';
import { formatCurrency, formatDateTime, formatQty, relativeTime } from '../lib/format';
import { MOVEMENT_TYPES } from '../lib/constants';

const movementTones = {
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

const movementLabels = MOVEMENT_TYPES.reduce((acc, key) => {
  acc[key] = key.replace(/_/g, ' ');
  return acc;
}, {});

export default function Dashboard() {
  const { data, loading, error, refetch } = useApiResource('/dashboard');

  if (loading && !data) return <LoadingState label="Loading dashboard…" />;
  if (error) return <ErrorState error={error} onRetry={refetch} />;

  const kpis = data?.kpis || {};
  const stockByWarehouse = data?.stock_by_warehouse || [];
  const lowStock = data?.low_stock_items || [];
  const movements = data?.recent_movements || [];
  const activity = data?.recent_activity || [];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Dashboard"
        description="A live snapshot of inventory, orders and warehouse activity."
      />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Inventory value" value={formatCurrency(kpis.inventory_value)} icon={Wallet} tone="green" loading={loading} />
        <StatCard
          label="Units on hand"
          value={formatQty(kpis.total_on_hand)}
          sublabel={`${formatQty(kpis.total_available)} available`}
          icon={Boxes}
          tone="blue"
          loading={loading}
        />
        <StatCard label="Active products" value={kpis.total_products ?? 0} icon={Package} tone="indigo" loading={loading} />
        <StatCard
          label="Low stock items"
          value={kpis.low_stock_count ?? 0}
          sublabel="At or below reorder point"
          icon={AlertTriangle}
          tone="amber"
          loading={loading}
        />
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Open orders" value={kpis.open_orders ?? 0} sublabel={formatCurrency(kpis.open_order_value)} icon={ShoppingCart} tone="purple" />
        <StatCard label="Pending receipts" value={kpis.pending_receipts ?? 0} icon={ArrowDownToLine} tone="blue" />
        <StatCard label="Open picking tasks" value={kpis.open_picking_tasks ?? 0} icon={ClipboardList} tone="indigo" />
        <StatCard label="Shipments in transit" value={kpis.shipments_in_transit ?? 0} icon={Truck} tone="amber" />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="text-base">Stock by warehouse</CardTitle>
          </CardHeader>
          <CardContent className="px-0 pb-0">
            <DataTable
              columns={[
                {
                  key: 'name',
                  header: 'Warehouse',
                  render: (row) => (
                    <div>
                      <p className="font-medium text-slate-800">{row.name}</p>
                      <p className="text-xs text-slate-400">{row.code}</p>
                    </div>
                  ),
                },
                { key: 'on_hand', header: 'On hand', className: 'text-right', render: (row) => formatQty(row.on_hand) },
                { key: 'available', header: 'Available', className: 'text-right', render: (row) => formatQty(row.available) },
                { key: 'value', header: 'Value', className: 'text-right', render: (row) => formatCurrency(row.value) },
              ]}
              rows={stockByWarehouse}
              loading={loading}
              emptyTitle="No warehouses yet"
              emptyMessage="Create a warehouse to start tracking inventory."
              skeletonRows={2}
            />
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0">
            <CardTitle className="text-base">Low stock</CardTitle>
            <Link to="/reports" className="text-xs font-medium text-blue-600 hover:underline">
              View report
            </Link>
          </CardHeader>
          <CardContent className="space-y-3">
            {lowStock.length === 0 ? (
              <p className="py-6 text-center text-sm text-slate-400">All products are above their reorder point.</p>
            ) : (
              lowStock.map((item) => (
                <div key={item.product_id} className="flex items-center justify-between gap-2">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-slate-700">{item.name}</p>
                    <p className="text-xs text-slate-400">{item.sku}</p>
                  </div>
                  <div className="text-right">
                    <p className="text-sm font-semibold text-amber-600">{formatQty(item.available)}</p>
                    <p className="text-xs text-slate-400">RP {formatQty(item.reorder_point)}</p>
                  </div>
                </div>
              ))
            )}
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Recent stock movements</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {movements.length === 0 ? (
              <p className="py-6 text-center text-sm text-slate-400">No stock movements recorded yet.</p>
            ) : (
              movements.map((m) => (
                <div key={m.id} className="flex items-center justify-between gap-3">
                  <div className="flex items-center gap-2">
                    {Number(m.quantity) >= 0 ? (
                      <ArrowDownToLine className="h-4 w-4 text-emerald-500" />
                    ) : (
                      <ArrowUpFromLine className="h-4 w-4 text-red-500" />
                    )}
                    <div>
                      <p className="text-sm font-medium text-slate-700">{m.product_name || m.sku}</p>
                      <p className="text-xs text-slate-400">{formatDateTime(m.created_at)}</p>
                    </div>
                  </div>
                  <div className="text-right">
                    <Badge tone={movementTones[m.movement_type] || 'slate'}>{movementLabels[m.movement_type] || m.movement_type}</Badge>
                    <p className={`mt-1 text-sm font-semibold ${Number(m.quantity) >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>
                      {Number(m.quantity) >= 0 ? '+' : ''}
                      {formatQty(m.quantity)}
                    </p>
                  </div>
                </div>
              ))
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Recent activity</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {activity.length === 0 ? (
              <p className="py-6 text-center text-sm text-slate-400">No activity recorded yet.</p>
            ) : (
              activity.map((log) => (
                <div key={log.id} className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-sm text-slate-700">
                      <span className="font-medium capitalize">{log.action?.replace(/_/g, ' ')}</span>{' '}
                      {log.entity_type?.replace(/_/g, ' ')}
                    </p>
                    <p className="text-xs text-slate-400">
                      {log.user_name || 'system'} · {relativeTime(log.created_at)}
                    </p>
                  </div>
                  <StatusBadge value={log.entity_type} tones={{}} />
                </div>
              ))
            )}
          </CardContent>
        </Card>
      </div>

      <div className="flex flex-wrap gap-3">
        <Link to="/receiving" className="inline-flex items-center gap-2 rounded-md border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50">
          <Building2 className="h-4 w-4" /> Receive goods
        </Link>
        <Link to="/orders" className="inline-flex items-center gap-2 rounded-md border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50">
          <ShoppingCart className="h-4 w-4" /> Create order
        </Link>
        <Link to="/stocktake" className="inline-flex items-center gap-2 rounded-md border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50">
          <ClipboardList className="h-4 w-4" /> Start stocktake
        </Link>
      </div>
    </div>
  );
}
