"use client"

import { useRouter } from "next/navigation"

export default function TeamPicker({ current, teams }: { current: string; teams: string[] }) {
  const router = useRouter()
  return (
    <select
      value={current}
      onChange={(e) => router.push(`/teams/${e.target.value}`)}
      className="rounded-md px-3 py-2 text-sm font-medium outline-none cursor-pointer"
      style={{
        background: "var(--card)",
        border: "1px solid var(--card-border)",
        color: "var(--foreground)",
      }}
    >
      {teams.map((t) => (
        <option key={t} value={t}>
          {t}
        </option>
      ))}
    </select>
  )
}
