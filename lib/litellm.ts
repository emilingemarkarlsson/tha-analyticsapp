import OpenAI from "openai"
import { SQL_SYSTEM_PROMPT } from "./sql-prompts"

export const litellm = new OpenAI({
  baseURL: process.env.LITELLM_BASE_URL + "/v1",
  apiKey: process.env.LITELLM_API_KEY,
})

function cleanSQL(content: string): string {
  const trimmed = content.trim()
  const fenceMatch = trimmed.match(/```(?:sql)?\s*([\s\S]*?)```/i)
  return (fenceMatch ? fenceMatch[1] : trimmed).trim()
}

/** Convert a natural language question to DuckDB SQL. Returns SQL string. */
export async function textToSQL(userQuestion: string): Promise<string> {
  const response = await litellm.chat.completions.create({
    model: "gemini-flash",
    messages: [
      { role: "system", content: SQL_SYSTEM_PROMPT },
      { role: "user", content: userQuestion },
    ],
    max_tokens: 500,
    temperature: 0,
  })
  return cleanSQL(response.choices[0].message.content ?? "")
}

/** Retry helper when first SQL fails at execution time. */
export async function fixSQLFromError(params: {
  question: string
  previousSQL: string
  sqlError: string
}): Promise<string> {
  const { question, previousSQL, sqlError } = params
  const response = await litellm.chat.completions.create({
    model: "gemini-flash",
    messages: [
      { role: "system", content: SQL_SYSTEM_PROMPT },
      {
        role: "user",
        content:
          `Original question:\n${question}\n\n` +
          `Previous SQL (failed):\n${previousSQL}\n\n` +
          `Execution error:\n${sqlError}\n\n` +
          "Return a corrected DuckDB SQL query only. Must be SELECT-only and include LIMIT.",
      },
    ],
    max_tokens: 500,
    temperature: 0,
  })
  return cleanSQL(response.choices[0].message.content ?? "")
}

/** Generate a short narrative summary of query results. */
export async function summarizeResults(
  question: string,
  results: Record<string, unknown>[]
): Promise<string> {
  const response = await litellm.chat.completions.create({
    model: "groq-llama-fast",
    messages: [
      {
        role: "system",
        content:
          "You are an NHL analytics expert. Given a user question and query results, write a concise 2-3 sentence summary in English. Use specific numbers. No fluff.",
      },
      {
        role: "user",
        content: `Question: ${question}\n\nResults (first 10 rows):\n${JSON.stringify(results.slice(0, 10), null, 2)}`,
      },
    ],
    max_tokens: 200,
    temperature: 0.3,
  })
  return response.choices[0].message.content?.trim() ?? ""
}
