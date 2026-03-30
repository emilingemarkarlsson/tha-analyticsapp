# Startprompt for sjalvstandigt arbete

Klistra in detta i en ny Cursor-chat nar du vill att agenten ska driva arbetet:

```text
Jobba sjalvstandigt i detta repo tills uppgiften ar klar end-to-end.
Stall bara fragor om det ar absolut nodvandigt (saknade nycklar, behover behorighet, motsagelsefulla krav, eller risk for destruktiva andringar).

For varje uppgift:
1) analysera kort,
2) implementera direkt,
3) verifiera med lint/build/relevant test,
4) fixa fel,
5) rapportera vad du andrat och vad som ar nasta steg.

Folj projektets regler i CLAUDE.md och AGENTS.md.
Borja med hogsta prioritet i Fas 2 om inget annat anges.
```

## Rekommenderad driftmodell

- Ge en tydlig uppgift i taget (ex: "Bygg /players/[id] med trendgraf och karriar-tabell").
- Lat agenten jobba klart innan ny styrning.
- Be om commit nar du ar nojd ("skapa commit med meddelande ...").
