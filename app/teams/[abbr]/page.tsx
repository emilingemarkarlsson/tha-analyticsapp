import { runQuery } from "@/lib/motherduck"
import { notFound } from "next/navigation"
import TeamPicker from "./TeamPicker"

const ALL_TEAMS = [
  "ANA","ARI","BOS","BUF","CAR","CGY","CHI","COL","CBJ","DAL",
  "DET","EDM","FLA","LAK","MIN","MTL","NSH","NJD","NYI","NYR",
  "OTT","PHI","PIT","SEA","SJS","STL","TBL","TOR","UTA","VAN","VGK","WSH","WPG",
]

interface GameRow {
  game_date: string
  opponent_abbr: string
  is_home: boolean
  goals_for: number
  goals_against: number
  team_points: number
}

async function getTeamGames(abbr: string): Promise<GameRow[]> {
  const result = await runQuery(`
    SELECT game_date, opponent_abbr, is_home,
           goals_for, goals_against, team_points
    FROM team_game_stats
    WHERE team_abbr = '${abbr}'
      AND game_type = '2'
      AND season = (SELECT MAX(season) FROM games WHERE game_type = '2')
    ORDER BY game_date DESC
    LIMIT 15
  `)
  return result.rows as unknown as GameRow[]
}

async function getTeamSeason(abbr: string) {
  const result = await runQuery(`
    SELECT pts_avg_5g, pts_avg_20g, pts_zscore_5v20,
           wins_last_5, losses_last_5, pts_cumulative, gp_season,
           gf_avg_10g, ga_avg_10g
    FROM team_rolling_stats
    WHERE team_abbr = '${abbr}'
      AND game_recency_rank = 1
    LIMIT 1
  `)
  return result.rows[0] ?? null
}

async function getTeamInsights(abbr: string) {
  const result = await runQuery(`
    SELECT insight_type, entity_name, headline, zscore, game_date
    FROM agent_insights
    WHERE team_abbr = '${abbr}'
    ORDER BY generated_at DESC
    LIMIT 5
  `)
  return result.rows
}

