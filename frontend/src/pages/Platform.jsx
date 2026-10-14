import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Building2, Boxes, Database, Plus, UserCog, Users } from 'lucide-react';
import api from '../lib/api';
import { useApiResource } from '../hooks/useApi';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../components/ui/toaster';
import { PageHeader } from '../components/common/PageHeader';
import { DataTable, Pagination } from '../components/common/DataTable';
import { Toolbar, SearchInput } from '../components/common/Toolbar';
import { StatCard } from '../components/common/StatCard';
import { Button } from '../components/ui/button';
import { Card } from '../components/ui/card';
import { Field, Input, Select } from '../components/ui/form';
import { Modal } from '../components/ui/modal';
import { StatusBadge } from '../components/ui/primitives';
import { formatDate, titleCase } from '../lib/format';
import { TENANT_STATUSES, STATUS_TONES } from '../lib/constants';

export default function Platform() {
  const { hasPermission, selectTenant } = useAuth();
  const navigate = useNavigate();
  const toast = useToast();
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState('');

  const stats = useApiResource('/platform/stats');
  const tenants = useApiResource('/platform/tenants', { page, page_size: 20, search: search || undefined, status: status || undefined });
  const plans = useApiResource('/platform/plans');

  const [createOpen, setCreateOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({
    name: '', code: '', owner_name: '', owner_email: '', owner_password: '',
    plan_code: '', timezone: 'Asia/Jakarta', currency: 'IDR',
  });

  const openCreate = () => {
    setForm({
      name: '', code: '', owner_name: '', owner_email: '', owner_password: '',
      plan_code: plans.data?.[0]?.code || '', timezone: 'Asia/Jakarta', currency: 'IDR',
    });
    setCreateOpen(true);
  };

  const submit = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      await api.post('/platform/tenants', {
        name: form.name,
        code: form.code.toUpperCase(),
        owner_name: form.owner_name,
        owner_email: form.owner_email,
        owner_password: form.owner_password,
        plan_code: form.plan_code || undefined,
        timezone: form.timezone,
        currency: form.currency,
      });
      toast.success('Tenant provisioned', `${form.name} is ready to use.`);
      setCreateOpen(false);
      tenants.refetch();
      stats.refetch();
    } catch (err) {
      toast.error('Could not provision tenant', err.message);
    } finally {
      setSaving(false);
    }
  };

  const setTenantStatus = async (tenant, nextStatus) => {
    try {
      await api.patch(`/platform/tenants/${tenant.id}`, { status: nextStatus });
      toast.success('Tenant updated', `${tenant.name} → ${titleCase(nextStatus)}`);
      tenants.refetch();
      stats.refetch();
    } catch (err) {
      toast.error('Could not update tenant', err.message);
    }
  };

  const manageUsers = async (tenant) => {
    try {
      await selectTenant(tenant.id);
      toast.success('Tenant context updated', `Managing users for ${tenant.name}`);
      navigate('/settings', { state: { tab: 'users', tenantName: tenant.name } });
    } catch (err) {
      toast.error('Could not open tenant users', err.message);
    }
  };

  const canManage = hasPermission('tenant:manage');

  return (
    <div className="space-y-6">
      <PageHeader
        title="Platform Administration"
        description="Cross-tenant visibility, provisioning and subscription plans."
        actions={
          canManage ? (
            <Button onClick={openCreate}><Plus className="mr-2 h-4 w-4" />Provision tenant</Button>
          ) : null
        }
      />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Tenants" value={stats.data?.tenants?.total ?? 0} icon={Building2} tone="blue" loading={stats.loading} sublabel={`${stats.data?.tenants?.demo ?? 0} demo`} />
        <StatCard label="Users" value={stats.data?.users ?? 0} icon={Users} tone="indigo" loading={stats.loading} />
        <StatCard label="Products" value={stats.data?.products ?? 0} icon={Boxes} tone="green" loading={stats.loading} />
        <StatCard label="Ledger entries" value={stats.data?.ledger_entries ?? 0} icon={Database} tone="amber" loading={stats.loading} sublabel={stats.data?.storage_backend} />
      </div>

      <Card>
        <Toolbar>
          <SearchInput value={search} onChange={(v) => { setSearch(v); setPage(1); }} placeholder="Search tenants…" className="sm:max-w-xs" />
          <Select value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }} className="sm:w-48">
            <option value="">All statuses</option>
            {TENANT_STATUSES.map((s) => <option key={s} value={s}>{titleCase(s)}</option>)}
          </Select>
        </Toolbar>

        <DataTable
          columns={[
            { key: 'name', header: 'Tenant', render: (r) => (<div><p className="font-medium text-slate-800">{r.name}</p><p className="text-xs text-slate-400">{r.code}</p></div>) },
            { key: 'users', header: 'Users', className: 'text-right', render: (r) => r.user_count ?? 0 },
            { key: 'warehouses', header: 'Warehouses', className: 'text-right', render: (r) => r.warehouse_count ?? 0 },
            { key: 'status', header: 'Status', render: (r) => <StatusBadge value={r.status} tones={STATUS_TONES} /> },
            { key: 'created_at', header: 'Created', render: (r) => formatDate(r.created_at) },
            {
              key: 'actions',
              header: '',
              className: 'text-right',
              render: (r) =>
                canManage ? (
                  <div className="flex justify-end gap-1">
                    <Button size="sm" variant="outline" onClick={() => manageUsers(r)}>
                      <UserCog className="mr-1.5 h-3.5 w-3.5" />Users
                    </Button>
                    {r.status !== 'active' ? (
                      <Button size="sm" variant="outline" onClick={() => setTenantStatus(r, 'active')}>Activate</Button>
                    ) : (
                      <Button size="sm" variant="outline" onClick={() => setTenantStatus(r, 'suspended')}>Suspend</Button>
                    )}
                  </div>
                ) : null,
            },
          ]}
          rows={tenants.data}
          loading={tenants.loading}
          error={tenants.error}
          onRetry={tenants.refetch}
          emptyTitle="No tenants"
          emptyMessage="Provision the first tenant to get started."
          emptyAction={canManage ? <Button onClick={openCreate}><Plus className="mr-2 h-4 w-4" />Provision tenant</Button> : null}
        />
        <Pagination meta={tenants.meta} onPageChange={setPage} />
      </Card>

      <Card className="p-4">
        <p className="mb-3 text-sm font-semibold text-slate-700">Subscription plans</p>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {(plans.data || []).map((plan) => (
            <div key={plan.id} className="rounded-lg border border-slate-200 p-4">
              <div className="flex items-center justify-between">
                <p className="font-medium text-slate-800">{plan.name}</p>
                <span className="text-sm font-semibold text-slate-700">
                  {plan.is_free ? 'Free' : `${plan.currency || 'IDR'} ${plan.price}`}
                </span>
              </div>
              <p className="mt-1 text-xs text-slate-400">{plan.code} · {plan.billing_cycle}</p>
              <ul className="mt-2 space-y-0.5 text-xs text-slate-500">
                <li>{plan.max_users} users · {plan.max_warehouses} warehouses</li>
                <li>{plan.max_products} products · {plan.max_locations} locations</li>
                <li>{plan.storage_gb} GB storage · {plan.api_calls_monthly} API calls/mo</li>
              </ul>
            </div>
          ))}
          {(plans.data || []).length === 0 ? <p className="text-sm text-slate-400">No plans configured.</p> : null}
        </div>
      </Card>

      <Modal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        title="Provision tenant"
        description="Creates the tenant, an owner account and a subscription."
        size="md"
        footer={
          <>
            <Button variant="outline" onClick={() => setCreateOpen(false)} disabled={saving}>Cancel</Button>
            <Button form="tenant-form" type="submit" disabled={saving}>{saving ? 'Provisioning…' : 'Provision tenant'}</Button>
          </>
        }
      >
        <form id="tenant-form" onSubmit={submit} className="space-y-4">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Field label="Organization name" required><Input value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} required /></Field>
            <Field label="Tenant code" required hint="Short uppercase code, e.g. ACME."><Input value={form.code} onChange={(e) => setForm((f) => ({ ...f, code: e.target.value }))} required /></Field>
            <Field label="Owner name" required><Input value={form.owner_name} onChange={(e) => setForm((f) => ({ ...f, owner_name: e.target.value }))} required /></Field>
            <Field label="Owner email" required><Input type="email" value={form.owner_email} onChange={(e) => setForm((f) => ({ ...f, owner_email: e.target.value }))} required /></Field>
            <Field label="Owner password" required hint="At least 8 characters."><Input type="text" value={form.owner_password} onChange={(e) => setForm((f) => ({ ...f, owner_password: e.target.value }))} required /></Field>
            <Field label="Plan">
              <Select value={form.plan_code} onChange={(e) => setForm((f) => ({ ...f, plan_code: e.target.value }))}>
                <option value="">Default plan</option>
                {(plans.data || []).map((p) => <option key={p.id} value={p.code}>{p.name}</option>)}
              </Select>
            </Field>
            <Field label="Timezone"><Input value={form.timezone} onChange={(e) => setForm((f) => ({ ...f, timezone: e.target.value }))} /></Field>
            <Field label="Currency"><Input value={form.currency} onChange={(e) => setForm((f) => ({ ...f, currency: e.target.value }))} /></Field>
          </div>
        </form>
      </Modal>
    </div>
  );
}
