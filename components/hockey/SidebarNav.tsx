"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { TrendingUp, BarChart2, Users, Shield, MessageSquare } from "lucide-react"

const navItems = [
  { href: "/", label: "Intelligence Feed", Icon: TrendingUp, exact: true },
  { href: "/standings", label: "Standings", Icon: BarChart2, exact: false },
  { href: "/players", label: "Players", Icon: Users, exact: false },
  { href: "/teams/TOR", label: "Teams", Icon: Shield, exact: false, matchPrefix: "/teams" },
  { href: "/chat", label: "AI Chat", Icon: MessageSquare, exact: false },
]

export default function SidebarNav() {
  const pathname = usePathname()

  return (
    <aside
      className="hidden md:flex md:w-60 md:shrink-0 md:flex-col md:justify-between py-6 px-4 border-r"
      style={{
        borderColor: "var(--glass-border)",
        background: "rgba(0,0,0,0.6)",
        backdropFilter: "blur(12px)",
      }}
    >
      <div className="space-y-8">
        {/* Logo */}
        <Link href="/" className="flex items-center gap-2.5 px-2">
          <div
            className="w-7 h-7 rounded flex items-center justify-center font-black text-xs"
            style={{ background: "var(--accent)", color: "#fff" }}
          >
            THA
          </div>
          <div>
            <div className="font-bold text-sm tracking-wide text-white leading-none">Analytics</div>
            <div className="text-xs mt-0.5" style={{ color: "var(--muted)" }}>NHL Intelligence</div>
          </div>
        </Link>

        {/* Nav links */}
        <nav className="space-y-0.5">
          {navItems.map((item) => {
            const { href, label, Icon, exact, matchPrefix } = item
            const active = exact
              ? pathname === href
              : pathname.startsWith(matchPrefix ?? href)

            return (
              <Link
                key={href}
                href={href}
                className="flex items-center gap-3 rounded px-3 py-2.5 text-sm transition-all"
                style={{
                  background: active ? "var(--accent-dim)" : "transparent",
                  color: active ? "var(--accent)" : "var(--muted)",
                  borderLeft: active ? "2px solid var(--accent)" : "2px solid transparent",
                  fontWeight: active ? 600 : 400,
                }}
              >
                <Icon size={15} strokeWidth={active ? 2.2 : 1.8} />
                <span>{label}</span>
              </Link>
            )
          })}
        </nav>
      </div>

      {/* Status footer */}
      <div
        className="rounded px-3 py-3 space-y-1"
        style={{ background: "rgba(255,255,255,0.03)", border: "1px solid var(--glass-border)" }}
      >
        <div className="flex items-center gap-2">
          <span className="w-1.5 h-1.5 rounded-full" style={{ background: "var(--accent)" }} />
          <span className="text-xs font-semibold" style={{ color: "var(--accent)" }}>Live</span>
        </div>
        <p className="text-xs leading-relaxed" style={{ color: "var(--muted)" }}>
          16 seasons · 850K+ records<br />Updated daily 09:00 CET
        </p>
      </div>
    </aside>
  )
}
