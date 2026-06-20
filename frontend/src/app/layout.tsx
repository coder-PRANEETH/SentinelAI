import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';
import { AuthProvider } from '@/lib/auth';
import { Sidebar } from '@/components/layout/Sidebar';
import { RightPanel } from '@/components/layout/RightPanel';

const inter = Inter({
  subsets: ['latin'],
  weight: ['400', '500', '600', '700'],
  variable: '--font-inter',
  display: 'swap',
});

export const metadata: Metadata = {
  title: 'SentinelAI — Traffic Incident Command Center',
  description:
    'AI-powered traffic incident decision support system for Bengaluru Traffic Police. Real-time incident management, resource dispatch, and predictive analytics.',
  keywords: ['traffic', 'incident management', 'bengaluru', 'AI', 'dispatch'],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={inter.variable}>
      <body
        className={inter.className}
        style={{
          fontFamily: 'var(--font-inter), system-ui, sans-serif',
          backgroundColor: '#FFFFFF',
          padding: '0px',
          minHeight: '100vh',
          margin: 0,
          boxSizing: 'border-box',
        }}
        suppressHydrationWarning
      >
        <AuthProvider>
          <div
            style={{
              display: 'flex',
              height: '100vh',
              backgroundColor: '#FFFFFF',
              overflow: 'hidden',
            }}
          >
            <Sidebar />
            <main style={{ flex: 1, overflowY: 'auto', backgroundColor: '#FFFFFF' }}>
              {children}
            </main>
            <RightPanel />
          </div>
        </AuthProvider>
      </body>
    </html>
  );
}
