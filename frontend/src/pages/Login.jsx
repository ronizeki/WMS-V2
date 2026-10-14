import React, { useState } from 'react';
import { Navigate, useLocation, useNavigate } from 'react-router-dom';
import { Boxes, Lock, Mail } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { Button } from '../components/ui/button';
import { Field, Input } from '../components/ui/form';
import { useToast } from '../components/ui/toaster';
import { useOnlineStatus } from '../hooks/useApi';

export default function Login() {
  const { login, isAuthenticated, loading } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const toast = useToast();
  const online = useOnlineStatus();
  const [form, setForm] = useState({ email: '', password: '', tenantCode: '' });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  if (!loading && isAuthenticated) {
    const from = location.state?.from?.pathname || '/dashboard';
    return <Navigate to={from} replace />;
  }

  const update = (key) => (event) => setForm((f) => ({ ...f, [key]: event.target.value }));

  const submit = async (event) => {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login({ email: form.email, password: form.password, tenantCode: form.tenantCode });
      toast.success('Welcome back');
      const from = location.state?.from?.pathname || '/dashboard';
      navigate(from, { replace: true });
    } catch (e) {
      setError(e.message || 'Sign in failed');
    } finally {
      setSubmitting(false);
    }
  };

  const fillDemo = (email, password) => () => setForm({ email, password, tenantCode: '' });

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4 py-10">
      <div className="grid w-full max-w-5xl overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm lg:grid-cols-2">
        <div className="hidden flex-col justify-between bg-gradient-to-br from-blue-700 to-indigo-800 p-10 text-white lg:flex">
          <div className="flex items-center gap-2">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-white/15">
              <Boxes className="h-5 w-5" />
            </div>
            <span className="text-lg font-semibold">StockPilot WMS</span>
          </div>
          <div className="space-y-3">
            <h1 className="text-3xl font-bold leading-tight">Warehouse operations, under control.</h1>
            <p className="text-blue-100">
              Real-time inventory, receiving, fulfilment and stocktake — built for multi-tenant operations
              with role-based access and a complete audit trail.
            </p>
          </div>
          <p className="text-xs text-blue-200">© {new Date().getFullYear()} StockPilot. Asia/Jakarta · IDR</p>
        </div>

        <div className="p-8 sm:p-10">
          <div className="mx-auto max-w-sm">
            <h2 className="text-2xl font-bold text-slate-900">Sign in</h2>
            <p className="mt-1 text-sm text-slate-500">Enter your credentials to access your workspace.</p>

            {!online ? (
              <div className="mt-4 rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-700">
                You are offline. Signing in requires a connection.
              </div>
            ) : null}

            <form className="mt-6 space-y-4" onSubmit={submit}>
              <Field label="Email" required>
                <div className="relative">
                  <Mail className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                  <Input
                    type="email"
                    autoComplete="email"
                    required
                    value={form.email}
                    onChange={update('email')}
                    placeholder="you@company.co.id"
                    className="pl-9"
                  />
                </div>
              </Field>

              <Field label="Password" required>
                <div className="relative">
                  <Lock className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                  <Input
                    type="password"
                    autoComplete="current-password"
                    required
                    value={form.password}
                    onChange={update('password')}
                    placeholder="••••••••"
                    className="pl-9"
                  />
                </div>
              </Field>

              <Field label="Tenant code" hint="Only needed if the same email exists in more than one organization.">
                <Input value={form.tenantCode} onChange={update('tenantCode')} placeholder="e.g. DEMO" />
              </Field>

              {error ? (
                <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>
              ) : null}

              <Button type="submit" className="w-full" disabled={submitting || !online}>
                {submitting ? 'Signing in…' : 'Sign in'}
              </Button>
            </form>

            <div className="mt-6 rounded-lg border border-dashed border-slate-300 bg-slate-50 p-4 text-sm">
              <p className="font-medium text-slate-700">Demo accounts</p>
              <div className="mt-2 space-y-2">
                <button
                  type="button"
                  onClick={fillDemo('owner@demowms.id', 'Demo1234!')}
                  className="flex w-full items-center justify-between rounded-md bg-white px-3 py-2 text-left ring-1 ring-slate-200 hover:ring-blue-300"
                >
                  <span>
                    <span className="block font-medium text-slate-700">Tenant Owner</span>
                    <span className="block text-xs text-slate-500">owner@demowms.id · Demo1234!</span>
                  </span>
                  <span className="text-xs text-blue-600">Use</span>
                </button>
                <button
                  type="button"
                  onClick={fillDemo('admin@stockpilot.io', 'Admin123!')}
                  className="flex w-full items-center justify-between rounded-md bg-white px-3 py-2 text-left ring-1 ring-slate-200 hover:ring-blue-300"
                >
                  <span>
                    <span className="block font-medium text-slate-700">Platform Admin</span>
                    <span className="block text-xs text-slate-500">admin@stockpilot.io · Admin123!</span>
                  </span>
                  <span className="text-xs text-blue-600">Use</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
