import PlayerTrendChart from "@/components/hockey/PlayerTrendChart"
import { runQuery } from "@/lib/motherduck"
import Link from "next/link"
import { notFound } from "next/navigation"

interface ProfileRow {
  player_id: string
  full_name: string
  team_abbr: string
  gp_season: number
  goals_season: number
  assists_season: number
  points_season: number
  pts_avg_5g: number
  pts_avg_20g: number
  pts_zscore_5v20: number
}

interface TrendRow {
  game_date: string
  goals: number
  assists: number
  points: number
}

interface CareerRow {
  season: number
  team_abbr: string
  gp: number
  goals: number
  assists: number
  points: number
}

function escapeSql(value: string): string {
  return value.replace(/'/g, "''")
}

async function getProfile(playerId: string): Promise<ProfileRow | null> {
  const id = escapeSql(playerId)
  const result = await runQuery(`
    SELECT CAST(player_id AS VARCHAR) AS player_id,
           player_first_name || ' ' || player_last_name AS full_name,
           team_abbr, gp_season, goals_season, assists_season, points_season,
           pts_avg_5g, pts_avg_20g, pts_zscore_5v20
    FROM player_rolling_stats
    WHERE CAST(player_id AS VARCHAR) = '${id}'
      AND game_recency_rank = 1
      AND season = (SELECT MAX(season) FROM games WHERE game_type = '2')
    LIMIT 1
  `)
  return (result.rows[0] as unknown as ProfileRow | undefined) ?? null
}

async function getTrend(playerId: string): Promise<TrendRow[]> {
  const id = escapeSql(playerId)
  const result = await runQuery(`
    SELECT game_date,
           goals,
           assists,
           (goals + assists) AS points
    FROM player_game_stats
    WHERE CAST(player_id AS VARCHAR) = '${id}'
      AND season = (SELECT MAX(season) FROM games WHERE game_type = '2')
      AND game_type = '2'
    ORDER BY game_date DESC
    LIMIT 20
  `)
  const rows = result.rows as unknown as TrendRow[]
  return [...rows].reverse()
}

async function getCareer(playerId: string): Promise<CareerRow[]> {
  const id = escapeSql(playerId)
  const result = await runQuery(`
    SELECT season, team_abbr,
           COUNT(*) AS gp,
           SUM(goals) AS goals,
           SUM(assists) AS assists,
           SUM(goals + assists) AS points
    FROM player_game_stats
    WHERE CAST(player_id AS VARCHAR) = '${id}'
      AND game_type = '2'
    GROUP BY season, team_abbr
    ORDER BY season DESC, points DESC
    LIMIT 30
  `)
  return result.rows as unknown as CareerRow[]
}

export default async function PlayerPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params
  const playerId = id.trim()
  if (!playerId) notFound()

  const [profile, trend, career] = await Promise.all([
    getProfile(playerId).catch(() => null),
    getTrend(playerId).catch(() => []),
    getCareer(playerId).catch(() => []),
  ])

  if (!profile) notFound()

  const z = Number(profile.pts_zscore_5v20)

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-extrabold tracking-tight text-white">{profile.full_name}</h1>
          <p className="text-sm mt-1" style={{ color: "var(--muted)" }}>
            {profile.team_abbr} &middot; ID {profile.player_id} &middot; Regular season
          </p>
        </div>
        <Link
          href="/players"
          className="text-sm px-3 py-1.5 rounded font-medium"
          style={{ background: "rgba(255,255,255,0.06)", color: "var(--foreground)", border: "1px solid var(--card-border)" }}
        >
          All players
        </Link>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { label: "Games Played", value: Number(profile.gp_season), color: "var(--foreground)" },
          { label: "Season Points", value: `${Number(profile.goals_season)}G – ${Number(profile.assists_season)}A`, color: "var(--accent)" },
          { label: "PTS / Last 5", value: Number(profile.pts_avg_5g).toFixed(2), color: "var(--hot)" },
          {
            label: "Form",
            value: `${z >= 0 ? "+" : ""}${z.toFixed(2)}σ`,
            color: z >= 0 ? "var(--hot)" : "var(--cold)",
          },
        ].map((stat) => (
          <div
            key={stat.label}
            className="rounded p-4"
            style={{ background: "var(--card)", border: "1px solid var(--card-border)" }}
          >
            <div className="text-2xl font-extrabold tracking-tight" style={{ color: stat.color }}>
              {stat.value}
            </div>
            <div className="text-xs mt-1" style={{ color: "var(--muted)" }}>{stat.label}</div>
          </div>
        ))}
      </div>

      {/* Trend chart */}
      <div
        className="rounded p-5"
        style={{ background: "var(--card)", border: "1px solid var(--card-border)" }}
      >
        <h2 className="text-sm font-semibold text-white mb-4">Points — Last 20 Games</h2>
        {trend.length === 0 ? (
          <p style={{ color: "var(--muted)" }} className="text-sm">No trend data available.</p>
        ) : (
          <PlayerTrendChart data={trend} />
        )}
      </div>

      {/* Career table */}
      <div>
        <h2 className="text-sm font-semibold text-white mb-3">Career Stats &middot; Regular Season</h2>
        <div
          className="rounded overflow-hidden"
          style={{ background: "var(--card)", border: "1px solid var(--card-border)" }}
        >
          <table className="w-full text-sm">
            <thead>
              <tr
                style={{
                  borderBottom: "1px solid var(--card-border)",
                  color: "var(--muted)",
                  background: "rgba(255,255,255,0.03)",
                }}
              >
                <th className="text-left px-4 py-3 text-xs">Season</th>
                <th className="text-left px-4 py-3 text-xs">Team</th>
                <th className="text-center px-3 py-3 text-xs">GP</th>
                <th className="text-center px-3 py-3 text-xs">G</th>
                <th className="text-center px-3 py-3 text-xs">A</th>
                <th className="text-center px-3 py-3 text-xs">PTS</th>
              </tr>
            </thead>
            <tbody>
              {career.map((row, i) => (
                <tr key={`${row.season}-${row.team_abbr}-${i}`} style={{ borderBottom: "1px solid rgba(255,255,255,0.04)" }}>
                  <td className="px-4 py-3 text-sm text-white">{row.season}</td>
                  <td className="px-4 py-3 text-sm" style={{ color: "var(--muted)" }}>{row.team_abbr}</td>
                  <td className="px-3 py-3 text-center text-sm" style={{ color: "var(--muted)" }}>{Number(row.gp)}</td>
                  <td className="px-3 py-3 text-center text-sm text-white">{Number(row.goals)}</td>
                  <td className="px-3 py-3 text-center text-sm" style={{ color: "var(--muted)" }}>{Number(row.assists)}</td>
                  <td className="px-3 py-3 text-center text-sm font-bold" style={{ color: "var(--accent)" }}>
                    {Number(row.points)}
                  </td>
                </tr>
              ))}
              {career.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-sm" style={{ color: "var(--muted)" }}>
                    No career data found.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
