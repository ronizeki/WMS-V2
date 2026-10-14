import React, { useState } from 'react';
import { Building2, MapPin, MoreHorizontal, Pencil, Plus, Trash2 } from 'lucide-react';
import api from '../lib/api';
import { useApiResource } from '../hooks/useApi';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../components/ui/toaster';
import { PageHeader } from '../components/common/PageHeader';
import { DataTable, Pagination } from '../components/common/DataTable';
import { Button } from '../components/ui/button';
import { Card } from '../components/ui/card';
import { Field, Input, Select, Checkbox } from '../components/ui/form';
import { Modal, ConfirmDialog } from '../components/ui/modal';
import { DropdownItem, DropdownMenu } from '../components/ui/dropdown';
import { StatusBadge } from '../components/ui/primitives';
import { LOCATION_TYPES, LOCATION_STATUSES, WAREHOUSE_STATUSES, STATUS_TONES } from '../lib/constants';

const emptyWarehouse = {
  code: '',
  name: '',
  status: 'active',
  timezone: 'Asia/Jakarta',
  address: '',
  city: '',
  province: '',
  postal_code: '',
  country: 'Indonesia',
  phone: '',
  is_default: false,
};

export default function Warehouses() {
  const { hasPermission } = useAuth();
  const toast = useToast();
  const canWrite = hasPermission('warehouse:write');

  const [page, setPage] = useState(1);
  const { data, meta, loading, error, refetch } = useApiResource('/warehouses', { page, page_size: 20 });

  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(emptyWarehouse);
  const [saving, setSaving] = useState(false);

  const [manageTarget, setManageTarget] = useState(null);
  const [locationForm, setLocationForm] = useState({ code: '', zone_id: '', location_type: 'storage', status: 'available' });
  const [zoneForm, setZoneForm] = useState({ code: '', name: '' });
  const [deleteTarget, setDeleteTarget] = useState(null);

  const manage = useApiResource(
    manageTarget ? `/warehouses/${manageTarget.id}/locations` : null,
    { page_size: 200 }
  );
  const zones = useApiResource(manageTarget ? `/warehouses/${manageTarget.id}/zones` : null);

  const openCreate = () => {
    setEditing(null);
    setForm(emptyWarehouse);
    setFormOpen(true);
  };

  const openEdit = (warehouse) => {
    setEditing(warehouse);
    setForm({ ...emptyWarehouse, ...warehouse });
    setFormOpen(true);
  };

  const update = (key) => (e) => {
    const value = e.target.type === 'checkbox' ? e.target.checked : e.target.value;
    setForm((f) => ({ ...f, [key]: value }));
  };

  const save = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      const payload = {
        code: form.code.trim(),
        name: form.name.trim(),
        status: form.status,
        timezone: form.timezone,
        address: form.address || null,
        city: form.city || null,
        province: form.province || null,
        postal_code: form.postal_code || null,
        country: form.country || 'Indonesia',
        phone: form.phone || null,
        is_default: Boolean(form.is_default),
      };
      if (editing) {
        await api.patch(`/warehouses/${editing.id}`, payload);
        toast.success('Warehouse updated');
      } else {
        await api.post('/warehouses', payload);
        toast.success('Warehouse created');
      }
      setFormOpen(false);
      refetch();
    } catch (err) {
      toast.error('Could not save warehouse', err.message);
    } finally {
      setSaving(false);
    }
  };

  const remove = async () => {
    try {
      await api.del(`/warehouses/${deleteTarget.id}`);
      toast.success('Warehouse closed');
      setDeleteTarget(null);
      refetch();
    } catch (err) {
      toast.error('Could not delete warehouse', err.message);
    }
  };

  const addLocation = async (e) => {
    e.preventDefault();
    try {
      await api.post(`/warehouses/${manageTarget.id}/locations`, {
        code: locationForm.code.trim(),
        zone_id: locationForm.zone_id || null,
        location_type: locationForm.location_type,
        status: locationForm.status,
      });
      toast.success('Location added');
      setLocationForm({ code: '', zone_id: '', location_type: 'storage', status: 'available' });
      manage.refetch();
    } catch (err) {
      toast.error('Could not add location', err.message);
    }
  };

  const addZone = async (e) => {
    e.preventDefault();
    try {
      await api.post(`/warehouses/${manageTarget.id}/zones`, { code: zoneForm.code.trim(), name: zoneForm.name.trim() });
      toast.success('Zone added');
      setZoneForm({ code: '', name: '' });
      zones.refetch();
    } catch (err) {
      toast.error('Could not add zone', err.message);
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Warehouses & Locations"
        description="Configure your physical network of warehouses, zones and storage locations."
        actions={canWrite ? <Button onClick={openCreate}><Plus className="mr-2 h-4 w-4" />New warehouse</Button> : null}
      />

      <Card>
        <DataTable
          columns={[
            {
              key: 'name',
              header: 'Warehouse',
              render: (row) => (
                <div className="flex items-center gap-3">
                  <div className="rounded-lg bg-blue-50 p-2 text-blue-600">
                    <Building2 className="h-4 w-4" />
                  </div>
                  <div>
                    <p className="font-medium text-slate-800">{row.name}</p>
                    <p className="text-xs text-slate-400">{row.code}</p>
                  </div>
                </div>
              ),
            },
            { key: 'city', header: 'City', render: (row) => row.city || '—' },
            { key: 'timezone', header: 'Timezone', render: (row) => row.timezone || 'Asia/Jakarta' },
            { key: 'is_default', header: 'Default', render: (row) => (row.is_default ? 'Yes' : '—') },
            { key: 'status', header: 'Status', render: (row) => <StatusBadge value={row.status} tones={STATUS_TONES} /> },
            {
              key: 'actions',
              header: '',
              className: 'text-right',
              render: (row) => (
                <div className="flex justify-end gap-1">
                  <Button variant="outline" size="sm" onClick={() => setManageTarget(row)}>
                    <MapPin className="mr-1.5 h-3.5 w-3.5" /> Locations
                  </Button>
                  {canWrite ? (
                    <DropdownMenu
                      trigger={
                        <button type="button" className="rounded-md p-1.5 text-slate-400 hover:bg-slate-100">
                          <MoreHorizontal className="h-4 w-4" />
                        </button>
                      }
                    >
                      <DropdownItem icon={Pencil} onClick={() => openEdit(row)}>Edit</DropdownItem>
                      <DropdownItem icon={Trash2} className="text-red-600" onClick={() => setDeleteTarget(row)}>Delete</DropdownItem>
                    </DropdownMenu>
                  ) : null}
                </div>
              ),
            },
          ]}
          rows={data}
          loading={loading}
          error={error}
          onRetry={refetch}
          emptyTitle="No warehouses yet"
          emptyMessage="Create a warehouse to define where stock is stored."
          emptyAction={canWrite ? <Button onClick={openCreate}><Plus className="mr-2 h-4 w-4" />New warehouse</Button> : null}
        />
        <Pagination meta={meta} onPageChange={setPage} />
      </Card>

      <Modal
        open={formOpen}
        onClose={() => setFormOpen(false)}
        title={editing ? 'Edit warehouse' : 'New warehouse'}
        size="lg"
        footer={
          <>
            <Button variant="outline" onClick={() => setFormOpen(false)} disabled={saving}>Cancel</Button>
            <Button form="warehouse-form" type="submit" disabled={saving}>{saving ? 'Saving…' : 'Save'}</Button>
          </>
        }
      >
        <form id="warehouse-form" onSubmit={save} className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field label="Code" required><Input value={form.code} onChange={update('code')} required placeholder="MAIN" /></Field>
          <Field label="Name" required><Input value={form.name} onChange={update('name')} required /></Field>
          <Field label="Status">
            <Select value={form.status} onChange={update('status')}>
              {WAREHOUSE_STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
            </Select>
          </Field>
          <Field label="Timezone"><Input value={form.timezone} onChange={update('timezone')} /></Field>
          <Field label="Address" className="sm:col-span-2"><Input value={form.address} onChange={update('address')} /></Field>
          <Field label="City"><Input value={form.city} onChange={update('city')} /></Field>
          <Field label="Province"><Input value={form.province} onChange={update('province')} /></Field>
          <Field label="Postal code"><Input value={form.postal_code} onChange={update('postal_code')} /></Field>
          <Field label="Country"><Input value={form.country} onChange={update('country')} /></Field>
          <Field label="Phone"><Input value={form.phone} onChange={update('phone')} /></Field>
          <div className="sm:col-span-2">
            <Checkbox label="Set as default warehouse" checked={form.is_default} onChange={update('is_default')} />
          </div>
        </form>
      </Modal>

      <Modal
        open={Boolean(manageTarget)}
        onClose={() => setManageTarget(null)}
        title={`Locations — ${manageTarget?.name || ''}`}
        size="lg"
      >
        <div className="space-y-6">
          <div>
            <h3 className="text-sm font-semibold text-slate-700">Zones</h3>
            <div className="mt-2 flex flex-wrap gap-2">
              {(zones.data || []).map((z) => (
                <span key={z.id} className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-600">{z.code} · {z.name}</span>
              ))}
              {(zones.data || []).length === 0 ? <p className="text-sm text-slate-400">No zones yet.</p> : null}
            </div>
            {canWrite ? (
              <form onSubmit={addZone} className="mt-3 flex flex-wrap items-end gap-2">
                <Field label="Code" className="w-28"><Input value={zoneForm.code} onChange={(e) => setZoneForm((f) => ({ ...f, code: e.target.value }))} required /></Field>
                <Field label="Name" className="w-40"><Input value={zoneForm.name} onChange={(e) => setZoneForm((f) => ({ ...f, name: e.target.value }))} required /></Field>
                <Button type="submit" variant="outline" size="sm"><Plus className="mr-1 h-3.5 w-3.5" />Add zone</Button>
              </form>
            ) : null}
          </div>

          <div className="border-t border-slate-200 pt-4">
            <h3 className="text-sm font-semibold text-slate-700">Locations</h3>
            <div className="mt-3">
              <DataTable
                columns={[
                  { key: 'code', header: 'Code', render: (r) => <span className="font-medium text-slate-800">{r.code}</span> },
                  { key: 'location_type', header: 'Type', render: (r) => r.location_type },
                  { key: 'status', header: 'Status', render: (r) => <StatusBadge value={r.status} tones={STATUS_TONES} /> },
                  { key: 'is_pickable', header: 'Pickable', render: (r) => (r.is_pickable ? 'Yes' : 'No') },
                  {
                    key: 'actions',
                    header: '',
                    className: 'text-right',
                    render: (r) =>
                      canWrite ? (
                        <Button
                          variant="ghost"
                          size="sm"
                          className="text-red-600"
                          onClick={async () => {
                            try {
                              await api.del(`/locations/${r.id}`);
                              toast.success('Location removed');
                              manage.refetch();
                            } catch (err) {
                              toast.error('Could not remove location', err.message);
                            }
                          }}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      ) : null,
                  },
                ]}
                rows={manage.data}
                loading={manage.loading}
                error={manage.error}
                onRetry={manage.refetch}
                emptyTitle="No locations yet"
                skeletonRows={3}
              />
            </div>

            {canWrite ? (
              <form onSubmit={addLocation} className="mt-4 flex flex-wrap items-end gap-2 border-t border-slate-100 pt-4">
                <Field label="Code" required className="w-28"><Input value={locationForm.code} onChange={(e) => setLocationForm((f) => ({ ...f, code: e.target.value }))} required placeholder="A-01-01" /></Field>
                <Field label="Zone" className="w-36">
                  <Select value={locationForm.zone_id} onChange={(e) => setLocationForm((f) => ({ ...f, zone_id: e.target.value }))}>
                    <option value="">None</option>
                    {(zones.data || []).map((z) => <option key={z.id} value={z.id}>{z.code}</option>)}
                  </Select>
                </Field>
                <Field label="Type" className="w-36">
                  <Select value={locationForm.location_type} onChange={(e) => setLocationForm((f) => ({ ...f, location_type: e.target.value }))}>
                    {LOCATION_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
                  </Select>
                </Field>
                <Field label="Status" className="w-36">
                  <Select value={locationForm.status} onChange={(e) => setLocationForm((f) => ({ ...f, status: e.target.value }))}>
                    {LOCATION_STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
                  </Select>
                </Field>
                <Button type="submit" size="sm"><Plus className="mr-1 h-3.5 w-3.5" />Add location</Button>
              </form>
            ) : null}
          </div>
        </div>
      </Modal>

      <ConfirmDialog
        open={Boolean(deleteTarget)}
        onClose={() => setDeleteTarget(null)}
        onConfirm={remove}
        title="Delete warehouse"
        message={`Delete "${deleteTarget?.name}"? Warehouses holding stock cannot be deleted.`}
        confirmLabel="Delete"
        destructive
      />
    </div>
  );
}
