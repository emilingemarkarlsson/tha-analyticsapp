import type { Metadata } from "next"
import { Inter } from "next/font/google"
import "./globals.css"
import SidebarNav from "@/components/hockey/SidebarNav"
import Link from "next/link"

const inter = Inter({ subsets: ["latin"], variable: "--font-inter", weight: ["400", "500", "600", "700", "800", "900"] })

export const metadata: Metadata = {
  title: "THA Analytics – NHL Hockey Intelligence",
  description: "16 seasons of NHL data. AI-powered insights. Daily trends.",
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${inter.variable} h-full`}>
      <body className="min-h-full" style={{ background: "var(--background)", color: "var(--foreground)" }}>
        <div className="min-h-screen md:flex">
          <SidebarNav />

          <div className="flex-1 min-w-0">
            {/* Mobile top bar */}
            <header
              className="md:hidden sticky top-0 z-40 px-4 h-14 flex items-center justify-between border-b"
              style={{ borderColor: "var(--glass-border)", background: "rgba(0,0,0,0.9)", backdropFilter: "blur(12px)" }}
            >
              <Link href="/" className="font-bold tracking-tight text-sm">
                <span style={{ color: "var(--accent)" }}>THA</span>
                <span className="text-white ml-1.5">Analytics</span>
              </Link>
              <Link
                href="/chat"
                className="text-xs px-3 py-1.5 rounded font-semibold"
                style={{ background: "var(--accent)", color: "#fff" }}
              >
                AI Chat
              </Link>
            </header>

            <main className="p-4 md:p-8 max-w-7xl">{children}</main>
          </div>
        </div>
      </body>
    </html>
  )
}
