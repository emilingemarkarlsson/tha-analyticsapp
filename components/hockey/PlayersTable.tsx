"use client"

import Link from "next/link"
import { useMemo, useState } from "react"
import { ChevronDown, ChevronUp, ChevronsUpDown } from "lucide-react"

interface PlayerRow {
  player_id: string
  full_name: string
  team_abbr: string
  gp_season: number
  goals_season: number
  assists_season: number
  pts_avg_5g: number
  pts_avg_20g: number
  pts_zscore_5v20: number
}

type SortKey = "pts_zscore_5v20" | "pts_avg_5g" | "pts_avg_20g" | "gp_season" | "goals_season" | "assists_season"

const COLUMNS: { key: SortKey; label: string; title: string }[] = [
  { key: "gp_season", label: "GP", title: "Games played" },
  { key: "goals_season", label: "G", title: "Goals this season" },
  { key: "assists_season", label: "A", title: "Assists this season" },
  { key: "pts_avg_5g", label: "PTS/5", title: "Avg points last 5 games" },
  { key: "pts_avg_20g", label: "PTS/20", title: "Avg points last 20 games" },
  { key: "pts_zscore_5v20", label: "Form (σ)", title: "Z-score: 5-game vs 20-game baseline" },
]

export default function PlayersTable({ players }: { players: PlayerRow[] }) {
  const [query, setQuery] = useState("")
  const [sortKey, setSortKey] = useState<SortKey>("pts_zscore_5v20")
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc")

  function handleSort(key: SortKey) {
    if (key === sortKey) {
      setSortDir((d) => (d === "desc" ? "asc" : "desc"))
    } else {
      setSortKey(key)
      setSortDir("desc")
    }
  }

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    const base = q
      ? players.filter(
          (p) =>
            String(p.full_name).toLowerCase().includes(q) ||
            String(p.team_abbr).toLowerCase().includes(q)
        )
      : players

    return [...base].sort((a, b) => {
      const av = Number(a[sortKey]) ?? 0
      const bv = Number(b[sortKey]) ?? 0
      return sortDir === "desc" ? bv - av : av - bv
    })
  }, [players, query, sortKey, sortDir])

  function SortIcon({ col }: { col: SortKey }) {
    if (col !== sortKey) return <ChevronsUpDown size={11} style={{ color: "rgba(255,255,255,0.2)", display: "inline", marginLeft: 3 }} />
    return sortDir === "desc"
      ? <ChevronDown size={11} style={{ color: "var(--accent)", display: "inline", marginLeft: 3 }} />
      : <ChevronUp size={11} style={{ color: "var(--accent)", display: "inline", marginLeft: 3 }} />
  }

  return (
    <div className="space-y-4">
      <input
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Search player or team..."
        className="w-full max-w-xs rounded px-3 py-2 text-sm outline-none"
        style={{
          background: "var(--card)",
          border: "1px solid var(--card-border)",
          color: "var(--foreground)",
        }}
      />

      <div
        className="rounded overflow-hidden"
        style={{ background: "var(--card)", border: "1px solid var(--card-border)" }}
      >
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr
                style={{
                  background: "rgba(255,255,255,0.03)",
                  borderBottom: "1px solid var(--card-border)",
                }}
              >
                <th className="text-left px-4 py-3 text-xs font-semibold" style={{ color: "var(--muted)" }}>
                  Player
                </th>
                <th className="text-center px-3 py-3 text-xs font-semibold" style={{ color: "var(--muted)" }}>
                  Team
                </th>
                {COLUMNS.map((col) => (
                  <th
                    key={col.key}
                    title={col.title}
                    onClick={() => handleSort(col.key)}
                    className="text-center px-3 py-3 text-xs font-semibold cursor-pointer select-none whitespace-nowrap"
                    style={{ color: col.key === sortKey ? "var(--accent)" : "var(--muted)" }}
                  >
                    {col.label}
                    <SortIcon col={col.key} />
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.map((p, i) => {
                const z = Number(p.pts_zscore_5v20)
                return (
                  <tr
                    key={p.player_id}
                    style={{ borderBottom: "1px solid rgba(255,255,255,0.04)" }}
                  >
                    <td className="px-4 py-2.5">
                      <Link
                        href={`/players/${p.player_id}`}
                        className="font-medium text-white text-sm hover:underline"
                        style={{ textUnderlineOffset: 3 }}
                      >
                        {p.full_name}
                      </Link>
                    </td>
                    <td className="px-3 py-2.5 text-center text-xs" style={{ color: "var(--muted)" }}>
                      {p.team_abbr}
                    </td>
                    <td className="px-3 py-2.5 text-center text-xs" style={{ color: "var(--muted)" }}>
                      {Number(p.gp_season)}
                    </td>
                    <td className="px-3 py-2.5 text-center text-xs text-white">
                      {Number(p.goals_season)}
                    </td>
                    <td className="px-3 py-2.5 text-center text-xs" style={{ color: "var(--muted)" }}>
                      {Number(p.assists_season)}
                    </td>
                    <td className="px-3 py-2.5 text-center text-xs font-medium text-white">
                      {Number(p.pts_avg_5g).toFixed(2)}
                    </td>
                    <td className="px-3 py-2.5 text-center text-xs" style={{ color: "var(--muted)" }}>
                      {Number(p.pts_avg_20g).toFixed(2)}
                    </td>
                    <td
                      className="px-3 py-2.5 text-center text-xs font-mono font-bold"
                      style={{ color: z >= 0 ? "var(--hot)" : "var(--cold)" }}
                    >
                      {z >= 0 ? "+" : ""}{z.toFixed(2)}
                    </td>
                  </tr>
                )
              })}
              {filtered.length === 0 && (
                <tr>
                  <td
                    colSpan={8}
                    className="px-4 py-8 text-center text-sm"
                    style={{ color: "var(--muted)" }}
                  >
                    No players matched your search.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        <div
          className="px-4 py-2.5 text-xs"
          style={{ color: "var(--muted)", borderTop: "1px solid var(--card-border)" }}
        >
          {filtered.length} players &middot; Click column headers to sort
        </div>
      </div>
    </div>
  )
}
