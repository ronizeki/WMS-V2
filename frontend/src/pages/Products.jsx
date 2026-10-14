import React, { useMemo, useState } from 'react';
import { MoreHorizontal, Pencil, Plus, Trash2 } from 'lucide-react';
import api from '../lib/api';
import { useApiResource, useDebounced } from '../hooks/useApi';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../components/ui/toaster';
import { PageHeader } from '../components/common/PageHeader';
import { DataTable, Pagination } from '../components/common/DataTable';
import { SearchInput, Toolbar } from '../components/common/Toolbar';
import { Button } from '../components/ui/button';
import { Card } from '../components/ui/card';
import { Field, Input, Select, Textarea, Checkbox } from '../components/ui/form';
import { Modal, ConfirmDialog } from '../components/ui/modal';
import { DropdownItem, DropdownMenu } from '../components/ui/dropdown';
import { StatusBadge } from '../components/ui/primitives';
import { formatCurrency, formatNumber } from '../lib/format';
import { PRODUCT_STATUSES, PRODUCT_TYPES, STATUS_TONES } from '../lib/constants';

const emptyForm = {
  sku: '',
  name: '',
  barcode: '',
  category_id: '',
  brand: '',
  product_type: 'finished_good',
  status: 'active',
  base_unit: 'PCS',
  cost_price: '',
  selling_price: '',
  reorder_point: '',
  reorder_quantity: '',
  description: '',
  track_batch: false,
  track_expiry: false,
  track_serial: false,
};

function toForm(product) {
  return {
    ...emptyForm,
    ...product,
    cost_price: product.cost_price ?? '',
    selling_price: product.selling_price ?? '',
    reorder_point: product.reorder_point ?? '',
    reorder_quantity: product.reorder_quantity ?? '',
    category_id: product.category_id || '',
    barcode: product.barcode || '',
    brand: product.brand || '',
    description: product.description || '',
  };
}

function toPayload(form) {
  return {
    sku: form.sku.trim(),
    name: form.name.trim(),
    barcode: form.barcode?.trim() || null,
    category_id: form.category_id || null,
    brand: form.brand?.trim() || null,
    product_type: form.product_type,
    status: form.status,
    base_unit: form.base_unit || 'PCS',
    cost_price: Number(form.cost_price) || 0,
    selling_price: form.selling_price === '' ? null : Number(form.selling_price),
    reorder_point: Number(form.reorder_point) || 0,
    reorder_quantity: Number(form.reorder_quantity) || 0,
    description: form.description?.trim() || null,
    track_batch: Boolean(form.track_batch),
    track_expiry: Boolean(form.track_expiry),
    track_serial: Boolean(form.track_serial),
  };
}

