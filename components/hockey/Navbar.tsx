"use client"

import Link from "next/link"

const links = [
  { href: "/",          label: "Insights" },
  { href: "/standings", label: "Standings" },
  { href: "/teams/TOR", label: "Teams" },
  { href: "/players",   label: "Players" },
  { href: "/chat",      label: "AI Chat" },
]

export default function Navbar() {
  return (
    <nav
      style={{ background: "#0f1829", borderBottom: "1px solid #1e2d4a" }}
      className="sticky top-0 z-50"
    >
      <div className="max-w-6xl mx-auto px-4 h-14 flex items-center justify-between">
        <Link href="/" className="flex items-center gap-2 font-bold text-lg tracking-tight">
          <span>🏒</span>
          <span style={{ color: "#c9a84c" }}>THA</span>
          <span className="text-white hidden sm:inline">Analytics</span>
        </Link>
        <div className="flex items-center gap-1">
          {links.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              className="px-3 py-1.5 rounded text-sm transition-colors"
              style={{ color: "#94a3b8" }}
              onMouseOver={(e) => (e.currentTarget.style.color = "#f1f5f9")}
              onMouseOut={(e) => (e.currentTarget.style.color = "#94a3b8")}
            >
              {l.label}
            </Link>
          ))}
        </div>
      </div>
    </nav>
  )
}
