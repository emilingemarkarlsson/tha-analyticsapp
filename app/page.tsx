import { runQuery } from "@/lib/motherduck"
import Link from "next/link"
import { TrendingUp, TrendingDown, Minus } from "lucide-react"

const INSIGHT_TYPE_LABEL: Record<string, string> = {
  hot_streak: "Hot Streak",
  breakout: "Breakout",
  cold_spell: "Cold Spell",
  slump: "Slump",
  goalie_hot: "Goalie Hot",
  goalie_cold: "Goalie Cold",
  team_surge: "Team Surge",
  team_collapse: "Team Collapse",
  possession_edge: "Possession Edge",
}

const INSIGHT_COLOR: Record<string, string> = {
  hot_streak: "var(--hot)",
  breakout: "var(--accent)",
  cold_spell: "var(--cold)",
  slump: "var(--muted)",
  goalie_hot: "var(--accent)",
  goalie_cold: "var(--cold)",
  team_surge: "var(--hot)",
  team_collapse: "var(--red)",
  possession_edge: "var(--sky)",
}

interface Insight {
  insight_type: string
  entity_name: string
  team_abbr: string
  zscore: number
  severity: number
  headline: string
  body: string
  game_date: string
  generated_at: string
}

async function getInsights(): Promise<Insight[]> {
  const result = await runQuery(`
    SELECT insight_type, entity_name, team_abbr, zscore, severity,
           headline, body, game_date, generated_at
    FROM agent_insights
    ORDER BY generated_at DESC, ABS(zscore) DESC
    LIMIT 25
  `)
  return result.rows as unknown as Insight[]
}

async function getTopPlayers() {
  const result = await runQuery(`
    SELECT player_first_name || ' ' || player_last_name AS name,
           CAST(player_id AS VARCHAR) AS player_id,
           team_abbr, pts_avg_5g, pts_zscore_5v20
    FROM player_rolling_stats
    WHERE game_recency_rank = 1
      AND season = (SELECT MAX(season) FROM games WHERE game_type = '2')
      AND gp_season >= 20
    ORDER BY pts_zscore_5v20 DESC
    LIMIT 8
  `)
  return result.rows
}

async function getColdPlayers() {
  const result = await runQuery(`
    SELECT player_first_name || ' ' || player_last_name AS name,
           CAST(player_id AS VARCHAR) AS player_id,
           team_abbr, pts_avg_5g, pts_zscore_5v20
    FROM player_rolling_stats
    WHERE game_recency_rank = 1
      AND season = (SELECT MAX(season) FROM games WHERE game_type = '2')
      AND gp_season >= 20
    ORDER BY pts_zscore_5v20 ASC
    LIMIT 5
  `)
  return result.rows
}

