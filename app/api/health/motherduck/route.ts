import { NextResponse } from "next/server"
import { getMotherDuckRuntimeConfig, probeMotherDuck } from "@/lib/motherduck"

export async function GET() {
  const config = getMotherDuckRuntimeConfig()
  const probe = await probeMotherDuck()

  const status = probe.ok ? 200 : 503
  return NextResponse.json(
    {
      ok: probe.ok,
      service: "motherduck",
      endpoint: config.endpoint,
      driver: config.driver,
      hasToken: config.hasToken,
      tokenPrefix: config.tokenPrefix,
      probeStatus: probe.status ?? null,
      probeError: probe.error ?? null,
      hint: probe.ok
        ? "Connection healthy."
        : "Check token type for SQL API and verify MOTHERDUCK_API_URL.",
    },
    { status }
  )
}
