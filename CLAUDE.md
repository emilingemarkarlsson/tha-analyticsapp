# THA Analytics App – NHL Hockey Analytics SaaS

## Vad detta är
Next.js 15 SaaS-frontend för NHL-analytics. Backend och datapipeline finns i ett separat repo (`tur-mage-ai`) och kör dagligen. Du ska INTE ändra pipelines – bara bygga UI mot MotherDuck.

## Tech stack
- **Next.js 15** (App Router, TypeScript)
- **shadcn/ui + Tailwind CSS** – komponenter och styling
- **Clerk** – autentisering (konfigurera på clerk.com, fyll i .env.local)
- **Recharts** – grafer och visualiseringar
- **LiteLLM proxy** – Text-to-SQL och insiktsgenerering
- **MotherDuck** – molndatabas med 16 säsongers NHL-data

## Vad som redan är byggt
- `lib/motherduck.ts` – server-side query-klient mot MotherDuck REST API
- `lib/litellm.ts` – textToSQL() och summarizeResults() via LiteLLM
- `lib/sql-prompts.ts` – SQL system prompt med fullt databasschema
- `app/api/query/route.ts` – POST /api/query (kör validerad SQL)
- `app/api/ai/route.ts` – POST /api/ai (fråga → SQL → kör → sammanfatta)
- `components/ui/` – shadcn-komponenter (button, card, table, input, badge, tabs, select)
- `.env.local` – MotherDuck och LiteLLM konfigurerade, Clerk saknas

## Vad du ska bygga härnäst (prioriterat)

### Fas 1 – MVP
1. **Layout** (`app/layout.tsx`) – navbar med Clerk auth, mörkt tema (mörkblå/svart, guld-accent)
2. **Startsida** (`app/page.tsx`) – senaste insikter från `agent_insights`, hot streaks
3. **AI Chat** (`app/chat/page.tsx`) – fri textfråga → POST /api/ai → tabell + sammanfattning
4. **Standings** (`app/standings/page.tsx`) – aktuell säsong, grupperat per division
5. **Lag-dashboard** (`app/teams/[abbr]/page.tsx`) – senaste 10 matcher, säsongsstat

### Fas 2
6. **Spelarsida** (`app/players/[id]/page.tsx`) – poängkurva, karriärstatistik
7. **Playoff bracket** (`app/playoffs/[season]/page.tsx`)

### Fas 3
8. **Stripe** – betalning, free/pro tier
9. **Multi-tenancy** via Clerk organizations

## Databas – MotherDuck `nhl`

### Primära tabeller
- `games` – en rad per match (game_id, game_date, season, home/away team, scores)
- `team_game_stats` – en rad per lag per match (team_abbr, goals_for/against, team_points)
- `player_game_stats` – en rad per spelare per match (med player_first_name, player_last_name)
- `game_events` – 6.6M play-by-play-rader
- `standings` – slutlig tabell per säsong
- `playoff_brackets` – slutspelsträd 2010–2026

### Feature store (förberäknat)
- `player_rolling_stats` – rolling averages + z-scores per spelare. Använd WHERE game_recency_rank = 1 för senaste form.
- `goalie_rolling_stats` – save% rolling stats för målvakter
- `team_rolling_stats` – lag-form, wins_last_5, pts_zscore_5v20
- `team_corsi` – shot attempt share per lag per match

### AI-insikter
- `agent_insights` – LLM-genererade insikter som uppdateras dagligen kl 09:00 CET
  - Kolumner: insight_type, entity_name, team_abbr, zscore, severity, headline, body, game_date

### Viktiga regler
- season är BIGINT: 20242025 (ej string)
- game_type = '2' grundserie, '3' slutspel
- teams.abbr är join-nyckeln (INTE teams.id)
- toi_seconds / 60 = minuter
- team_points: 2=vinst, 1=OT-förlust, 0=förlust

## Exempel-queries

Senaste AI-insikter:
SELECT insight_type, entity_name, team_abbr, zscore, headline, body FROM agent_insights ORDER BY generated_at DESC LIMIT 10;

Aktuell tabell:
SELECT teamAbbrev, wins, losses, otLosses, points, gamesPlayed FROM standings WHERE season = 20242025 ORDER BY points DESC;

Spelares senaste form:
SELECT player_first_name, player_last_name, team_abbr, pts_avg_5g, pts_avg_20g, pts_zscore_5v20 FROM player_rolling_stats WHERE game_recency_rank = 1 AND season = (SELECT MAX(season) FROM games WHERE game_type = '2') ORDER BY ABS(pts_zscore_5v20) DESC LIMIT 20;

## Design-riktlinjer
- Mörkt tema: bakgrund #0a0f1e (mörkblå), text vit, accent #c9a84c (guld)
- Hockeyemojis som visuella ledtrådar: 🏒 🥅 🔥 ❄️ 📈
- Mobile-first, responsivt
- Snabb – använd React Server Components för datahämtning där möjligt

## Starta lokalt
npm run dev
Öppna http://localhost:3000

## Deploy
Vercel – koppla repot, lägg in env-variabler i Vercel dashboard.
Clerk kräver eget konto och nycklar (clerk.com, gratis upp till 10 000 MAU).

## Autonomt arbetssatt (agent)

Mål: Agenten ska jobba sjalvstandigt i detta repo och bara stalla fragor nar det ar nodvandigt.

### Arbetsloop (alltid)
1. Forsta passet:
   - Las `CLAUDE.md` och `AGENTS.md`.
   - Kolla `git status`.
   - Bekrafta att .env-variabler finns for den feature som ska testas.
2. Implementera end-to-end:
   - Gor kodandring.
   - Kor snabb verifiering (build/lint/feature-test).
   - Fixa eventuella fel direkt.
3. Rapportera kort:
   - Vad som andrades.
   - Vad som verifierades.
   - Exakt nasta steg.

### Fragor far endast stallas om
- Hemligheter/nycklar saknas och blockerar testning.
- Krav ar motsagelsefulla och leder till olika produktbeteenden.
- Aterkalleliga risker finns (t.ex. datamigration/destruktiva kommandon).
- Externa konton/behorigheter maste godkannas av anvandaren.

### Standardbeslut utan att fraga
- Valj minsta sakra implementation som funkar med befintlig kodstil.
- Prioritera server components for datahamtning dar det passar.
- Behall dark theme + hockeyprofil enligt designriktlinjer.
- Lagg till sma, tydliga felmeddelanden vid API-fel.

### Klara definition (DoD)
- Typning passerar och lint ar clean for andrade filer.
- Berord sida/route fungerar lokalt eller via isolerat API-test.
- Inga hardkodade secrets i kod.
- Andringen ar dokumenterad kort i slutsvaret.
