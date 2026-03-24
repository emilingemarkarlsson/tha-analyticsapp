"use client"

import { useState } from "react"
import { Send } from "lucide-react"

const EXAMPLES = [
  "Who has the most points in the last 5 games?",
  "Show me Toronto's last 10 games",
  "Which goalies have the best save% this season?",
  "Top scorers in the 2024–25 season",
  "Which teams have the best home record this season?",
]

interface QueryResult {
  sql: string
  summary: string
  result: { columns: string[]; rows: Record<string, unknown>[]; rowCount: number }
}

export default function ChatPage() {
  const [question, setQuestion] = useState("")
  const [loading, setLoading] = useState(false)
  const [data, setData] = useState<QueryResult | null>(null)
  const [error, setError] = useState("")

  async function ask(q: string) {
    if (!q.trim()) return
    setLoading(true)
    setError("")
    setData(null)
    setQuestion(q)

    try {
      const res = await fetch("/api/ai", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: q }),
      })
      const json = await res.json()
      if (!res.ok) throw new Error(json.error ?? "Request failed")
      setData(json)
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-8 max-w-4xl">
      <div>
        <h1 className="text-2xl font-extrabold tracking-tight text-white">AI Chat</h1>
        <p className="mt-1 text-sm" style={{ color: "var(--muted)" }}>
          Ask anything about NHL data — 16 seasons, 850K+ game records
        </p>
      </div>

      {/* Input */}
      <div
        className="flex gap-0 rounded overflow-hidden"
        style={{ border: "1px solid var(--card-border)" }}
      >
        <input
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && ask(question)}
          placeholder="Ask a question about NHL data..."
          className="flex-1 px-4 py-3 text-sm outline-none"
          style={{
            background: "var(--card)",
            color: "var(--foreground)",
            borderRight: "1px solid var(--card-border)",
          }}
        />
        <button
          onClick={() => ask(question)}
          disabled={loading || !question.trim()}
          className="px-4 py-3 font-semibold text-sm transition-all disabled:opacity-40 flex items-center gap-2"
          style={{ background: "var(--accent)", color: "#fff" }}
        >
          <Send size={14} />
          {loading ? "Thinking..." : "Ask"}
        </button>
      </div>

      {/* Example questions */}
      <div>
        <p className="text-xs mb-2 uppercase tracking-widest font-semibold" style={{ color: "var(--muted)" }}>
          Try these
        </p>
        <div className="flex flex-wrap gap-2">
          {EXAMPLES.map((ex) => (
            <button
              key={ex}
              onClick={() => ask(ex)}
              className="px-3 py-1.5 rounded text-xs font-medium transition-all"
              style={{
                background: "rgba(255,255,255,0.05)",
                color: "var(--muted)",
                border: "1px solid var(--card-border)",
              }}
            >
              {ex}
            </button>
          ))}
        </div>
      </div>

      {/* Error */}
      {error && (
        <div
          className="rounded p-4 text-sm"
          style={{ background: "var(--red-dim)", border: "1px solid var(--red)", color: "var(--red)" }}
        >
          {error}
        </div>
      )}

      {/* Results */}
      {data && (
        <div className="space-y-4">
          {/* Summary */}
          <div className="rounded p-4" style={{ background: "var(--card)", border: "1px solid var(--card-border)" }}>
            <p className="text-sm leading-relaxed text-white">{data.summary}</p>
          </div>

          {/* SQL */}
          <details>
            <summary
              className="cursor-pointer text-xs font-medium select-none"
              style={{ color: "var(--muted)" }}
            >
              Show SQL
            </summary>
            <pre
              className="mt-2 p-4 rounded text-xs overflow-x-auto"
              style={{
                background: "rgba(135,206,235,0.04)",
                color: "var(--sky)",
                border: "1px solid var(--card-border)",
              }}
            >
              {data.sql}
            </pre>
          </details>

          {/* Table */}
          {data.result.rows.length > 0 && (
            <div
              className="rounded overflow-auto"
              style={{ background: "var(--card)", border: "1px solid var(--card-border)" }}
            >
              <table className="w-full text-sm">
                <thead>
                  <tr
                    style={{
                      borderBottom: "1px solid var(--card-border)",
                      background: "rgba(255,255,255,0.03)",
                    }}
                  >
                    {data.result.columns.map((col) => (
                      <th
                        key={col}
                        className="text-left px-4 py-3 text-xs font-semibold uppercase tracking-wide"
                        style={{ color: "var(--muted)" }}
                      >
                        {col}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {data.result.rows.map((row, i) => (
                    <tr
                      key={i}
                      style={{ borderBottom: "1px solid rgba(255,255,255,0.04)" }}
                    >
                      {data.result.columns.map((col) => (
                        <td key={col} className="px-4 py-2.5 text-sm text-white">
                          {String(row[col] ?? "")}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
              <div
                className="px-4 py-2 text-xs"
                style={{ color: "var(--muted)", borderTop: "1px solid var(--card-border)" }}
              >
                {data.result.rowCount} rows returned
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
