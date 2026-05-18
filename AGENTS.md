# Państwa-Miasta — Agent Onboarding

Real-time multiplayer Państwa-Miasta po polsku, FastAPI + WebSocket + vanilla JS.
Solo project, prod target: smartphone-first.

## ⚠️ Agent — najpierw sprawdź knowledge base

Zanim zaczniesz cokolwiek robić (pisać kod, proponować zmiany, diagnozować),
**najpierw zajrzyj do knowledge base** (`knowledge_base/`):

1. Użyj `mcp-bridge.py` lub bezpośredniego MCP, żeby sprawdzić czy są już fakty
   na dany temat (decyzje architektoniczne, konwencje, stack, gotchas).
2. Jeśli znajdziesz — użyj ich.
3. **Po każdym tasku/prompcie** przejrzyj co nowego się pojawiło i dodaj
   trwałe fakty do KB (decyzje, konwencje, problemy, gotchas, konfiguracje).
4. Nie przechowuj sekretów, tokenów, haseł.

Knowledge base to Kùzu grafowa baza, dostępna przez MCP (`knowledge-base`)
lub przez `tools/mcp-bridge.py`. Zawiera: projekty, stack, ADR, workflow,
konwencje, serwery, release'y, konfiguracje.
