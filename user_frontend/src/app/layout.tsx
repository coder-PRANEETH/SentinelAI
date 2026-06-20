import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700", "800"],
  variable: "--font-inter",
  display: "swap",
});

export const metadata: Metadata = {
  title: "SentinelAI — Report Road Incidents",
  description:
    "Report road incidents, breakdowns, accidents and emergencies in seconds. SentinelAI coordinates help instantly.",
  keywords: ["traffic", "incident report", "bengaluru", "emergency", "breakdown"],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={inter.variable}>
      <body className={inter.className} suppressHydrationWarning>
        {children}
      </body>
    </html>
  );
}
