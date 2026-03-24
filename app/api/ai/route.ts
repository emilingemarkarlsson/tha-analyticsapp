import { NextRequest, NextResponse } from "next/server"
import { fixSQLFromError, summarizeResults, textToSQL } from "@/lib/litellm"
import { runQuery, validateSQL } from "@/lib/motherduck"

export async function POST(req: NextRequest) {
  let sql = ""
  try {
    const { question } = await req.json()
    if (!question || typeof question !== "string") {
      return NextResponse.json({ error: "Missing question field" }, { status: 400 })
    }

    // Step 1: question → SQL
    sql = await textToSQL(question)

    // Step 2: validate SQL
    const validation = validateSQL(sql)
    if (!validation.ok) {
      return NextResponse.json({ error: validation.error, sql }, { status: 400 })
    }

    // Step 3: run query (auto-repair once on SQL runtime error)
    let result
    try {
      result = await runQuery(sql)
    } catch (queryErr) {
      const retrySQL = await fixSQLFromError({
        question,
        previousSQL: sql,
        sqlError: queryErr instanceof Error ? queryErr.message : "Unknown query error",
      })
      const retryValidation = validateSQL(retrySQL)
      if (!retryValidation.ok) {
        throw new Error(`Auto-repair failed validation: ${retryValidation.error}`)
      }
      sql = retrySQL
      result = await runQuery(sql)
    }

    // Step 4: summarize results
    const summary = await summarizeResults(question, result.rows)

    return NextResponse.json({ sql, result, summary })
  } catch (err) {
    const message = err instanceof Error ? err.message : "AI query failed"
    return NextResponse.json({ error: message, sql: sql || null }, { status: 500 })
  }
}
