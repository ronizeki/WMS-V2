import React from 'react';
import { BrowserRouter as Router, Navigate, Route, Routes } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import { ToastProvider } from './components/ui/toaster';
import { AppLayout, RequirePermission } from './components/RequireAuth';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import Products from './pages/Products';
import Inventory from './pages/Inventory';
import Warehouses from './pages/Warehouses';
import Receiving from './pages/Receiving';
import Orders from './pages/Orders';
import Picking from './pages/Picking';
import Packing from './pages/Packing';
import Shipping from './pages/Shipping';
import Transfers from './pages/Transfers';
import Stocktake from './pages/Stocktake';
import Reports from './pages/Reports';
import Audit from './pages/Audit';
import Settings from './pages/Settings';
import Platform from './pages/Platform';
import NotFound from './pages/NotFound';

function App() {
  return (
    <ToastProvider>
      <AuthProvider>
        <Router>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route element={<AppLayout />}>
              <Route path="/" element={<Navigate to="/dashboard" replace />} />
              <Route
                path="/dashboard"
                element={
                  <RequirePermission permission="dashboard:read">
                    <Dashboard />
                  </RequirePermission>
                }
              />
              <Route
                path="/products"
                element={
                  <RequirePermission permission="product:read">
                    <Products />
                  </RequirePermission>
                }
              />
              <Route
                path="/inventory"
                element={
                  <RequirePermission permission="inventory:read">
                    <Inventory />
                  </RequirePermission>
                }
              />
              <Route
                path="/warehouses"
                element={
                  <RequirePermission permission="warehouse:read">
                    <Warehouses />
                  </RequirePermission>
                }
              />
              <Route
                path="/receiving"
                element={
                  <RequirePermission permission="inbound:read">
                    <Receiving />
                  </RequirePermission>
                }
              />
              <Route
                path="/orders"
                element={
                  <RequirePermission permission="outbound:read">
                    <Orders />
                  </RequirePermission>
                }
              />
              <Route
                path="/picking"
                element={
                  <RequirePermission permission="outbound:read">
                    <Picking />
                  </RequirePermission>
                }
              />
              <Route
                path="/packing"
                element={
                  <RequirePermission permission="outbound:read">
                    <Packing />
                  </RequirePermission>
                }
              />
              <Route
                path="/shipping"
                element={
                  <RequirePermission permission="outbound:read">
                    <Shipping />
                  </RequirePermission>
                }
              />
              <Route
                path="/transfers"
                element={
                  <RequirePermission permission="transfer:read">
                    <Transfers />
                  </RequirePermission>
                }
              />
              <Route
                path="/stocktake"
                element={
                  <RequirePermission permission="stocktake:read">
                    <Stocktake />
                  </RequirePermission>
                }
              />
              <Route
                path="/reports"
                element={
                  <RequirePermission permission="report:read">
                    <Reports />
                  </RequirePermission>
                }
              />
              <Route
                path="/audit"
                element={
                  <RequirePermission permission="audit:read">
                    <Audit />
                  </RequirePermission>
                }
              />
              <Route
                path="/settings"
                element={
                  <RequirePermission permission="settings:read">
                    <Settings />
                  </RequirePermission>
                }
              />
              <Route
                path="/platform"
                element={
                  <RequirePermission permission="tenant:manage">
                    <Platform />
                  </RequirePermission>
                }
              />
              <Route path="*" element={<NotFound />} />
            </Route>
          </Routes>
        </Router>
      </AuthProvider>
    </ToastProvider>
  );
}

export default App;
