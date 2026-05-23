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

## 🔁 Obowiązkowy cykl KB

Przed każdą operacją na kodzie:
1. `list_entities()` lub `search_entities(query)` — sprawdź czy są reguły, fixy, gotchas na dany temat
2. Przeczytaj **wszystkie encje typu `rule-*`, `wf-*`, `convention`** — to są wiążące reguły workflow

Po każdej zakończonej operacji (fix, refactor, test, commit, push, PR, merge):
3. `search_entities()` pod kątem nowych faktów do zapisania
4. `create_entity()` lub `add_observations()` — dodaj decyzje, gotchas, konfiguracje, problemy

Bez kroków 1-4 twoja praca jest niekompletna.
