import React from 'react';
import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import Layout from './layout/Layout';
import { LoadingState } from './common/States';
import { EmptyState } from './common/States';
import { ShieldAlert } from 'lucide-react';
import { Button } from './ui/button';

export function RequireAuth({ children }) {
  const { isAuthenticated, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <LoadingState label="Restoring your session…" />
      </div>
    );
  }
  if (!isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }
  return children || <Outlet />;
}

export function RequirePermission({ permission, children }) {
  const { hasPermission } = useAuth();
  if (permission && !hasPermission(permission)) {
    return (
      <EmptyState
        icon={ShieldAlert}
        title="Access restricted"
        message="You do not have permission to view this page. Contact your administrator if you believe this is a mistake."
        action={<Button variant="outline" onClick={() => window.history.back()}>Go back</Button>}
      />
    );
  }
  return children;
}

export function AppLayout() {
  return (
    <RequireAuth>
      <Layout>
        <Outlet />
      </Layout>
    </RequireAuth>
  );
}
