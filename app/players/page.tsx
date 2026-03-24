import PlayersTable from "@/components/hockey/PlayersTable"
import { runQuery } from "@/lib/motherduck"

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

async function getPlayers(): Promise<PlayerRow[]> {
  const result = await runQuery(`
    SELECT CAST(player_id AS VARCHAR) AS player_id,
           player_first_name || ' ' || player_last_name AS full_name,
           team_abbr, gp_season, goals_season, assists_season,
           pts_avg_5g, pts_avg_20g, pts_zscore_5v20
    FROM player_rolling_stats
    WHERE game_recency_rank = 1
      AND season = (SELECT MAX(season) FROM games WHERE game_type = '2')
      AND gp_season >= 10
    ORDER BY ABS(pts_zscore_5v20) DESC
    LIMIT 300
  `)
  return result.rows as unknown as PlayerRow[]
}

export default async function PlayersPage() {
  let players: PlayerRow[] = []
  let error = ""

  try {
    players = await getPlayers()
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to load players"
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-extrabold tracking-tight text-white">Players</h1>
        <p className="mt-1 text-sm" style={{ color: "var(--muted)" }}>
          Current season form &middot; 5-game vs 20-game baseline z-score
        </p>
      </div>

      {error ? (
        <div
          className="rounded p-4 text-sm"
          style={{ background: "var(--red-dim)", border: "1px solid var(--red)", color: "var(--red)" }}
        >
          {error}
        </div>
      ) : (
        <PlayersTable players={players} />
      )}
    </div>
  )
}
