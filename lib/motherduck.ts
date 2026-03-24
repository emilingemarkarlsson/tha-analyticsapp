/**
 * MotherDuck client – server-side only.
 * Uses MotherDuck REST API with Bearer token.
 * Never import this in client components.
 */

import { execFile } from "node:child_process"
import { promisify } from "node:util"

const TOKEN = process.env.MOTHERDUCK_TOKEN
const BASE = process.env.MOTHERDUCK_API_URL ?? "https://api.motherduck.com/sql"
const DRIVER = process.env.MOTHERDUCK_DRIVER ?? "duckdb-cli"
const execFileAsync = promisify(execFile)

export interface QueryResult {
  columns: string[]
  rows: Record<string, unknown>[]
  rowCount: number
}

async function runQueryViaDuckDB(sql: string): Promise<QueryResult> {
  if (!TOKEN) {
    throw new Error("Missing MOTHERDUCK_TOKEN")
  }

  const connection = `md:nhl?motherduck_token=${encodeURIComponent(TOKEN)}&attach_mode=single`
  let stdout = ""
  let stderr = ""
  try {
    const out = await execFileAsync(
      "duckdb",
      [connection, "-json", "-c", sql],
      { timeout: 60000, maxBuffer: 5 * 1024 * 1024 }
    )
    stdout = out.stdout
    stderr = out.stderr
  } catch (err) {
    const e = err as { stderr?: string; message?: string; signal?: string }
    const detail = (e.stderr ?? e.message ?? "Unknown DuckDB error").slice(0, 500)
    throw new Error(`DuckDB query failed: ${detail}`)
  }

  const combined = `${stdout}\n${stderr}`.trim()
  const start = combined.indexOf("[")
  const end = combined.lastIndexOf("]")
  if (start < 0 || end < 0 || end <= start) {
    throw new Error(`DuckDB did not return JSON output. Raw output: ${combined.slice(0, 300)}`)
  }

  const rows = JSON.parse(combined.slice(start, end + 1)) as Record<string, unknown>[]
  const columns = Object.keys(rows[0] ?? {})
  return { columns, rows, rowCount: rows.length }
}

async function runQueryViaRest(sql: string): Promise<QueryResult> {
  if (!TOKEN) {
    throw new Error("Missing MOTHERDUCK_TOKEN")
  }

  const res = await fetch(BASE, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${TOKEN}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ query: sql, database: "nhl" }),
    cache: "no-store",
  })

  if (!res.ok) {
    const err = await res.text()

    if (res.status === 401) {
      throw new Error(
        `MotherDuck auth failed (401) at ${BASE}. Response: ${err}. ` +
          "Verify token type and endpoint, or override MOTHERDUCK_API_URL."
      )
    }

    throw new Error(`MotherDuck ${res.status} at ${BASE}: ${err}`)
  }

  const data = await res.json()
  const columns: string[] = data.columns ?? Object.keys(data.rows?.[0] ?? {})
  const rawRows: unknown[][] = data.rows ?? []

  let rows: Record<string, unknown>[]
  if (rawRows.length > 0 && Array.isArray(rawRows[0])) {
    rows = rawRows.map((r) =>
      Object.fromEntries(columns.map((col, i) => [col, (r as unknown[])[i]]))
    )
  } else {
    rows = rawRows as unknown as Record<string, unknown>[]
  }

  return { columns, rows, rowCount: rows.length }
}

export async function runQuery(sql: string): Promise<QueryResult> {
  if (DRIVER === "rest") {
    return runQueryViaRest(sql)
  }

  try {
    return await runQueryViaDuckDB(sql)
  } catch (duckErr) {
    if (DRIVER === "duckdb-cli") {
      throw duckErr
    }
    return runQueryViaRest(sql)
  }
}

export function getMotherDuckRuntimeConfig() {
  return {
    endpoint: BASE,
    driver: DRIVER,
    hasToken: Boolean(TOKEN),
    tokenPrefix: TOKEN ? TOKEN.slice(0, 12) : "",
  }
}

export async function probeMotherDuck(): Promise<{
  ok: boolean
  status?: number
  error?: string
  endpoint: string
}> {
  if (!TOKEN) {
    return { ok: false, error: "Missing MOTHERDUCK_TOKEN", endpoint: BASE }
  }

  try {
    await runQuery("SELECT 1 AS ok LIMIT 1")
    return { ok: true, status: 200, endpoint: BASE }
  } catch (err) {
    return {
      ok: false,
      error: err instanceof Error ? err.message : "Unknown probe error",
      endpoint: BASE,
    }
  }
}

export function validateSQL(sql: string): { ok: boolean; error?: string } {
  const normalized = sql.trim().toUpperCase()
  if (!normalized.startsWith("SELECT")) {
    return { ok: false, error: "Only SELECT queries are allowed." }
  }
  if (!normalized.includes("LIMIT")) {
    return { ok: false, error: "Query must include a LIMIT clause." }
  }
  return { ok: true }
}
