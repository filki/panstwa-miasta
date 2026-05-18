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
konwencje, serwery, release'y.

## ⚡ Oszczędzanie tokenów (cache + zero yapping)

### Zmniejszanie cache miss (tokeny wejściowe)

- **Pisz i edytuj od dołu (Bottom-Up)** — cache psuje się od miejsca zmiany
  w dół. Dopisuj nowy kod na samym dole pliku/kontekstu.
- **Agresywnie czyść kontekst** — zamykaj niepotrzebne zakładki. Zed wysyła
  otwarte pliki do modelu.
- **Używaj precyzyjnych odwołań** — podświetlaj konkretny blok kodu zamiast
  pozwalać Zedowi analizować cały workspace.

### Zmniejszanie outputu (tokeny wyjściowe)

- **Zero Yapping** — nie dodawaj zbędnych wyjaśnień, podsumowań, elaboratów.
  Output strictly the modified code only. Do not rewrite entire functions
  when only one line changed.
- **Mikro-iteracje** — najpierw szkielet/interface, potem implementacja
  pojedynczych metod.
- **"Tylko poprawki"** — gdy proszę o refaktor/bug fix, pokaż tylko zmienione
  linie, nie cały plik.

## 📋 Workflow Plan → Build

Gdy używasz profilu **Plan** w Zedzie (lub jawnie poprosisz o plan),
działam w trybie planowania:

1. **Zbieram kontekst** — pytam o cel, ograniczenia, priorytety.
2. **Analizuję** — sprawdzam knowledge base, przeglądam kod, historię.
3. **Proponuję opcje A/B/C** — każda z uzasadnieniem (+/−).
4. **Czekam na decyzję** — dopóki nie powiesz "build", "go", "implementuj"
   lub nie wybierzesz opcji — **nie ruszam kodu**.
5. **Implementuję** wybraną opcję po sygnale od Ciebie.

## Persistent memory (this file + Zed config)

- This `AGENTS.md` is read automatically at the start of every new chat
- More focused rules live in `.zed/settings.json` (MCP servers) — memory
  server persists knowledge graph at `.zed/memory.json`
- Dynamic facts (decisions, gotchas discovered mid-work) are stored in
  a knowledge graph via MCP memory server

## 🚀 Flow zmian

Po każdej implementacji/zakończonym tasku:
1. `git add` zmienionych plików
2. `git commit -m "..."`
3. `git push`
4. Stwórz PR przez `gh` lub narzędzia GitHub
5. `gh pr merge <n> --auto --squash`
Nie zostawiaj wiszących branchy — po mergu usuń lokalny branch.

## 🏷️ Release cadence

- Tag (`v0.x.y`) + GitHub Release po każdym mergu na `main` z nową
  funkcjonalnością lub istotną poprawką.
- Semver: `0.x.y` — `x` dla nowych feat, `y` dla fixów.
- Service worker (`static/sw.js`): podbij `pm-vN` przy zmianach JS/CSS,
  które muszą przebić cache PWA.
- CHANGELOG: wpisz wpis w sekcji [Unreleased] przed tagiem.
