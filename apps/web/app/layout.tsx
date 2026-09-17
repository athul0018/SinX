import { Inter } from "next/font/google";
import type { Metadata, Viewport } from "next";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-sans",
});

export const metadata: Metadata = {
  title: "GSB Infrastructure",
  description: "Project attendance, plans, and progress for GSB Infrastructure",
  manifest: "/manifest.json",
  appleWebApp: { capable: true, title: "GSB Infrastructure" },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#014465",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className={`${inter.className} ${inter.variable}`}>{children}</body>
    </html>
  );
}
