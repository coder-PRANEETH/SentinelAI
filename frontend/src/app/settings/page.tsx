'use client';
import { PageHeading } from '@/components/layout/PageHeading';
import { useAuth } from '@/lib/auth';
import { Settings, User, Bell, Lock, Shield } from 'lucide-react';
import { useState } from 'react';

export default function SettingsPage() {
  const { user } = useAuth();
  const [notificationsEnabled, setNotificationsEnabled] = useState(true);
  const [darkMode, setDarkMode] = useState(true);

  return (
    <>
      <PageHeading title={
        <>
          <span
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: '36px',
              height: '36px',
              borderRadius: '10px',
              backgroundColor: '#CDFF50',
              flexShrink: 0,
            }}
          >
            <Settings size={18} color="#111111" strokeWidth={2.5} />
          </span>
          System Settings
        </>
      } />
      
      <div className="flex-1 px-7 pb-7 overflow-auto">
        <div style={{ maxWidth: '800px', display: 'flex', flexDirection: 'column', gap: '24px' }}>
          
          {/* Profile Section */}
          <div className="card">
            <h3 style={{ fontSize: '16px', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
              <User size={18} /> User Profile
            </h3>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
              <div className="form-group">
                <label className="form-label">Username</label>
                <input type="text" className="form-input" value={user?.username || ''} disabled style={{ background: 'var(--bg)' }} />
              </div>
              <div className="form-group">
                <label className="form-label">Email</label>
                <input type="text" className="form-input" value={user?.email || ''} disabled style={{ background: 'var(--bg)' }} />
              </div>
              <div className="form-group">
                <label className="form-label">Role</label>
                <input type="text" className="form-input" value={user?.role || ''} disabled style={{ background: 'var(--bg)' }} />
              </div>
              <div className="form-group">
                <label className="form-label">Station ID</label>
                <input type="text" className="form-input" value={user?.station_id || 'Global'} disabled style={{ background: 'var(--bg)' }} />
              </div>
            </div>
          </div>

          {/* Preferences Section */}
          <div className="card">
            <h3 style={{ fontSize: '16px', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
              <Bell size={18} /> Preferences
            </h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div>
                  <div style={{ fontWeight: 600, fontSize: '14px' }}>Push Notifications</div>
                  <div style={{ fontSize: '12px', color: 'var(--muted)' }}>Receive alerts for new high-priority incidents</div>
                </div>
                <button 
                  className={`btn-${notificationsEnabled ? 'primary' : 'outline'}`}
                  onClick={() => setNotificationsEnabled(!notificationsEnabled)}
                >
                  {notificationsEnabled ? 'Enabled' : 'Disabled'}
                </button>
              </div>
              
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderTop: '1px solid var(--border)', paddingTop: '16px' }}>
                <div>
                  <div style={{ fontWeight: 600, fontSize: '14px' }}>Dark Theme</div>
                  <div style={{ fontSize: '12px', color: 'var(--muted)' }}>Use the high-contrast night UI mode</div>
                </div>
                <button 
                  className={`btn-${darkMode ? 'primary' : 'outline'}`}
                  onClick={() => setDarkMode(!darkMode)}
                >
                  {darkMode ? 'Enabled' : 'Disabled'}
                </button>
              </div>
            </div>
          </div>

          {/* Security Section */}
          <div className="card">
            <h3 style={{ fontSize: '16px', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
              <Shield size={18} /> Security
            </h3>
            <button className="btn-outline" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Lock size={14} /> Change Password
            </button>
          </div>

        </div>
      </div>
    </>
  );
}
