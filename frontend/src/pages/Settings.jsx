import React, { useMemo, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { Plus, Save, Shield, Trash2, UserCog, UserPlus, Building2, KeyRound } from 'lucide-react';
import api from '../lib/api';
import { useApiResource } from '../hooks/useApi';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../components/ui/toaster';
import { PageHeader } from '../components/common/PageHeader';
import { DataTable, Pagination } from '../components/common/DataTable';
import { Button } from '../components/ui/button';
import { Card } from '../components/ui/card';
import { Tabs } from '../components/ui/tabs';
import { Checkbox, Field, Input, Select } from '../components/ui/form';
import { Modal, ConfirmDialog } from '../components/ui/modal';
import { Badge, StatusBadge } from '../components/ui/primitives';
import { formatDateTime, titleCase } from '../lib/format';
import { USER_STATUSES, STATUS_TONES } from '../lib/constants';

const SETTING_TOGGLES = [
  { key: 'allow_negative_stock', label: 'Allow negative stock', hint: 'Permit on-hand to go below zero (not recommended).' },
  { key: 'require_adjustment_approval', label: 'Require adjustment approval', hint: 'Stock adjustments must be approved before posting.' },
  { key: 'require_transfer_approval', label: 'Require transfer approval', hint: 'Transfers must be approved before dispatch.' },
  { key: 'require_cycle_count_approval', label: 'Require stocktake approval', hint: 'Cycle count variances post only after approval.' },
  { key: 'auto_create_putaway_tasks', label: 'Auto-create putaway tasks', hint: 'Generate putaway work when a receipt is posted.' },
  { key: 'low_stock_notifications', label: 'Low stock notifications', hint: 'Surface low-stock alerts on the dashboard.' },
  { key: 'batch_tracking_default', label: 'Track batches by default', hint: 'New products default to batch tracking.' },
  { key: 'serial_tracking_default', label: 'Track serials by default', hint: 'New products default to serial tracking.' },
];

export default function Settings() {
  const { hasPermission, tenant, isPlatformAdmin } = useAuth();
  const location = useLocation();
  const toast = useToast();
  const [tab, setTab] = useState(location.state?.tab || 'profile');

  React.useEffect(() => {
    if (location.state?.tab) setTab(location.state.tab);
  }, [location.state]);

  const settings = useApiResource('/settings');
  const roles = useApiResource('/roles');
  const permissions = useApiResource('/permissions');
  const [userPage, setUserPage] = useState(1);
  const users = useApiResource('/users', { page: userPage, page_size: 20 });

  const [profile, setProfile] = useState(null);
  React.useEffect(() => {
    if (settings.data) setProfile(settings.data);
  }, [settings.data]);

  const [savingProfile, setSavingProfile] = useState(false);
  const updateProfile = (key) => (e) => {
    const value = e.target.type === 'checkbox' ? e.target.checked : e.target.value;
    setProfile((p) => ({ ...p, [key]: value }));
  };
  const updateSetting = (key) => (e) => {
    const value = e.target.type === 'checkbox' ? e.target.checked : e.target.value;
    setProfile((p) => ({ ...p, settings: { ...p.settings, [key]: value } }));
  };

  const saveProfile = async (e) => {
    e.preventDefault();
    if (!profile) return;
    setSavingProfile(true);
    try {
      const payload = {
        name: profile.name,
        timezone: profile.timezone,
        currency: profile.currency,
        locale: profile.locale,
        phone: profile.phone,
        email: profile.email,
        address: profile.address,
        city: profile.city,
        province: profile.province,
        postal_code: profile.postal_code,
        country: profile.country,
        website: profile.website,
        tax_number: profile.tax_number,
        settings: profile.settings,
      };
      await api.patch('/settings', payload);
      toast.success('Settings saved');
      settings.refetch();
    } catch (err) {
      toast.error('Could not save settings', err.message);
    } finally {
      setSavingProfile(false);
    }
  };

  // ---- users
  const [userFormOpen, setUserFormOpen] = useState(false);
  const [editingUser, setEditingUser] = useState(null);
  const [userForm, setUserForm] = useState({ email: '', full_name: '', password: '', phone: '', status: 'active', role_codes: [] });
  const [savingUser, setSavingUser] = useState(false);
  const [resetTarget, setResetTarget] = useState(null);
  const [newPassword, setNewPassword] = useState('');
  const [deactivateTarget, setDeactivateTarget] = useState(null);

  const openCreateUser = () => {
    setEditingUser(null);
    setUserForm({ email: '', full_name: '', password: '', phone: '', status: 'active', role_codes: ['warehouse_operator'] });
    setUserFormOpen(true);
  };
  const openEditUser = (user) => {
    setEditingUser(user);
    setUserForm({ email: user.email, full_name: user.full_name, password: '', phone: user.phone || '', status: user.status, role_codes: user.role_codes || [] });
    setUserFormOpen(true);
  };
  const toggleRoleCode = (code) =>
    setUserForm((f) => ({
      ...f,
      role_codes: f.role_codes.includes(code) ? f.role_codes.filter((c) => c !== code) : [...f.role_codes, code],
    }));

  const saveUser = async (e) => {
    e.preventDefault();
    setSavingUser(true);
    try {
      if (editingUser) {
        await api.patch(`/users/${editingUser.id}`, {
          full_name: userForm.full_name,
          phone: userForm.phone || null,
          status: userForm.status,
          role_codes: userForm.role_codes,
        });
        toast.success('User updated');
      } else {
        await api.post('/users', {
          email: userForm.email,
          full_name: userForm.full_name,
          password: userForm.password,
          phone: userForm.phone || undefined,
          status: userForm.status,
          role_codes: userForm.role_codes,
        });
        toast.success('User created');
      }
      setUserFormOpen(false);
      users.refetch();
    } catch (err) {
      toast.error('Could not save user', err.message);
    } finally {
      setSavingUser(false);
    }
  };

  const doResetPassword = async () => {
    try {
      await api.post(`/users/${resetTarget.id}/reset-password`, { password: newPassword });
      toast.success('Password reset');
      setResetTarget(null);
      setNewPassword('');
    } catch (err) {
      toast.error('Could not reset password', err.message);
    }
  };

  const doDeactivate = async () => {
    try {
      await api.del(`/users/${deactivateTarget.id}`);
      toast.success('User deactivated');
      setDeactivateTarget(null);
      users.refetch();
    } catch (err) {
      toast.error('Could not deactivate user', err.message);
    }
  };

  // ---- roles
  const [roleFormOpen, setRoleFormOpen] = useState(false);
  const [editingRole, setEditingRole] = useState(null);
  const [roleForm, setRoleForm] = useState({ code: '', name: '', description: '', permissions: [] });
  const [savingRole, setSavingRole] = useState(false);
  const [deleteRoleTarget, setDeleteRoleTarget] = useState(null);

  const permissionGroups = permissions.data?.by_category || {};

  const openCreateRole = () => {
    setEditingRole(null);
    setRoleForm({ code: '', name: '', description: '', permissions: [] });
    setRoleFormOpen(true);
  };
  const openEditRole = (role) => {
    setEditingRole(role);
    setRoleForm({ code: role.code, name: role.name, description: role.description || '', permissions: role.permissions || [] });
    setRoleFormOpen(true);
  };
  const togglePermission = (code) =>
    setRoleForm((f) => ({
      ...f,
      permissions: f.permissions.includes(code) ? f.permissions.filter((p) => p !== code) : [...f.permissions, code],
    }));

  const saveRole = async (e) => {
    e.preventDefault();
    setSavingRole(true);
    try {
      const payload = { code: roleForm.code, name: roleForm.name, description: roleForm.description || null, permissions: roleForm.permissions };
      if (editingRole) {
        await api.patch(`/roles/${editingRole.id}`, payload);
        toast.success('Role updated');
      } else {
        await api.post('/roles', payload);
        toast.success('Role created');
      }
      setRoleFormOpen(false);
      roles.refetch();
    } catch (err) {
      toast.error('Could not save role', err.message);
    } finally {
      setSavingRole(false);
    }
  };

  const deleteRole = async () => {
    try {
      await api.del(`/roles/${deleteRoleTarget.id}`);
      toast.success('Role deleted');
      setDeleteRoleTarget(null);
      roles.refetch();
    } catch (err) {
      toast.error('Could not delete role', err.message);
    }
  };

  const canWriteSettings = hasPermission('settings:write');
  const canWriteUsers = hasPermission('user:write');
  const canWriteRoles = hasPermission('role:write');

  const tabs = useMemo(() => {
    const list = [{ value: 'profile', label: 'Organization', icon: Building2 }];
    if (hasPermission('user:read')) list.push({ value: 'users', label: 'Users', icon: UserCog });
    if (hasPermission('role:read')) list.push({ value: 'roles', label: 'Roles & permissions', icon: Shield });
    return list;
  }, [hasPermission]);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Settings"
        description={
          isPlatformAdmin && tenant?.name
            ? `Managing organization: ${tenant.name} (${tenant.code || ''})`
            : 'Organization profile, preferences, users and access control.'
        }
      />

      <Card>
        <Tabs value={tab} onChange={setTab} tabs={tabs} />

        {tab === 'profile' ? (
          <form onSubmit={saveProfile} className="space-y-6 p-6">
            {settings.loading ? <p className="text-sm text-slate-400">Loading…</p> : null}
            {profile ? (
              <>
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
                  <Field label="Organization name" required><Input value={profile.name || ''} onChange={updateProfile('name')} disabled={!canWriteSettings} /></Field>
                  <Field label="Timezone"><Input value={profile.timezone || ''} onChange={updateProfile('timezone')} disabled={!canWriteSettings} /></Field>
                  <Field label="Currency"><Input value={profile.currency || ''} onChange={updateProfile('currency')} disabled={!canWriteSettings} /></Field>
                  <Field label="Locale"><Input value={profile.locale || ''} onChange={updateProfile('locale')} disabled={!canWriteSettings} /></Field>
                  <Field label="Email"><Input type="email" value={profile.email || ''} onChange={updateProfile('email')} disabled={!canWriteSettings} /></Field>
                  <Field label="Phone"><Input value={profile.phone || ''} onChange={updateProfile('phone')} disabled={!canWriteSettings} /></Field>
                  <Field label="City"><Input value={profile.city || ''} onChange={updateProfile('city')} disabled={!canWriteSettings} /></Field>
                  <Field label="Province"><Input value={profile.province || ''} onChange={updateProfile('province')} disabled={!canWriteSettings} /></Field>
                  <Field label="Postal code"><Input value={profile.postal_code || ''} onChange={updateProfile('postal_code')} disabled={!canWriteSettings} /></Field>
                  <Field label="Country"><Input value={profile.country || ''} onChange={updateProfile('country')} disabled={!canWriteSettings} /></Field>
                  <Field label="Tax number"><Input value={profile.tax_number || ''} onChange={updateProfile('tax_number')} disabled={!canWriteSettings} /></Field>
                  <Field label="Website"><Input value={profile.website || ''} onChange={updateProfile('website')} disabled={!canWriteSettings} /></Field>
                  <Field label="Address" className="sm:col-span-2 lg:col-span-3"><Input value={profile.address || ''} onChange={updateProfile('address')} disabled={!canWriteSettings} /></Field>
                </div>

                <div className="border-t border-slate-200 pt-5">
                  <h3 className="text-sm font-semibold text-slate-700">Operational preferences</h3>
                  <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
                    {SETTING_TOGGLES.map((item) => (
                      <div key={item.key} className="rounded-lg border border-slate-200 p-3">
                        <Checkbox
                          label={item.label}
                          checked={Boolean(profile.settings?.[item.key])}
                          onChange={updateSetting(item.key)}
                          disabled={!canWriteSettings}
                        />
                        <p className="mt-1 pl-6 text-xs text-slate-500">{item.hint}</p>
                      </div>
                    ))}
                  </div>
                  <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
                    <Field label="Costing method">
                      <Select value={profile.settings?.costing_method || 'weighted_average'} onChange={updateSetting('costing_method')} disabled={!canWriteSettings}>
                        <option value="weighted_average">Weighted average</option>
                        <option value="fifo">FIFO</option>
                      </Select>
                    </Field>
                    <Field label="Reservation timeout (minutes)">
                      <Input type="number" min="0" value={profile.settings?.reservation_timeout_minutes ?? 30} onChange={updateSetting('reservation_timeout_minutes')} disabled={!canWriteSettings} />
                    </Field>
                  </div>
                </div>

                {canWriteSettings ? (
                  <div className="flex justify-end border-t border-slate-200 pt-4">
                    <Button type="submit" disabled={savingProfile}>
                      <Save className="mr-2 h-4 w-4" /> {savingProfile ? 'Saving…' : 'Save changes'}
                    </Button>
                  </div>
                ) : null}
              </>
            ) : null}
          </form>
        ) : null}

        {tab === 'users' ? (
          <div>
            <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
              <p className="text-sm text-slate-500">{users.meta?.total ?? 0} user(s) in this organization</p>
              {canWriteUsers ? (
                <Button size="sm" onClick={openCreateUser}><UserPlus className="mr-2 h-4 w-4" />Invite user</Button>
              ) : null}
            </div>
            <DataTable
              columns={[
                { key: 'full_name', header: 'Name', render: (r) => (<div><p className="font-medium text-slate-800">{r.full_name}</p><p className="text-xs text-slate-400">{r.email}</p></div>) },
                { key: 'role_codes', header: 'Roles', render: (r) => (<div className="flex flex-wrap gap-1">{(r.role_codes || []).map((c) => <Badge key={c} tone="indigo">{titleCase(c)}</Badge>)}</div>) },
                { key: 'status', header: 'Status', render: (r) => <StatusBadge value={r.status} tones={STATUS_TONES} /> },
                { key: 'created_at', header: 'Added', render: (r) => formatDateTime(r.created_at) },
                {
                  key: 'actions',
                  header: '',
                  className: 'text-right',
                  render: (r) =>
                    canWriteUsers ? (
                      <div className="flex justify-end gap-1">
                        <Button size="sm" variant="outline" onClick={() => openEditUser(r)}>Edit</Button>
                        <Button size="sm" variant="ghost" title="Reset password" onClick={() => { setResetTarget(r); setNewPassword(''); }}><KeyRound className="h-4 w-4" /></Button>
                        <Button size="sm" variant="ghost" className="text-red-600" onClick={() => setDeactivateTarget(r)}><Trash2 className="h-4 w-4" /></Button>
                      </div>
                    ) : null,
                },
              ]}
              rows={users.data}
              loading={users.loading}
              error={users.error}
              onRetry={users.refetch}
              emptyTitle="No users yet"
            />
            <Pagination meta={users.meta} onPageChange={setUserPage} />
          </div>
        ) : null}

        {tab === 'roles' ? (
          <div>
            <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
              <p className="text-sm text-slate-500">{(roles.data || []).length} role(s)</p>
              {canWriteRoles ? (
                <Button size="sm" onClick={openCreateRole}><Plus className="mr-2 h-4 w-4" />New role</Button>
              ) : null}
            </div>
            <DataTable
              columns={[
                { key: 'name', header: 'Role', render: (r) => (<div><p className="font-medium text-slate-800">{r.name}</p><p className="text-xs text-slate-400">{r.code}</p></div>) },
                { key: 'permissions', header: 'Permissions', render: (r) => <Badge tone="blue">{(r.permissions || []).length} granted</Badge> },
                { key: 'is_system', header: 'Type', render: (r) => (r.is_system ? <Badge tone="slate">System</Badge> : <Badge tone="green">Custom</Badge>) },
                {
                  key: 'actions',
                  header: '',
                  className: 'text-right',
                  render: (r) =>
                    canWriteRoles ? (
                      <div className="flex justify-end gap-1">
                        <Button size="sm" variant="outline" onClick={() => openEditRole(r)}>Edit</Button>
                        {!r.is_system ? (
                          <Button size="sm" variant="ghost" className="text-red-600" onClick={() => setDeleteRoleTarget(r)}><Trash2 className="h-4 w-4" /></Button>
                        ) : null}
                      </div>
                    ) : null,
                },
              ]}
              rows={roles.data}
              loading={roles.loading}
              error={roles.error}
              onRetry={roles.refetch}
              emptyTitle="No roles"
            />
          </div>
        ) : null}
      </Card>

      {/* User modal */}
      <Modal
        open={userFormOpen}
        onClose={() => setUserFormOpen(false)}
        title={editingUser ? 'Edit user' : 'Invite user'}
        size="md"
        footer={
          <>
            <Button variant="outline" onClick={() => setUserFormOpen(false)} disabled={savingUser}>Cancel</Button>
            <Button form="user-form" type="submit" disabled={savingUser}>{savingUser ? 'Saving…' : 'Save'}</Button>
          </>
        }
      >
        <form id="user-form" onSubmit={saveUser} className="space-y-4">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Field label="Full name" required><Input value={userForm.full_name} onChange={(e) => setUserForm((f) => ({ ...f, full_name: e.target.value }))} required /></Field>
            <Field label="Email" required><Input type="email" value={userForm.email} onChange={(e) => setUserForm((f) => ({ ...f, email: e.target.value }))} required disabled={Boolean(editingUser)} /></Field>
            {!editingUser ? (
              <Field label="Temporary password" required hint="At least 8 characters."><Input type="text" value={userForm.password} onChange={(e) => setUserForm((f) => ({ ...f, password: e.target.value }))} required /></Field>
            ) : null}
            <Field label="Phone"><Input value={userForm.phone} onChange={(e) => setUserForm((f) => ({ ...f, phone: e.target.value }))} /></Field>
            <Field label="Status">
              <Select value={userForm.status} onChange={(e) => setUserForm((f) => ({ ...f, status: e.target.value }))}>
                {USER_STATUSES.map((s) => <option key={s} value={s}>{titleCase(s)}</option>)}
              </Select>
            </Field>
          </div>
          <div>
            <p className="mb-2 text-sm font-medium text-slate-700">Roles</p>
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
              {(roles.data || []).map((role) => (
                <Checkbox
                  key={role.id}
                  label={`${role.name}${role.is_system ? '' : ' (custom)'}`}
                  checked={userForm.role_codes.includes(role.code)}
                  onChange={() => toggleRoleCode(role.code)}
                />
              ))}
            </div>
          </div>
        </form>
      </Modal>

      <ConfirmDialog
        open={Boolean(resetTarget)}
        onClose={() => setResetTarget(null)}
        onConfirm={doResetPassword}
        title="Reset password"
        confirmLabel="Reset"
        message={
          <div className="space-y-2">
            <p>Set a new password for {resetTarget?.full_name}.</p>
            <Input type="text" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} placeholder="New password" />
          </div>
        }
      />

      <ConfirmDialog
        open={Boolean(deactivateTarget)}
        onClose={() => setDeactivateTarget(null)}
        onConfirm={doDeactivate}
        title="Deactivate user"
        message={`Deactivate ${deactivateTarget?.full_name}? They will no longer be able to sign in.`}
        confirmLabel="Deactivate"
        destructive
      />

      {/* Role modal */}
      <Modal
        open={roleFormOpen}
        onClose={() => setRoleFormOpen(false)}
        title={editingRole ? 'Edit role' : 'New role'}
        size="lg"
        footer={
          <>
            <Button variant="outline" onClick={() => setRoleFormOpen(false)} disabled={savingRole}>Cancel</Button>
            <Button form="role-form" type="submit" disabled={savingRole}>{savingRole ? 'Saving…' : 'Save role'}</Button>
          </>
        }
      >
        <form id="role-form" onSubmit={saveRole} className="space-y-4">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Field label="Name" required><Input value={roleForm.name} onChange={(e) => setRoleForm((f) => ({ ...f, name: e.target.value }))} required /></Field>
            <Field label="Code" required hint="Lowercase identifier, e.g. shift_lead.">
              <Input value={roleForm.code} onChange={(e) => setRoleForm((f) => ({ ...f, code: e.target.value }))} required disabled={Boolean(editingRole)} />
            </Field>
            <Field label="Description" className="sm:col-span-2"><Input value={roleForm.description} onChange={(e) => setRoleForm((f) => ({ ...f, description: e.target.value }))} /></Field>
          </div>
          <div>
            <p className="mb-2 text-sm font-medium text-slate-700">Permissions</p>
            <div className="space-y-3">
              {Object.entries(permissionGroups).map(([category, perms]) => (
                <div key={category} className="rounded-lg border border-slate-200 p-3">
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">{titleCase(category)}</p>
                  <div className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-2">
                    {perms.map((perm) => (
                      <Checkbox
                        key={perm.code}
                        label={`${perm.name} — ${perm.code}`}
                        checked={roleForm.permissions.includes(perm.code)}
                        onChange={() => togglePermission(perm.code)}
                      />
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </form>
      </Modal>

      <ConfirmDialog
        open={Boolean(deleteRoleTarget)}
        onClose={() => setDeleteRoleTarget(null)}
        onConfirm={deleteRole}
        title="Delete role"
        message={`Delete the role "${deleteRoleTarget?.name}"? Users assigned to it may lose access.`}
        confirmLabel="Delete"
        destructive
      />
    </div>
  );
}
