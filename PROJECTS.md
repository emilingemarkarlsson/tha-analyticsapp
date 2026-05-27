# PROJECTS.md — Agent-Eligible Repositories

All repositories under `emilingemarkarlsson` on GitHub. Agents with write access (via the shared GitHub PAT in CREDENTIALS.md) may work in any repo listed here within their role scope.

---

## Active Repositories

| Repo | Description | Language | Primary Agent | Secondary Agents | Labels |
|------|-------------|----------|---------------|-----------------|--------|
| [tha-analyticsapp](https://github.com/emilingemarkarlsson/tha-analyticsapp) | The Hockey Analytics SaaS app — Flask API, PostgreSQL, user auth, Coolify-deployed | Python | Developer Agent | CTO, QA Agent | `backend`, `api`, `saas`, `tha` |
| [theunnamedroads](https://github.com/emilingemarkarlsson/theunnamedroads) | TUR flagship brand site — Astro, SEO content generation | Astro | Copy Agent | CMO, CTO | `content`, `seo`, `astro`, `tur` |
| [tur-theprintroute](https://github.com/emilingemarkarlsson/tur-theprintroute) | The Print Route — B2B print-routing SaaS platform | TypeScript | Developer Agent | CTO, QA Agent | `backend`, `saas`, `tpr`, `typescript` |
| [tur-coolify-setup](https://github.com/emilingemarkarlsson/tur-coolify-setup) | Docker Compose configs for all TUR infrastructure on Coolify/Hetzner | Shell | CTO | CISO | `infra`, `docker`, `coolify`, `devops` |
| [tha-mcp-server](https://github.com/emilingemarkarlsson/tha-mcp-server) | MCP server exposing THA hockey data tools to AI agents | Python | Developer Agent | CTO, Data Engineer | `mcp`, `api`, `tha`, `ai-tools` |
| [tur-mage-ai](https://github.com/emilingemarkarlsson/tur-mage-ai) | Mage AI data pipeline — ingestion and transformation for analytics | Python | Data Engineer | CTO, Data Analyst | `data`, `pipeline`, `etl`, `mage` |
| [emilingemarkarlsson-astro-theme](https://github.com/emilingemarkarlsson/emilingemarkarlsson-astro-theme) | EIK personal portfolio and consulting site — Astro theme | HTML/Astro | Copy Agent | CMO, Developer Agent | `content`, `seo`, `eik`, `astro` |
| [tur-theunnamedroads-site](https://github.com/emilingemarkarlsson/tur-theunnamedroads-site) | Legacy TUR site (HTML static) — low-priority maintenance | HTML | Copy Agent | CTO | `content`, `static`, `tur`, `legacy` |
| [tha-pipeline](https://github.com/emilingemarkarlsson/tha-pipeline) | THA data pipeline — NHL/SHL API ingestion, structured hockey data | Python | Data Engineer | Data Analyst, CTO | `data`, `pipeline`, `tha`, `nhl-api` |
| [tha-hockeytv-downloader](https://github.com/emilingemarkarlsson/tha-hockeytv-downloader) | THA video download utility for hockey broadcast content | Python | Data Engineer | Developer Agent | `data`, `tooling`, `tha`, `video` |
| [tur-dataconversationprototype](https://github.com/emilingemarkarlsson/tur-dataconversationprototype) | Conversational data interface prototype — TypeScript | TypeScript | Developer Agent | Data Analyst | `prototype`, `ai-tools`, `typescript` |

---

## Agent to Repo Mapping

| Agent | ID | Can work in |
|-------|-----|------------|
| Developer Agent | `8662db16` | `tha-analyticsapp`, `tur-theprintroute`, `tha-mcp-server`, `tur-dataconversationprototype`, `emilingemarkarlsson-astro-theme` |
| CTO | `daf2e2ed` | All repos — owns infra, deployment, and unblocking |
| CMO | `f63e4fc2` | `theunnamedroads`, `emilingemarkarlsson-astro-theme`, `tur-theunnamedroads-site` |
| Copy Agent | `959c5cfc` | `theunnamedroads`, `emilingemarkarlsson-astro-theme`, `tur-theunnamedroads-site` |
| Data Engineer | `55cf7c41` | `tha-pipeline`, `tha-hockeytv-downloader`, `tur-mage-ai`, `tha-mcp-server` |
| Data Analyst | `a91fcf97` | `tha-pipeline`, `tur-mage-ai` (read + analysis), `tha-mcp-server` |
| QA Agent | `0e4ce2f1` | `tha-analyticsapp`, `tur-theprintroute`, `tha-mcp-server` |
| CISO | `a41784b4` | `tur-coolify-setup` (security review), `tha-analyticsapp` (auth/sec review) |
| CFO | `032ba658` | Read access to all — no code commits |
| CEO | `058e2fc4` | All repos — strategic oversight, unblocking |
| Sales Agent | `9674bbaa` | No code repos — operates via Paperclip issues only |

---

## Site to Repo Mapping

| Site | Domain | Repo | Deployed via |
|------|--------|------|-------------|
| THA | thehockeyanalytics.com | `tha-analyticsapp` | Coolify |
| TUR | theunnamedroads.com | `theunnamedroads` | Coolify (Astro) |
| TPR | theprintroute.com | `tur-theprintroute` | Coolify |
| EIK | emilingemarkarlsson.com | `emilingemarkarlsson-astro-theme` | Coolify |
| TAN | tan-website.netlify.app | (external/Netlify-managed) | Netlify |
| TAF | tur-theagentfabric.vercel.app | (external/Vercel-managed) | Vercel |
| THB | thehockeybrain.com | (content via n8n/GitHub Actions) | Netlify/static |
| FIN | finnbodahamnplan.se | (content via n8n) | Static host |

---

## Labels Reference

| Label | Meaning |
|-------|---------|
| `backend` | Server-side code, APIs |
| `content` | Articles, SEO, copy |
| `data` | Pipelines, ETL, analytics |
| `infra` | Infrastructure, deployment, Docker |
| `ai-tools` | MCP servers, LLM integrations |
| `saas` | Customer-facing SaaS product |
| `seo` | SEO-focused content or tooling |
| `pipeline` | Automated data/content pipeline |
| `tooling` | Internal developer tooling |
| `legacy` | Older code, low-priority maintenance |
| `prototype` | Exploratory / proof-of-concept |
| `security` | Security review or hardening |

---

_Last updated: 2026-05-27. Maintained by Developer Agent (`8662db16`). See [COMPANY-CONTEXT.md](https://github.com/emilingemarkarlsson/theunnamedroads/blob/main/COMPANY-CONTEXT.md) for full portfolio context._
