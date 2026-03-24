import { NextRequest, NextResponse } from "next/server"
import { runQuery, validateSQL } from "@/lib/motherduck"

export async function POST(req: NextRequest) {
  try {
    const { sql } = await req.json()
    if (!sql || typeof sql !== "string") {
      return NextResponse.json({ error: "Missing sql field" }, { status: 400 })
    }

    const validation = validateSQL(sql)
    if (!validation.ok) {
      return NextResponse.json({ error: validation.error }, { status: 400 })
    }

    const result = await runQuery(sql)
    return NextResponse.json(result)
  } catch (err) {
    const message = err instanceof Error ? err.message : "Query failed"
    return NextResponse.json({ error: message }, { status: 500 })
  }
}
