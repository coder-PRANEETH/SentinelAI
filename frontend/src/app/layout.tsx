import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';
import { AuthProvider } from '@/lib/auth';
import { Sidebar } from '@/components/layout/Sidebar';
import { RightPanel } from '@/components/layout/RightPanel';
import { IncidentRealtimeSync } from '@/components/realtime/IncidentRealtimeSync';

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
          <IncidentRealtimeSync />
          <div className="flex flex-col-reverse md:flex-row h-[100dvh] bg-white overflow-hidden">
            <Sidebar />
            <main className="flex-1 overflow-y-auto bg-white relative">
              {children}
            </main>
            <RightPanel />
          </div>
        </AuthProvider>
      </body>
    </html>
  );
}