export default async function TeamPage({ params }: { params: Promise<{ abbr: string }> }) {
  const { abbr } = await params
  const upperAbbr = abbr.toUpperCase()

  if (!ALL_TEAMS.includes(upperAbbr)) notFound()

  const [games, season, insights] = await Promise.all([
    getTeamGames(upperAbbr).catch(() => []),
    getTeamSeason(upperAbbr).catch(() => null),
    getTeamInsights(upperAbbr).catch(() => []),
  ])

  const formZ = season ? Number(season.pts_zscore_5v20) : 0

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-extrabold tracking-tight text-white">{upperAbbr}</h1>
          <p className="text-sm mt-1" style={{ color: "var(--muted)" }}>
            Current season &middot; Regular season
          </p>
        </div>
        <TeamPicker current={upperAbbr} teams={ALL_TEAMS} />
      </div>

      {/* Season stat cards */}
      {season && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {[
            {
              label: "Points",
              value: Number(season.pts_cumulative),
              sub: `${Number(season.gp_season)} GP`,
              color: "var(--accent)",
            },
            {
              label: "Last 5 Record",
              value: `${Number(season.wins_last_5).toFixed(0)}–${Number(season.losses_last_5).toFixed(0)}`,
              sub: "W – L",
              color: "var(--accent)",
            },
            {
              label: "GF/10",
              value: Number(season.gf_avg_10g).toFixed(2),
              sub: `GA/10: ${Number(season.ga_avg_10g).toFixed(2)}`,
              color: "var(--hot)",
            },
            {
              label: "Form",
              value: `${formZ >= 0 ? "+" : ""}${formZ.toFixed(2)}σ`,
              sub: "5 vs 20 game",
              color: formZ >= 0 ? "var(--hot)" : "var(--cold)",
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
              <div className="text-xs font-semibold mt-1 text-white">{stat.label}</div>
              <div className="text-xs mt-0.5" style={{ color: "var(--muted)" }}>{stat.sub}</div>
            </div>
          ))}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Recent games */}
        <div className="lg:col-span-2">
          <h2
            className="text-xs font-semibold uppercase tracking-widest mb-3"
            style={{ color: "var(--muted)" }}
          >
            Recent Games
          </h2>
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
                  <th className="text-left px-4 py-3 text-xs">Date</th>
                  <th className="text-left px-4 py-3 text-xs">Opponent</th>
                  <th className="text-center px-3 py-3 text-xs">H/A</th>
                  <th className="text-center px-4 py-3 text-xs">Score</th>
                  <th className="text-center px-4 py-3 text-xs">Result</th>
                </tr>
              </thead>
              <tbody>
                {games.map((g, i) => {
                  const win = Number(g.team_points) === 2
                  const otl = Number(g.team_points) === 1
                  return (
                    <tr key={i} style={{ borderBottom: "1px solid rgba(255,255,255,0.04)" }}>
                      <td className="px-4 py-3 text-xs" style={{ color: "var(--muted)" }}>
                        {String(g.game_date).slice(0, 10)}
                      </td>
                      <td className="px-4 py-3 text-sm font-semibold text-white">
                        {g.opponent_abbr}
                      </td>
                      <td className="px-3 py-3 text-center text-xs" style={{ color: "var(--muted)" }}>
                        {g.is_home ? "HOME" : "AWAY"}
                      </td>
                      <td className="px-4 py-3 text-center font-mono text-sm text-white">
                        {Number(g.goals_for)}–{Number(g.goals_against)}
                      </td>
                      <td className="px-4 py-3 text-center">
                        <span
                          className="px-2 py-0.5 rounded text-xs font-bold"
                          style={{
                            background: win
                              ? "rgba(90,143,78,0.2)"
                              : otl
                              ? "rgba(135,206,235,0.1)"
                              : "rgba(196,30,58,0.15)",
                            color: win
                              ? "var(--accent)"
                              : otl
                              ? "var(--cold)"
                              : "var(--red)",
                          }}
                        >
                          {win ? "W" : otl ? "OTL" : "L"}
                        </span>
                      </td>
                    </tr>
                  )
                })}
                {games.length === 0 && (
                  <tr>
                    <td colSpan={5} className="px-4 py-8 text-center text-sm" style={{ color: "var(--muted)" }}>
                      No games found.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Team insights */}
        <div>
          <h2
            className="text-xs font-semibold uppercase tracking-widest mb-3"
            style={{ color: "var(--muted)" }}
          >
            AI Insights
          </h2>
          {insights.length === 0 ? (
            <div
              className="rounded p-4 text-xs"
              style={{
                background: "var(--card)",
                border: "1px solid var(--card-border)",
                color: "var(--muted)",
              }}
            >
              No recent insights for {upperAbbr}.
            </div>
          ) : (
            <div className="space-y-2">
              {insights.map((ins: Record<string, unknown>, i) => {
                const z = Number(ins.zscore)
                return (
                  <div
                    key={i}
                    className="rounded p-3"
                    style={{ background: "var(--card)", border: "1px solid var(--card-border)" }}
                  >
                    <div className="flex items-center justify-between gap-2 mb-1">
                      <span className="text-xs font-semibold text-white">{String(ins.entity_name)}</span>
                      <span
                        className="text-xs font-mono font-bold tabular-nums"
                        style={{ color: z >= 0 ? "var(--hot)" : "var(--cold)" }}
                      >
                        {z >= 0 ? "+" : ""}{z.toFixed(2)}σ
                      </span>
                    </div>
                    {ins.headline != null && (
                      <p className="text-xs leading-snug" style={{ color: "var(--muted)" }}>
                        {String(ins.headline)}
                      </p>
                    )}
                  </div>
                )
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
