import { Settings } from 'lucide-react';
import Link from 'next/link';
import { Outfit } from 'next/font/google';

const outfit = Outfit({
  subsets: ['latin'],
  weight: ['600', '700'],
  display: 'swap',
});

interface PageHeadingProps {
  title: React.ReactNode;
}

export function PageHeading({ title }: PageHeadingProps) {
  return (
    <div className="flex items-center justify-between px-7 pb-5" style={{ paddingLeft: '20px', paddingTop: '16px' }}>
      <h1
        className={outfit.className}
        style={{
          fontSize: '36px',
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
        <button className="icon-btn">
          <Settings size={18} className="text-text-2" />
        </button>
        <Link href="/incidents/new" className="btn-primary" style={{ textDecoration: 'none' }}>
          + New Incident
        </Link>
      </div>
    </div>
  );
}
