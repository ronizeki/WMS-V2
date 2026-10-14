import React, { useEffect, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import {
  Archive,
  BarChart3,
  Building2,
  ChevronLeft,
  ClipboardCheck,
  ClipboardList,
  LayoutDashboard,
  LogOut,
  Menu,
  Package,
  ScrollText,
  Settings as SettingsIcon,
  ShoppingCart,
  Truck,
  User as UserIcon,
  Warehouse as WarehouseIcon,
  Wifi,
  WifiOff,
  X,
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { useOnlineStatus } from '../../hooks/useApi';
import { initials } from '../../lib/format';
import { cn } from '../../lib/utils';
import { DropdownItem, DropdownMenu } from '../ui/dropdown';
import { OfflineBanner } from '../common/OfflineBanner';
import { InstallPrompt } from '../common/InstallPrompt';
import { TenantSwitcher } from './TenantSwitcher';

const NAV_SECTIONS = [
  {
    title: 'Overview',
    items: [{ name: 'Dashboard', href: '/dashboard', icon: LayoutDashboard, permission: 'dashboard:read' }],
  },
  {
    title: 'Catalog',
    items: [
      { name: 'Products', href: '/products', icon: Package, permission: 'product:read' },
      { name: 'Warehouses', href: '/warehouses', icon: Building2, permission: 'warehouse:read' },
    ],
  },
  {
    title: 'Operations',
    items: [
      { name: 'Inventory', href: '/inventory', icon: WarehouseIcon, permission: 'inventory:read' },
      { name: 'Receiving', href: '/receiving', icon: Truck, permission: 'inbound:read' },
      { name: 'Orders', href: '/orders', icon: ShoppingCart, permission: 'outbound:read' },
      { name: 'Picking', href: '/picking', icon: ClipboardList, permission: 'outbound:read' },
      { name: 'Packing', href: '/packing', icon: Package, permission: 'outbound:read' },
      { name: 'Shipping', href: '/shipping', icon: Truck, permission: 'outbound:read' },
      { name: 'Transfers', href: '/transfers', icon: Archive, permission: 'transfer:read' },
      { name: 'Stocktake', href: '/stocktake', icon: ClipboardCheck, permission: 'stocktake:read' },
    ],
  },
  {
    title: 'Insights',
    items: [
      { name: 'Reports', href: '/reports', icon: BarChart3, permission: 'report:read' },
      { name: 'Audit Log', href: '/audit', icon: ScrollText, permission: 'audit:read' },
    ],
  },
  {
    title: 'Administration',
    items: [
      { name: 'Settings', href: '/settings', icon: SettingsIcon, permission: 'settings:read' },
      { name: 'Platform', href: '/platform', icon: Building2, permission: 'tenant:manage' },
    ],
  },
];

export default function Layout({ children }) {
  const location = useLocation();
  const { user, permissions, logout, isPlatformAdmin } = useAuth();
  const online = useOnlineStatus();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(false);

  useEffect(() => {
    setMobileOpen(false);
  }, [location.pathname]);

  const visibleSections = NAV_SECTIONS.map((section) => ({
    ...section,
    items: section.items.filter((item) => permissions.includes(item.permission)),
  })).filter((section) => section.items.length > 0);

  const NavContent = ({ onNavigate }) => (
    <nav className="flex-1 space-y-6 overflow-y-auto px-3 py-4">
      {visibleSections.map((section) => (
        <div key={section.title}>
          {!collapsed ? (
            <p className="px-3 pb-2 text-xs font-semibold uppercase tracking-wider text-slate-400">
              {section.title}
            </p>
          ) : null}
          <ul className="space-y-1">
            {section.items.map((item) => {
              const active = location.pathname === item.href || location.pathname.startsWith(`${item.href}/`);
              const Icon = item.icon;
              return (
                <li key={item.href}>
                  <Link
                    to={item.href}
                    onClick={onNavigate}
                    title={collapsed ? item.name : undefined}
                    className={cn(
                      'flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition',
                      active
                        ? 'bg-blue-50 text-blue-700'
                        : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900',
                      collapsed && 'justify-center px-2'
                    )}
                  >
                    <Icon className="h-4 w-4 shrink-0" />
                    {!collapsed ? <span className="truncate">{item.name}</span> : null}
                  </Link>
                </li>
              );
            })}
          </ul>
        </div>
      ))}
    </nav>
  );

  const Brand = (
    <div className={cn('flex items-center gap-2 px-4 py-4', collapsed && 'justify-center px-2')}>
      <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-blue-600 text-sm font-bold text-white">
        SP
      </div>
      {!collapsed ? (
        <div className="leading-tight">
          <p className="text-sm font-semibold text-slate-900">StockPilot</p>
          <p className="text-xs text-slate-500">WMS</p>
        </div>
      ) : null}
    </div>
  );

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Desktop sidebar */}
      <aside
        className={cn(
          'fixed inset-y-0 left-0 z-30 hidden flex-col border-r border-slate-200 bg-white transition-all lg:flex',
          collapsed ? 'w-[68px]' : 'w-64'
        )}
      >
        {Brand}
        <NavContent />
        <button
          type="button"
          onClick={() => setCollapsed((v) => !v)}
          className="flex items-center justify-center gap-2 border-t border-slate-200 py-3 text-xs text-slate-500 hover:bg-slate-50"
        >
          <ChevronLeft className={cn('h-4 w-4 transition-transform', collapsed && 'rotate-180')} />
          {!collapsed ? 'Collapse' : null}
        </button>
      </aside>

      {/* Mobile sidebar */}
      {mobileOpen ? (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-slate-900/50" onClick={() => setMobileOpen(false)} />
          <aside className="absolute inset-y-0 left-0 flex w-64 flex-col bg-white">
            <div className="flex items-center justify-between border-b border-slate-200 pr-2">
              {Brand}
              <button type="button" onClick={() => setMobileOpen(false)} aria-label="Close menu">
                <X className="h-5 w-5 text-slate-500" />
              </button>
            </div>
            <NavContent onNavigate={() => setMobileOpen(false)} />
          </aside>
        </div>
      ) : null}

      <div className={cn('flex min-h-screen flex-col', collapsed ? 'lg:pl-[68px]' : 'lg:pl-64')}>
        <OfflineBanner />
        <InstallPrompt />
        <header className="sticky top-0 z-20 flex h-16 items-center gap-3 border-b border-slate-200 bg-white/95 px-4 backdrop-blur">
          <button
            type="button"
            className="rounded-md p-2 text-slate-500 hover:bg-slate-100 lg:hidden"
            onClick={() => setMobileOpen(true)}
            aria-label="Open menu"
          >
            <Menu className="h-5 w-5" />
          </button>

          <div className="flex flex-1 items-center gap-3">
            {isPlatformAdmin ? <TenantSwitcher /> : null}
          </div>

          <div className="flex items-center gap-3">
            <span
              className={cn(
                'hidden items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium sm:inline-flex',
                online ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-700'
              )}
              title={online ? 'Connected' : 'Offline'}
            >
              {online ? <Wifi className="h-3.5 w-3.5" /> : <WifiOff className="h-3.5 w-3.5" />}
              {online ? 'Online' : 'Offline'}
            </span>

            <DropdownMenu
              trigger={
                <button
                  type="button"
                  className="flex items-center gap-2 rounded-full border border-slate-200 py-1 pl-1 pr-3 transition hover:bg-slate-50"
                >
                  <span className="flex h-8 w-8 items-center justify-center rounded-full bg-blue-600 text-xs font-semibold text-white">
                    {initials(user?.full_name, user?.email)}
                  </span>
                  <span className="hidden text-left leading-tight sm:block">
                    <span className="block text-sm font-medium text-slate-700">{user?.full_name}</span>
                    <span className="block text-xs text-slate-400">
                      {(user?.role_codes || []).length ? user.role_codes[0].replace(/_/g, ' ') : user?.email}
                    </span>
                  </span>
                </button>
              }
            >
              <div className="border-b border-slate-100 px-3 py-2">
                <p className="text-sm font-medium text-slate-700">{user?.full_name}</p>
                <p className="text-xs text-slate-500">{user?.email}</p>
              </div>
              <DropdownItem icon={UserIcon} onClick={() => window.location.assign('/settings')}>
                Account &amp; settings
              </DropdownItem>
              <DropdownItem icon={LogOut} className="text-red-600" onClick={logout}>
                Sign out
              </DropdownItem>
            </DropdownMenu>
          </div>
        </header>

        <main className="flex-1 px-4 py-6 sm:px-6 lg:px-8">{children}</main>

        <footer className="border-t border-slate-200 px-6 py-3 text-center text-xs text-slate-400">
          StockPilot WMS · Multi-tenant Warehouse Management System
        </footer>
      </div>
    </div>
  );
}
