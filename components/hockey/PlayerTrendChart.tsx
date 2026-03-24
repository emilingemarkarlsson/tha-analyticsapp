"use client"

import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"

interface TrendPoint {
  game_date: string
  points: number
  goals: number
  assists: number
}

export default function PlayerTrendChart({ data }: { data: TrendPoint[] }) {
  return (
    <div className="h-80 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 12, right: 20, left: 0, bottom: 0 }}>
          <CartesianGrid stroke="var(--card-border)" strokeDasharray="3 3" />
          <XAxis
            dataKey="game_date"
            tick={{ fill: "var(--muted)", fontSize: 12 }}
            tickFormatter={(v: string) => String(v).slice(5, 10)}
          />
          <YAxis tick={{ fill: "var(--muted)", fontSize: 12 }} />
          <Tooltip
            contentStyle={{ background: "var(--background)", border: "1px solid var(--card-border)", color: "var(--foreground)" }}
            labelStyle={{ color: "var(--muted)" }}
          />
          <Legend />
          <Line type="monotone" dataKey="points" stroke="var(--accent)" strokeWidth={2} dot={false} name="Points" />
          <Line type="monotone" dataKey="goals" stroke="var(--hot)" strokeWidth={1.5} dot={false} name="Goals" />
          <Line type="monotone" dataKey="assists" stroke="var(--cold)" strokeWidth={1.5} dot={false} name="Assists" />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
