'use client';
import { Settings, LogOut } from 'lucide-react';
import Link from 'next/link';
import { Outfit } from 'next/font/google';
import { useAuth } from '@/lib/auth';

const outfit = Outfit({
  subsets: ['latin'],
  weight: ['600', '700'],
  display: 'swap',
});

interface PageHeadingProps {
  title: React.ReactNode;
}

export function PageHeading({ title }: PageHeadingProps) {
  const { logout } = useAuth();

  return (
    <div className="flex flex-col md:flex-row md:items-center justify-between px-4 md:px-7 pb-5 gap-4" style={{ paddingTop: '16px' }}>
      <h1
        className={outfit.className}
        style={{
          fontSize: 'clamp(22px, 5vw, 36px)',
          fontWeight: 700,
          color: '#111111',
          lineHeight: 1.15,
          letterSpacing: '-0.02em',
          display: 'flex',
          alignItems: 'center',
          gap: '10px',
          margin: 0,
        }}
      >
        {title}
      </h1>
      <div className="flex items-center gap-2">
        <Link href="/settings" className="icon-btn" title="Settings" style={{ textDecoration: 'none', color: 'var(--text-2)' }}>
          <Settings size={18} />
        </Link>
        <button className="icon-btn md:hidden" onClick={() => logout()} title="Sign Out">
          <LogOut size={18} style={{ color: 'var(--color-danger)' }} />
        </button>
        <Link href="/incidents/new" className="btn-primary" style={{ textDecoration: 'none' }}>
          + New Incident
        </Link>
      </div>
    </div>
  );
}
