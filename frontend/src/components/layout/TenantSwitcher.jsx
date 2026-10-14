import React, { useState } from 'react';
import { Building2, ChevronsUpDown } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { useApiResource } from '../../hooks/useApi';
import { DropdownItem, DropdownMenu } from '../ui/dropdown';
import { Spinner } from '../ui/primitives';
import { useToast } from '../ui/toaster';

export function TenantSwitcher() {
  const { activeTenantId, selectTenant, tenant } = useAuth();
  const toast = useToast();
  const [switching, setSwitching] = useState(false);
  const { data: tenants } = useApiResource('/platform/tenants', { page_size: 100 });

  const current = (tenants || []).find((t) => t.id === activeTenantId);
  const label = tenant?.name || current?.name || 'Select organization';

  const choose = async (tenantId) => {
    setSwitching(true);
    try {
      await selectTenant(tenantId);
      toast.success('Tenant context updated');
    } catch (e) {
      toast.error('Could not switch tenant', e.message);
    } finally {
      setSwitching(false);
    }
  };

  return (
    <DropdownMenu
      align="left"
      trigger={
        <button
          type="button"
          className="flex items-center gap-2 rounded-md border border-slate-200 px-3 py-1.5 text-sm text-slate-700 transition hover:bg-slate-50"
        >
          <Building2 className="h-4 w-4 text-slate-400" />
          <span className="max-w-[10rem] truncate">{label}</span>
          {switching ? <Spinner className="h-3.5 w-3.5" /> : <ChevronsUpDown className="h-4 w-4 text-slate-400" />}
        </button>
      }
    >
      <div className="max-h-72 overflow-y-auto">
        {(tenants || []).map((t) => (
          <DropdownItem key={t.id} onClick={() => choose(t.id)}>
            <span className="flex items-center gap-2">
              {t.id === activeTenantId ? (
                <span className="h-2 w-2 rounded-full bg-blue-600" />
              ) : (
                <span className="h-2 w-2 rounded-full bg-transparent" />
              )}
              <span className="flex-1">
                {t.name}
                <span className="ml-1 text-xs text-slate-400">({t.code})</span>
              </span>
            </span>
          </DropdownItem>
        ))}
        {!tenants ? <div className="px-3 py-2 text-sm text-slate-400">Loading…</div> : null}
      </div>
    </DropdownMenu>
  );
}

export default TenantSwitcher;