export default function Products() {
  const { hasPermission } = useAuth();
  const toast = useToast();
  const canWrite = hasPermission('product:write');
  const canDelete = hasPermission('product:delete');

  const [search, setSearch] = useState('');
  const [status, setStatus] = useState('');
  const [categoryId, setCategoryId] = useState('');
  const [page, setPage] = useState(1);
  const debouncedSearch = useDebounced(search);

  const params = useMemo(
    () => ({
      search: debouncedSearch || undefined,
      status: status || undefined,
      category_id: categoryId || undefined,
      page,
      page_size: 20,
    }),
    [debouncedSearch, status, categoryId, page]
  );

  const { data, meta, loading, error, refetch } = useApiResource('/products', params);
  const { data: categories, refetch: refetchCategories } = useApiResource('/categories');

  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(emptyForm);
  const [saving, setSaving] = useState(false);

  const [archiveTarget, setArchiveTarget] = useState(null);
  const [archiving, setArchiving] = useState(false);

  const [categoryOpen, setCategoryOpen] = useState(false);
  const [categoryForm, setCategoryForm] = useState({ name: '', code: '', description: '' });

  const openCreate = () => {
    setEditing(null);
    setForm(emptyForm);
    setFormOpen(true);
  };

  const openEdit = (product) => {
    setEditing(product);
    setForm(toForm(product));
    setFormOpen(true);
  };

  const update = (key) => (event) => {
    const value = event.target.type === 'checkbox' ? event.target.checked : event.target.value;
    setForm((f) => ({ ...f, [key]: value }));
  };

  const save = async (event) => {
    event.preventDefault();
    setSaving(true);
    try {
      const payload = toPayload(form);
      if (editing) {
        await api.patch(`/products/${editing.id}`, payload);
        toast.success('Product updated');
      } else {
        await api.post('/products', payload);
        toast.success('Product created');
      }
      setFormOpen(false);
      refetch();
    } catch (e) {
      toast.error('Could not save product', e.message);
    } finally {
      setSaving(false);
    }
  };

  const archive = async () => {
    setArchiving(true);
    try {
      await api.del(`/products/${archiveTarget.id}`);
      toast.success('Product archived');
      setArchiveTarget(null);
      refetch();
    } catch (e) {
      toast.error('Could not archive product', e.message);
    } finally {
      setArchiving(false);
    }
  };

  const createCategory = async (event) => {
    event.preventDefault();
    try {
      await api.post('/categories', {
        name: categoryForm.name,
        code: categoryForm.code || undefined,
        description: categoryForm.description || undefined,
      });
      toast.success('Category created');
      setCategoryForm({ name: '', code: '', description: '' });
      refetchCategories();
    } catch (e) {
      toast.error('Could not create category', e.message);
    }
  };

  const categoryName = (id) => (categories || []).find((c) => c.id === id)?.name || '—';

  return (
    <div className="space-y-6">
      <PageHeader
        title="Products"
        description="Manage your catalog, pricing and reorder rules."
        actions={
          canWrite ? (
            <>
              <Button variant="outline" onClick={() => setCategoryOpen(true)}>
                Categories
              </Button>
              <Button onClick={openCreate}>
                <Plus className="mr-2 h-4 w-4" /> New product
              </Button>
            </>
          ) : null
        }
      />

      <Card>
        <Toolbar>
          <SearchInput value={search} onChange={(v) => { setSearch(v); setPage(1); }} placeholder="Search SKU, name or barcode…" className="sm:max-w-xs" />
          <div className="flex flex-1 flex-wrap gap-3">
            <Select value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }} className="sm:w-40">
              <option value="">All statuses</option>
              {PRODUCT_STATUSES.map((s) => (
                <option key={s} value={s}>{s.replace(/_/g, ' ')}</option>
              ))}
            </Select>
            <Select value={categoryId} onChange={(e) => { setCategoryId(e.target.value); setPage(1); }} className="sm:w-44">
              <option value="">All categories</option>
              {(categories || []).map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </Select>
          </div>
        </Toolbar>

        <DataTable
          columns={[
            {
              key: 'sku',
              header: 'SKU / Name',
              render: (row) => (
                <div>
                  <p className="font-medium text-slate-800">{row.sku}</p>
                  <p className="text-xs text-slate-500">{row.name}</p>
                </div>
              ),
            },
            { key: 'category_id', header: 'Category', render: (row) => categoryName(row.category_id) },
            { key: 'base_unit', header: 'Unit' },
            { key: 'cost_price', header: 'Cost', className: 'text-right', render: (row) => formatCurrency(row.cost_price) },
            { key: 'reorder_point', header: 'Reorder at', className: 'text-right', render: (row) => formatNumber(row.reorder_point) },
            {
              key: 'status',
              header: 'Status',
              render: (row) => <StatusBadge value={row.status} tones={STATUS_TONES} />,
            },
            {
              key: 'actions',
              header: '',
              className: 'text-right',
              render: (row) =>
                canWrite ? (
                  <DropdownMenu
                    trigger={
                      <button type="button" className="rounded-md p-1.5 text-slate-400 hover:bg-slate-100">
                        <MoreHorizontal className="h-4 w-4" />
                      </button>
                    }
                  >
                    <DropdownItem icon={Pencil} onClick={() => openEdit(row)}>
                      Edit
                    </DropdownItem>
                    {canDelete ? (
                      <DropdownItem icon={Trash2} className="text-red-600" onClick={() => setArchiveTarget(row)}>
                        Archive
                      </DropdownItem>
                    ) : null}
                  </DropdownMenu>
                ) : null,
            },
          ]}
          rows={data}
          loading={loading}
          error={error}
          onRetry={refetch}
          emptyTitle="No products yet"
          emptyMessage={search ? 'No products match your search.' : 'Create your first product to start receiving stock.'}
          emptyAction={canWrite ? <Button onClick={openCreate}><Plus className="mr-2 h-4 w-4" />New product</Button> : null}
        />
        <Pagination meta={meta} onPageChange={setPage} />
      </Card>

      <Modal
        open={formOpen}
        onClose={() => setFormOpen(false)}
        title={editing ? 'Edit product' : 'New product'}
        size="lg"
        footer={
          <>
            <Button variant="outline" onClick={() => setFormOpen(false)} disabled={saving}>
              Cancel
            </Button>
            <Button form="product-form" type="submit" disabled={saving}>
              {saving ? 'Saving…' : editing ? 'Save changes' : 'Create product'}
            </Button>
          </>
        }
      >
        <form id="product-form" onSubmit={save} className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field label="SKU" required>
            <Input value={form.sku} onChange={update('sku')} required placeholder="e.g. SKU-0001" />
          </Field>
          <Field label="Barcode">
            <Input value={form.barcode} onChange={update('barcode')} placeholder="EAN / UPC" />
          </Field>
          <Field label="Name" required className="sm:col-span-2">
            <Input value={form.name} onChange={update('name')} required placeholder="Product name" />
          </Field>
          <Field label="Category">
            <Select value={form.category_id} onChange={update('category_id')}>
              <option value="">Uncategorised</option>
              {(categories || []).map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </Select>
          </Field>
          <Field label="Brand">
            <Input value={form.brand} onChange={update('brand')} />
          </Field>
          <Field label="Product type">
            <Select value={form.product_type} onChange={update('product_type')}>
              {PRODUCT_TYPES.map((t) => (
                <option key={t} value={t}>{t.replace(/_/g, ' ')}</option>
              ))}
            </Select>
          </Field>
          <Field label="Status">
            <Select value={form.status} onChange={update('status')}>
              {PRODUCT_STATUSES.map((s) => (
                <option key={s} value={s}>{s.replace(/_/g, ' ')}</option>
              ))}
            </Select>
          </Field>
          <Field label="Base unit" required>
            <Input value={form.base_unit} onChange={update('base_unit')} required placeholder="PCS" />
          </Field>
          <Field label="Cost price">
            <Input type="number" min="0" step="0.01" value={form.cost_price} onChange={update('cost_price')} />
          </Field>
          <Field label="Selling price">
            <Input type="number" min="0" step="0.01" value={form.selling_price} onChange={update('selling_price')} />
          </Field>
          <Field label="Reorder point" hint="Available stock below this triggers low-stock alerts.">
            <Input type="number" min="0" step="0.01" value={form.reorder_point} onChange={update('reorder_point')} />
          </Field>
          <Field label="Reorder quantity">
            <Input type="number" min="0" step="0.01" value={form.reorder_quantity} onChange={update('reorder_quantity')} />
          </Field>
          <Field label="Description" className="sm:col-span-2">
            <Textarea value={form.description} onChange={update('description')} />
          </Field>
          <div className="flex flex-wrap gap-5 sm:col-span-2">
            <Checkbox label="Track batch" checked={form.track_batch} onChange={update('track_batch')} />
            <Checkbox label="Track expiry" checked={form.track_expiry} onChange={update('track_expiry')} />
            <Checkbox label="Track serial" checked={form.track_serial} onChange={update('track_serial')} />
          </div>
        </form>
      </Modal>

      <ConfirmDialog
        open={Boolean(archiveTarget)}
        onClose={() => setArchiveTarget(null)}
        onConfirm={archive}
        title="Archive product"
        message={`Archive "${archiveTarget?.name}"? Historical stock records are preserved but the product will be hidden from active lists.`}
        confirmLabel="Archive"
        loading={archiving}
        destructive
      />

      <Modal open={categoryOpen} onClose={() => setCategoryOpen(false)} title="Product categories" size="md">
        <form onSubmit={createCategory} className="space-y-3">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <Field label="Name" required className="sm:col-span-2">
              <Input value={categoryForm.name} onChange={(e) => setCategoryForm((f) => ({ ...f, name: e.target.value }))} required />
            </Field>
            <Field label="Code">
              <Input value={categoryForm.code} onChange={(e) => setCategoryForm((f) => ({ ...f, code: e.target.value }))} />
            </Field>
          </div>
          <Button type="submit" size="sm"><Plus className="mr-2 h-4 w-4" />Add category</Button>
        </form>
        <div className="mt-4 divide-y divide-slate-100 border-t border-slate-200">
          {(categories || []).length === 0 ? (
            <p className="py-4 text-sm text-slate-400">No categories yet.</p>
          ) : (
            (categories || []).map((c) => (
              <div key={c.id} className="flex items-center justify-between py-2">
                <div>
                  <p className="text-sm font-medium text-slate-700">{c.name}</p>
                  {c.code ? <p className="text-xs text-slate-400">{c.code}</p> : null}
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-red-600"
                  onClick={async () => {
                    try {
                      await api.del(`/categories/${c.id}`);
                      toast.success('Category removed');
                      refetchCategories();
                    } catch (e) {
                      toast.error('Could not remove category', e.message);
                    }
                  }}
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            ))
          )}
        </div>
      </Modal>
    </div>
  );
}
