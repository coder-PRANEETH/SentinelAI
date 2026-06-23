'use client';
import { useState, FormEvent } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import { ShieldCheck, Loader2 } from 'lucide-react';
import type { ApiError } from '@/lib/api';
import { motion, AnimatePresence } from 'framer-motion';

export default function LoginPage() {
  const { login, isLoading } = useAuth();
  const router = useRouter();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    try {
      await login(username, password);
      router.replace('/dashboard');
    } catch (err) {
      const apiErr = err as ApiError;
      if (apiErr?.message?.toLowerCase().includes('locked')) {
        setError('Account temporarily locked. Try again in 30 minutes.');
      } else {
        setError('Invalid credentials. Please try again.');
      }
    }
  };

  return (
    <div style={{
      minHeight: '100vh',
      background: '#111111', // Dark background for the login page
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '24px',
    }}>
      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.2 }} style={{ width: '100%', maxWidth: '420px', display: 'flex', flexDirection: 'column', gap: '32px' }}>

        {/* Brand */}
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '14px' }}>
          <div style={{
            width: 52, height: 52, borderRadius: '16px',
            background: '#CDFF50', // Lime green
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            boxShadow: '0 8px 16px rgba(205,255,80,0.2)'
          }}>
            <ShieldCheck size={26} color="#111111" strokeWidth={2.5} />
          </div>
          <div style={{ textAlign: 'center' }}>
            <h1 style={{ fontSize: '26px', fontWeight: 800, color: '#FFFFFF', letterSpacing: '-0.03em', marginBottom: '4px' }}>
              SentinelAI
            </h1>
            <p style={{ fontSize: '13px', color: '#A0A0A0' }}>
              Traffic Incident Command Center
            </p>
          </div>
        </div>

        {/* Card */}
        <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: '20px', padding: '32px', borderRadius: '24px', boxShadow: '0 20px 40px rgba(0,0,0,0.4)', border: 'none' }}>
          <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
            <div className="form-group">
              <label htmlFor="username" className="form-label">Username</label>
              <input
                id="username" type="text"
                value={username} onChange={e => setUsername(e.target.value)}
                placeholder="Enter your username"
                autoComplete="username" required
                className="form-input transition-all focus:ring-2 focus:ring-gray-300"
                style={{ borderRadius: '9999px', height: '44px', paddingLeft: '18px', outline: 'none' }}
              />
            </div>

            <div className="form-group" style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <label htmlFor="password" className="form-label">Password</label>
              <input
                id="password" type="password"
                value={password} onChange={e => setPassword(e.target.value)}
                placeholder="Enter your password"
                autoComplete="current-password" required
                className="form-input transition-all focus:ring-2 focus:ring-gray-300"
                style={{ borderRadius: '9999px', height: '44px', paddingLeft: '18px', outline: 'none' }}
              />
            </div>

            <AnimatePresence>
              {error && (
                <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} exit={{ opacity: 0, height: 0 }} style={{ overflow: 'hidden' }}>
                  <div style={{
                    padding: '10px 14px',
                    background: 'rgba(229,62,62,0.08)',
                    border: '1px solid rgba(229,62,62,0.18)',
                    borderRadius: '10px', fontSize: '12px', color: 'var(--err)',
                    marginTop: '4px', marginBottom: '4px',
                  }}>
                    {error}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>

            <button
              id="login-submit" type="submit" className={`btn-accent hover:scale-[1.02] active:scale-95 transition-all focus:ring-2 focus:ring-gray-300 focus:outline-none ${isLoading ? 'opacity-80' : ''}`}
              disabled={isLoading}
              style={{ width: '100%', justifyContent: 'center', padding: '12px 24px', marginTop: '8px', height: '44px', display: 'flex', alignItems: 'center', gap: '8px' }}
            >
              {isLoading ? <><Loader2 size={16} className="animate-spin" /> Signing in…</> : 'Sign In'}
            </button>
          </form>

          <div style={{ position: 'relative', textAlign: 'center' }}>
            <hr style={{ border: 'none', borderTop: '1px solid var(--border)' }} />
            <span style={{
              position: 'absolute', top: '50%', left: '50%',
              transform: 'translate(-50%, -50%)',
              background: '#FFFFFF', padding: '0 12px',
              fontSize: '11px', color: '#A0A0A0', fontWeight: 600, textTransform: 'uppercase'
            }}>OR</span>
          </div>

          <button
            id="demo-login" type="button"
            className="hover:scale-[1.02] active:scale-95 transition-all focus:ring-2 focus:ring-gray-300 focus:outline-none"
            disabled={isLoading}
            onClick={() => {
              setUsername('admin');
              setPassword('admin123');
              login('admin', 'admin123')
                .then(() => router.replace('/dashboard'))
                .catch(() => setError('Demo login failed. Make sure the database is seeded.'));
            }}
            style={{
              width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center',
              padding: '12px 24px', borderRadius: '9999px', border: '1px solid #E5E5E5',
              background: '#FFFFFF', color: '#111111', fontSize: '13px', fontWeight: 600,
              cursor: 'pointer', height: '44px'
            }}
            onMouseEnter={(e) => e.currentTarget.style.background = '#F5F5F3'}
            onMouseLeave={(e) => e.currentTarget.style.background = '#FFFFFF'}
          >
            {isLoading ? <Loader2 size={16} className="animate-spin" /> : 'Demo Login'}
          </button>
        </div>

        <p style={{ fontSize: '11px', color: '#6B6B6B', textAlign: 'center' }}>
          Bengaluru Traffic Police — Authorized Personnel Only
        </p>
      </motion.div>
    </div>
  );
}
