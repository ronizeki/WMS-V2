import React, { useState } from 'react';
import { useApiResource } from '../hooks/useApi';
import { PageHeader } from '../components/common/PageHeader';
import { DataTable, Pagination } from '../components/common/DataTable';
import { Toolbar } from '../components/common/Toolbar';
import { Card } from '../components/ui/card';
import { Input } from '../components/ui/form';
import { Badge } from '../components/ui/primitives';
import { formatDateTime, titleCase } from '../lib/format';

const ACTION_TONES = {
  create: 'green',
  update: 'blue',
  delete: 'red',
  approve: 'green',
  reject: 'red',
  allocate: 'indigo',
  pick: 'indigo',
  pack: 'indigo',
  ship: 'purple',
  receive: 'green',
  dispatch: 'blue',
  login: 'slate',
  reset_password: 'amber',
  deactivate: 'amber',
};

export default function Audit() {
  const [page, setPage] = useState(1);
  const [entityType, setEntityType] = useState('');
  const [action, setAction] = useState('');
  const [userId, setUserId] = useState('');

  const logs = useApiResource('/audit-logs', {
    page,
    page_size: 50,
    entity_type: entityType || undefined,
    action: action || undefined,
    user_id: userId || undefined,
  });

  return (
    <div className="space-y-6">
      <PageHeader title="Audit Log" description="An immutable trail of who did what, when and from where." />

      <Card>
        <Toolbar>
          <Input value={entityType} onChange={(e) => { setEntityType(e.target.value); setPage(1); }} placeholder="Filter by entity (e.g. sales_order)" className="sm:max-w-xs" />
          <Input value={action} onChange={(e) => { setAction(e.target.value); setPage(1); }} placeholder="Filter by action (e.g. ship)" className="sm:max-w-xs" />
          <Input value={userId} onChange={(e) => { setUserId(e.target.value); setPage(1); }} placeholder="Filter by user id" className="sm:max-w-xs" />
        </Toolbar>

        <DataTable
          columns={[
            { key: 'created_at', header: 'When', render: (r) => formatDateTime(r.created_at) },
            {
              key: 'action',
              header: 'Action',
              render: (r) => <Badge tone={ACTION_TONES[r.action] || 'slate'}>{titleCase(r.action)}</Badge>,
            },
            { key: 'entity_type', header: 'Entity', render: (r) => titleCase(r.entity_type) },
            { key: 'description', header: 'Description', render: (r) => r.description || '—' },
            { key: 'user_name', header: 'User', render: (r) => r.user_name || r.user_id || 'system' },
            { key: 'ip_address', header: 'IP', render: (r) => r.ip_address || '—' },
          ]}
          rows={logs.data}
          loading={logs.loading}
          error={logs.error}
          onRetry={logs.refetch}
          emptyTitle="No audit entries"
          emptyMessage="Activity will appear here as users work in the system."
        />
        <Pagination meta={logs.meta} onPageChange={setPage} />
      </Card>
    </div>
  );
}
