'use client';
import { useState, useEffect } from 'react';
import { useAuth } from '@/lib/auth';
import { LogOut, ChevronDown, Bell } from 'lucide-react';

interface TopBarProps {
  title?: string;
  actions?: React.ReactNode;
}

export function TopBar({ title, actions }: TopBarProps) {
  const { user, logout } = useAuth();
  const [now, setNow] = useState<Date>(new Date());
  const [menuOpen, setMenuOpen] = useState(false);
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);

  const formattedTime = now.toLocaleTimeString('en-IN', {
    hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false,
  });
  const formattedDate = now.toLocaleDateString('en-IN', {
    weekday: 'short', day: 'numeric', month: 'short',
  });

  return (
    <header className="topbar">
      {/* Left — title */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
        {title && (
          <h1 className="section-heading" style={{ fontSize: '18px' }}>{title}</h1>
        )}
        {actions}
      </div>

      {/* Right — clock + user */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
        {/* Clock */}
        {mounted && (
          <div style={{ textAlign: 'right' }}>
            <div style={{
              fontSize: '13px', fontWeight: 600, color: 'var(--ink)',
              fontVariantNumeric: 'tabular-nums', letterSpacing: '-0.01em',
            }}>
              {formattedTime}
            </div>
            <div style={{ fontSize: '10px', color: 'var(--muted)' }}>
              {formattedDate}
            </div>
          </div>
        )}

        {/* Bell */}
        <div style={{ position: 'relative' }}>
          <button 
            onClick={() => setNotificationsOpen(o => !o)}
            style={{
              width: 36, height: 36, borderRadius: '10px',
              border: '1px solid var(--border)', background: 'var(--surface)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              cursor: 'pointer', color: 'var(--muted)',
            }}>
            <Bell size={15} />
          </button>

          {notificationsOpen && (
            <>
              <div
                style={{ position: 'fixed', inset: 0, zIndex: 30 }}
                onClick={() => setNotificationsOpen(false)}
              />
              <div style={{
                position: 'absolute', top: '110%', right: 0,
                background: 'var(--surface)', border: '1px solid var(--border)',
                borderRadius: '14px', padding: '12px', width: '280px',
                zIndex: 40, boxShadow: '0 8px 32px rgba(0,0,0,0.1)',
                display: 'flex', flexDirection: 'column', gap: '8px'
              }}>
                <h4 style={{ fontSize: '13px', fontWeight: 700, borderBottom: '1px solid var(--border)', paddingBottom: '8px' }}>Recent Alerts</h4>
                <div style={{ fontSize: '12px', color: 'var(--muted)', padding: '8px 0' }}>
                  No new system alerts.
                </div>
              </div>
            </>
          )}
        </div>

        {/* User pill */}
        {user && (
          <div style={{ position: 'relative' }}>
            <button
              onClick={() => setMenuOpen(o => !o)}
              style={{
                display: 'flex', alignItems: 'center', gap: '8px',
                background: 'var(--surface)', border: '1px solid var(--border)',
                borderRadius: '9999px', padding: '5px 12px 5px 6px',
                cursor: 'pointer',
              }}
            >
              <div style={{
                width: 26, height: 26, borderRadius: '50%',
                background: 'var(--ink)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                color: '#fff', fontSize: '10px', fontWeight: 700,
              }}>
                {user.username.charAt(0).toUpperCase()}
              </div>
              <span style={{ fontSize: '13px', fontWeight: 500, color: 'var(--ink)' }}>
                {user.username}
              </span>
              <ChevronDown size={12} style={{ color: 'var(--muted)' }} />
            </button>

            {menuOpen && (
              <>
                <div
                  style={{ position: 'fixed', inset: 0, zIndex: 30 }}
                  onClick={() => setMenuOpen(false)}
                />
                <div style={{
                  position: 'absolute', top: '110%', right: 0,
                  background: 'var(--surface)', border: '1px solid var(--border)',
                  borderRadius: '14px', padding: '6px', minWidth: '160px',
                  zIndex: 40, boxShadow: '0 8px 32px rgba(0,0,0,0.1)',
                }}>
                  <button
                    onClick={() => { logout(); setMenuOpen(false); }}
                    style={{
                      display: 'flex', alignItems: 'center', gap: '8px',
                      width: '100%', padding: '9px 12px', border: 'none',
                      background: 'none', cursor: 'pointer', borderRadius: '9px',
                      fontSize: '13px', color: 'var(--err)', fontWeight: 500,
                    }}
                  >
                    <LogOut size={14} />
                    Sign out
                  </button>
                </div>
              </>
            )}
          </div>
        )}
      </div>
    </header>
  );
}
