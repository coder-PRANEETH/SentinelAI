'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  LayoutDashboard, FilePlus, Map as MapIcon, Radio,
  Package, BarChart2, Clock, Plus, Settings, LogOut, User as UserIcon
} from 'lucide-react';
import { useAuth } from '@/lib/auth';

const NAV = [
  { href: '/dashboard',    icon: LayoutDashboard, label: 'Dashboard' },
  { href: '/map',          icon: MapIcon,         label: 'Map View' },
  { href: '/stations',     icon: Radio,           label: 'Stations' },
  { href: '/resources',    icon: Package,         label: 'Resources' },
  { href: '/analytics',    icon: BarChart2,       label: 'Analytics' },
  { href: '/history',      icon: Clock,           label: 'History' },
];

export function Sidebar() {
  const path = usePathname();
  const { user, logout } = useAuth();

  if (path === '/login') return null;

  return (
    <aside className="sidebar">
      {/* Create Button */}
      <Link href="/incidents/new" className="sidebar-create-btn" title="New Incident">
        <Plus size={18} style={{ flexShrink: 0 }} />
        <span>New Incident</span>
      </Link>

      {/* Nav icons */}
      <nav className="sidebar-nav">
        {NAV.map(({ href, icon: Icon, label }) => {
          const active = path === href || path.startsWith(href + '/');
          return (
            <Link
              key={href}
              href={href}
              className={`sidebar-icon-btn ${active ? 'active' : ''}`}
              title={label}
            >
              <Icon size={18} style={{ flexShrink: 0 }} />
              <span>{label}</span>
            </Link>
          );
        })}
      </nav>

      <div style={{ flex: 1 }} />

      {/* Bottom: settings + avatar */}
      <div className="sidebar-bottom">
        <Link
          href="/settings"
          className={`sidebar-icon-btn ${path === '/settings' ? 'active' : ''}`}
          title="Settings"
        >
          <Settings size={18} style={{ flexShrink: 0 }} />
          <span>Settings</span>
        </Link>

        <div className="sidebar-user">
          <div className="sidebar-user-header">
            <div className="sidebar-user-avatar">
              <UserIcon size={18} strokeWidth={2.5} />
            </div>
            <div className="sidebar-user-info">
              <span className="sidebar-user-name">{user?.username || 'User'}</span>
              <span className="sidebar-user-role">{user?.role ? user.role.replace('_', ' ') : 'Role'}</span>
            </div>
          </div>
          <button className="sidebar-logout-btn" onClick={() => logout()}>
            <LogOut size={14} />
            <span>Sign Out</span>
          </button>
        </div>
      </div>
    </aside>
  );
}
