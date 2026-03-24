import { runQuery } from "@/lib/motherduck"

interface Standing {
  teamAbbrev: string
  teamName: string
  wins: number
  losses: number
  otLosses: number
  points: number
  gamesPlayed: number
  goalFor: number
  goalAgainst: number
  divisionAbbrev: string
  conferenceAbbrev: string
  streakCode: string
  streakCount: number
}

const DIVISION_ORDER = ["A", "M", "C", "P"]
const DIVISION_NAMES: Record<string, string> = {
  A: "Atlantic", M: "Metropolitan", C: "Central", P: "Pacific",
}
const CONFERENCE_MAP: Record<string, string> = {
  A: "E", M: "E", C: "W", P: "W",
}

async function getStandings(): Promise<Standing[]> {
  const result = await runQuery(`
    SELECT teamAbbrev, teamName, wins, losses, otLosses, points, gamesPlayed,
           goalFor, goalAgainst, divisionAbbrev, conferenceAbbrev,
           streakCode, streakCount
    FROM standings
    WHERE season = (SELECT MAX(season) FROM standings)
    ORDER BY divisionAbbrev, points DESC
    LIMIT 40
  `)
  return result.rows as unknown as Standing[]
}

function getPlayoffStatus(
  index: number,
  team: Standing,
  allStandings: Standing[]
): { label: string; color: string } | null {
  if (index < 3) {
    return { label: "DIV", color: "var(--accent)" }
  }
  const conf = CONFERENCE_MAP[team.divisionAbbrev]
  const divTopTeams = DIVISION_ORDER
    .filter((d) => CONFERENCE_MAP[d] === conf)
    .flatMap((d) =>
      allStandings
        .filter((t) => t.divisionAbbrev === d)
        .sort((a, b) => Number(b.points) - Number(a.points))
        .slice(0, 3)
    )
  const confTeams = allStandings
    .filter((t) => CONFERENCE_MAP[t.divisionAbbrev] === conf)
    .sort((a, b) => Number(b.points) - Number(a.points))
  const wildCardTeams = confTeams
    .filter((t) => !divTopTeams.some((dt) => dt.teamAbbrev === t.teamAbbrev))
    .slice(0, 2)
  if (wildCardTeams.some((t) => t.teamAbbrev === team.teamAbbrev)) {
    return { label: "WC", color: "var(--sky)" }
  }
  return null
}

export default async function StandingsPage() {
  let standings: Standing[] = []
  let error = ""

  try {
    standings = await getStandings()
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to load standings"
  }

  const byDivision = DIVISION_ORDER.reduce((acc, div) => {
    acc[div] = standings.filter((s) => s.divisionAbbrev === div)
    return acc
  }, {} as Record<string, Standing[]>)

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-extrabold tracking-tight text-white">Standings</h1>
        <p className="mt-1 text-sm" style={{ color: "var(--muted)" }}>
          Current season &middot; Regular season
        </p>
      </div>

      {/* Legend */}
      <div className="flex items-center gap-5 text-xs" style={{ color: "var(--muted)" }}>
        <div className="flex items-center gap-1.5">
          <span
            className="text-xs font-bold px-1.5 py-0.5 rounded"
            style={{ color: "var(--accent)", border: "1px solid var(--accent)", lineHeight: 1 }}
          >
            DIV
          </span>
          <span>Division leader (top 3)</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span
            className="text-xs font-bold px-1.5 py-0.5 rounded"
            style={{ color: "var(--sky)", border: "1px solid var(--sky)", lineHeight: 1 }}
          >
            WC
          </span>
          <span>Wild card</span>
        </div>
      </div>

      {error && (
        <div
          className="rounded p-4 text-sm"
          style={{ background: "var(--red-dim)", border: "1px solid var(--red)", color: "var(--red)" }}
        >
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        {DIVISION_ORDER.map((div) => {
          const teams = byDivision[div] ?? []
          if (teams.length === 0) return null
          return (
            <div
              key={div}
              className="rounded overflow-hidden"
              style={{ background: "var(--card)", border: "1px solid var(--card-border)" }}
            >
              <div
                className="px-4 py-3 flex items-center justify-between"
                style={{ background: "rgba(255,255,255,0.03)", borderBottom: "1px solid var(--card-border)" }}
              >
                <h2 className="font-bold text-white text-sm tracking-tight">
                  {DIVISION_NAMES[div]} Division
                </h2>
                <span className="text-xs font-medium" style={{ color: "var(--muted)" }}>
                  {CONFERENCE_MAP[div] === "E" ? "Eastern" : "Western"} Conference
                </span>
              </div>
              <table className="w-full text-xs">
                <thead>
                  <tr style={{ borderBottom: "1px solid var(--card-border)", color: "var(--muted)" }}>
                    <th className="text-left px-4 py-2.5">Team</th>
                    <th className="text-center px-2 py-2.5">GP</th>
                    <th className="text-center px-2 py-2.5">W</th>
                    <th className="text-center px-2 py-2.5">L</th>
                    <th className="text-center px-2 py-2.5">OTL</th>
                    <th className="text-center px-2 py-2.5 font-semibold" style={{ color: "var(--accent)" }}>PTS</th>
                    <th className="text-center px-2 py-2.5">DIFF</th>
                    <th className="text-center px-2 py-2.5">STK</th>
                  </tr>
                </thead>
                <tbody>
                  {teams.map((t, i) => {
                    const diff = Number(t.goalFor) - Number(t.goalAgainst)
                    const streak = `${t.streakCode}${t.streakCount}`
                    const status = getPlayoffStatus(i, t, standings)
                    return (
                      <tr
                        key={t.teamAbbrev}
                        style={{ borderBottom: "1px solid rgba(255,255,255,0.04)" }}
                      >
                        <td className="px-4 py-2.5">
                          <div className="flex items-center gap-2">
                            <span className="w-4 text-right tabular-nums" style={{ color: "rgba(255,255,255,0.2)" }}>
                              {i + 1}
                            </span>
                            {status && (
                              <span
                                className="text-xs font-bold px-1 py-0.5 rounded shrink-0"
                                style={{ color: status.color, border: `1px solid ${status.color}`, lineHeight: 1, fontSize: "9px" }}
                              >
                                {status.label}
                              </span>
                            )}
                            <span className="font-semibold text-white">{t.teamAbbrev}</span>
                          </div>
                        </td>
                        <td className="text-center px-2 py-2.5" style={{ color: "var(--muted)" }}>{t.gamesPlayed}</td>
                        <td className="text-center px-2 py-2.5 font-semibold text-white">{t.wins}</td>
                        <td className="text-center px-2 py-2.5" style={{ color: "var(--muted)" }}>{t.losses}</td>
                        <td className="text-center px-2 py-2.5" style={{ color: "var(--muted)" }}>{t.otLosses}</td>
                        <td className="text-center px-2 py-2.5 font-bold" style={{ color: "var(--accent)" }}>
                          {t.points}
                        </td>
                        <td
                          className="text-center px-2 py-2.5 font-mono"
                          style={{ color: diff >= 0 ? "var(--accent)" : "var(--red)" }}
                        >
                          {diff >= 0 ? "+" : ""}{diff}
                        </td>
                        <td className="text-center px-2 py-2.5 font-mono" style={{ color: "var(--muted)" }}>
                          {streak}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )
        })}
      </div>
    </div>
  )
}