export default async function HomePage() {
  const [insightsRes, playersRes, coldRes] = await Promise.allSettled([
    getInsights(),
    getTopPlayers(),
    getColdPlayers(),
  ])

  const insights = insightsRes.status === "fulfilled" ? insightsRes.value : []
  const topPlayers = playersRes.status === "fulfilled" ? playersRes.value : []
  const coldPlayers = coldRes.status === "fulfilled" ? coldRes.value : []
  const insightsError = insightsRes.status === "rejected" ? insightsRes.reason : null
  const latestDate = insights[0]?.game_date ?? null

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-extrabold tracking-tight text-white">
            Intelligence Feed
          </h1>
          <p className="mt-1 text-sm" style={{ color: "var(--muted)" }}>
            AI-generated anomaly detection across 16 seasons of NHL data
            {latestDate && (
              <>
                {" "}&middot; Last update:{" "}
                <span className="text-white">{String(latestDate).slice(0, 10)}</span>
              </>
            )}
          </p>
        </div>
        <Link
          href="/chat"
          className="shrink-0 text-sm px-4 py-2 rounded font-semibold transition-all"
          style={{ background: "var(--accent)", color: "#fff" }}
        >
          Ask AI
        </Link>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Insights feed */}
        <div className="lg:col-span-2 space-y-2.5">
          <h2 className="text-xs font-semibold uppercase tracking-widest pb-1" style={{ color: "var(--muted)" }}>
            Latest Insights
          </h2>

          {insightsError && (
            <div
              className="rounded p-4 text-sm"
              style={{ background: "var(--red-dim)", border: "1px solid var(--red)", color: "var(--red)" }}
            >
              {String((insightsError as Error)?.message ?? insightsError)}
            </div>
          )}

          {insights.length === 0 && !insightsError ? (
            <div
              className="rounded p-8 text-center text-sm"
              style={{ background: "var(--card)", border: "1px solid var(--card-border)", color: "var(--muted)" }}
            >
              No insights yet — pipeline runs daily at 09:00 CET.
            </div>
          ) : (
            insights.map((insight, i) => {
              const accentColor = INSIGHT_COLOR[insight.insight_type] ?? "var(--accent)"
              const zscore = Number(insight.zscore)
              return (
                <div
                  key={i}
                  className="rounded p-4 space-y-2 transition-colors"
                  style={{
                    background: "var(--card)",
                    border: "1px solid var(--card-border)",
                    borderLeft: `2px solid ${accentColor}`,
                  }}
                >
                  <div className="flex items-start justify-between gap-3 flex-wrap">
                    <div className="flex items-center gap-2 min-w-0">
                      <span className="font-semibold text-white text-sm">{insight.entity_name}</span>
                      <span
                        className="text-xs px-1.5 py-0.5 rounded font-mono"
                        style={{ background: "rgba(255,255,255,0.06)", color: "var(--muted)" }}
                      >
                        {insight.team_abbr}
                      </span>
                    </div>
                    <div className="flex items-center gap-2.5 shrink-0">
                      <span
                        className="text-xs px-2 py-0.5 rounded font-medium"
                        style={{ color: accentColor, background: "rgba(255,255,255,0.05)" }}
                      >
                        {INSIGHT_TYPE_LABEL[insight.insight_type] ?? insight.insight_type}
                      </span>
                      <span
                        className="text-xs font-mono font-bold tabular-nums"
                        style={{ color: zscore >= 0 ? "var(--hot)" : "var(--cold)" }}
                      >
                        {zscore >= 0 ? "+" : ""}{zscore.toFixed(2)}σ
                      </span>
                    </div>
                  </div>

                  {insight.headline && (
                    <p className="text-sm font-medium text-white leading-snug">{insight.headline}</p>
                  )}
                  {insight.body && (
                    <p className="text-xs leading-relaxed" style={{ color: "var(--muted)" }}>
                      {insight.body}
                    </p>
                  )}

                  <div className="flex items-center justify-between pt-0.5">
                    <span className="text-xs" style={{ color: "rgba(255,255,255,0.2)" }}>
                      {String(insight.game_date).slice(0, 10)}
                    </span>
                    {insight.severity != null && (
                      <div className="flex items-center gap-0.5">
                        {[1, 2, 3, 4, 5].map((n) => (
                          <span
                            key={n}
                            className="w-1.5 h-1.5 rounded-full"
                            style={{
                              background: n <= Number(insight.severity) ? accentColor : "rgba(255,255,255,0.1)",
                            }}
                          />
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              )
            })
          )}
        </div>

        {/* Right sidebar */}
        <div className="space-y-6">
          {/* Hot players */}
          <div>
            <h2 className="text-xs font-semibold uppercase tracking-widest mb-3 flex items-center gap-2" style={{ color: "var(--muted)" }}>
              <TrendingUp size={12} style={{ color: "var(--hot)" }} />
              Hottest Right Now
            </h2>
            <div className="rounded overflow-hidden" style={{ background: "var(--card)", border: "1px solid var(--card-border)" }}>
              {topPlayers.length === 0 ? (
                <div className="p-4 text-xs" style={{ color: "var(--muted)" }}>No data</div>
              ) : (
                topPlayers.map((p: Record<string, unknown>, i) => (
                  <Link
                    key={i}
                    href={`/players/${p.player_id}`}
                    className="flex items-center justify-between px-4 py-2.5 transition-colors"
                    style={{
                      borderBottom: i < topPlayers.length - 1 ? "1px solid var(--card-border)" : "none",
                    }}
                  >
                    <div className="flex items-center gap-2.5 min-w-0">
                      <span className="text-xs tabular-nums w-4 text-right" style={{ color: "rgba(255,255,255,0.25)" }}>
                        {i + 1}
                      </span>
                      <div className="min-w-0">
                        <div className="text-xs font-medium text-white truncate">{String(p.name)}</div>
                        <div className="text-xs" style={{ color: "var(--muted)" }}>{String(p.team_abbr)}</div>
                      </div>
                    </div>
                    <div className="text-right shrink-0">
                      <div className="text-xs font-mono font-bold" style={{ color: "var(--hot)" }}>
                        +{Number(p.pts_zscore_5v20).toFixed(2)}σ
                      </div>
                      <div className="text-xs" style={{ color: "var(--muted)" }}>
                        {Number(p.pts_avg_5g).toFixed(2)} pts/g
                      </div>
                    </div>
                  </Link>
                ))
              )}
            </div>
          </div>

          {/* Cold players */}
          {coldPlayers.length > 0 && (
            <div>
              <h2 className="text-xs font-semibold uppercase tracking-widest mb-3 flex items-center gap-2" style={{ color: "var(--muted)" }}>
                <TrendingDown size={12} style={{ color: "var(--cold)" }} />
                Slumping
              </h2>
              <div className="rounded overflow-hidden" style={{ background: "var(--card)", border: "1px solid var(--card-border)" }}>
                {coldPlayers.map((p: Record<string, unknown>, i) => (
                  <Link
                    key={i}
                    href={`/players/${p.player_id}`}
                    className="flex items-center justify-between px-4 py-2.5 transition-colors"
                    style={{ borderBottom: i < coldPlayers.length - 1 ? "1px solid var(--card-border)" : "none" }}
                  >
                    <div className="flex items-center gap-2.5 min-w-0">
                      <span className="text-xs tabular-nums w-4 text-right" style={{ color: "rgba(255,255,255,0.25)" }}>
                        {i + 1}
                      </span>
                      <div className="min-w-0">
                        <div className="text-xs font-medium text-white truncate">{String(p.name)}</div>
                        <div className="text-xs" style={{ color: "var(--muted)" }}>{String(p.team_abbr)}</div>
                      </div>
                    </div>
                    <div className="text-right shrink-0">
                      <div className="text-xs font-mono font-bold" style={{ color: "var(--cold)" }}>
                        {Number(p.pts_zscore_5v20).toFixed(2)}σ
                      </div>
                      <div className="text-xs" style={{ color: "var(--muted)" }}>
                        {Number(p.pts_avg_5g).toFixed(2)} pts/g
                      </div>
                    </div>
                  </Link>
                ))}
              </div>
            </div>
          )}

          {/* Methodology note */}
          <div
            className="rounded p-4 space-y-1.5"
            style={{ background: "var(--card)", border: "1px solid var(--card-border)" }}
          >
            <div className="flex items-center gap-1.5">
              <Minus size={10} style={{ color: "var(--accent)" }} />
              <h3 className="text-xs font-semibold uppercase tracking-widest" style={{ color: "var(--accent)" }}>
                Methodology
              </h3>
            </div>
            <p className="text-xs leading-relaxed" style={{ color: "var(--muted)" }}>
              Z-scores compare a player&apos;s last 5 games against their 20-game rolling baseline.
              Anomalies beyond ±1.5σ trigger an insight. Data refreshes daily at 09:00 CET.
            </p>
            <Link
              href="/players"
              className="inline-block text-xs font-semibold mt-1"
              style={{ color: "var(--accent)" }}
            >
              Browse all players
            </Link>
          </div>
        </div>
      </div>
    </div>
  )
}
