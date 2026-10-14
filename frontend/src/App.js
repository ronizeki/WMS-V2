import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { Toaster } from './components/ui/toaster';
import Layout from './components/layout/Layout';
import Dashboard from './pages/Dashboard';
import Products from './pages/Products';
import Inventory from './pages/Inventory';
import Warehouses from './pages/Warehouses';
import Receiving from './pages/Receiving';
import Picking from './pages/Picking';
import Packing from './pages/Packing';
import Shipping from './pages/Shipping';
import Transfers from './pages/Transfers';
import Stocktake from './pages/Stocktake';
import Reports from './pages/Reports';
import Settings from './pages/Settings';
import NotFound from './pages/NotFound';

function App() {
  return (
    <Router>
      <Layout>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/products" element={<Products />} />
          <Route path="/inventory" element={<Inventory />} />
          <Route path="/warehouses" element={<Warehouses />} />
          <Route path="/receiving" element={<Receiving />} />
          <Route path="/picking" element={<Picking />} />
          <Route path="/packing" element={<Packing />} />
          <Route path="/shipping" element={<Shipping />} />
          <Route path="/transfers" element={<Transfers />} />
          <Route path="/stocktake" element={<Stocktake />} />
          <Route path="/reports" element={<Reports />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </Layout>
      <Toaster />
    </Router>
  );
}

export default App;