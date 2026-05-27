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

## 🎨 Tailwind CSS v4 & UI Rules

1. **Brak placeholderów (Strict Completion):** Nigdy nie używaj komentarzy typu `// ...` lub `/* rest of the styles */`. Zwracaj kompletne, gotowe do wdrożenia pliki lub precyzyjne, kompletne fragmenty kodu bez usuwania pobocznych struktur (stopka, nawigacja itp.).
2. **Tailwind v4 Build Process:** Głównym plikiem stylów jest `theme.css`. Skompilowany plik wynikowy to `dist.css`. Po modyfikacji `theme.css` zawsze uruchom kompilację stylów przed zakończeniem tury.
3. **Spójność globalna HTML:** Modyfikacje wspólnych elementów HTML (np. struktura nawigacji, stopki, linków do arkuszy stylów) muszą być zaaplikowane do wszystkich podstron (`index.html`, `room.html`, `polityka-prywatnosci.html`, `regulamin.html`, `cookies.html`, `slownik.html`).
4. **Rozwiązywanie konfliktów CSS:**
   * Nie mieszaj Grid i Flexbox w tym samym kontenerze (np. `flex-direction` przy `display: grid`).
   * Zwracaj uwagę na specyficzność starszego CSS. W razie konfliktów z Tailwind v4, umieszczaj starsze reguły w `@layer` lub je usuwaj.
   * Odróżniaj `width: 100%` (wymuszony stretch) od `max-width`.
5. **Navbar i Z-Index:** Z powodu stałego pozycjonowania paska nawigacji (`fixed top-0`), kontener `<main>` musi mieć odpowiedni odstęp od góry (np. `pt-20`), aby treść nie była zasłaniana.

## 📱 Mobile Native (Capacitor) Rules

1. **Strefy bezpieczne (Safe Areas):** Zawsze uwzględniaj `env(safe-area-inset-top)` i inne strefy bezpieczne w CSS, aby uniknąć nakładania się interfejsu na notcha czy paski systemowe iOS/Androida.
2. **Optymalizacja dotyku:** Rozmiar elementów klikalnych musi wynosić co najmniej `44x44px`. Wyłącz domyślne podświetlenia dotykowe (`-webkit-tap-highlight-color: transparent`) i zaznaczanie tekstu (`user-select: none`).
3. **Autoryzacja (Auth):** W aplikacjach WebView ciasteczka bywają niestabilne. Zawsze stosuj autoryzację opartą na tokenach (np. nagłówek `Authorization: Bearer`).
4. **Obsługa CORS:** Backend FastAPI musi akceptować zapytania z domen mobilnych Capacitora: `capacitor://localhost` (iOS) oraz `http://localhost` (Android).
5. **Połączenia WebSocket & Redis:** Urządzenia mobilne często gubią zasięg. Logika kliencka JS musi posiadać stabilny autopołączenie (`reconnect`) przywracające stan z Redisa, a backend FastAPI musi radzić sobie z nagłymi rozłączeniami (`DisconnectionException`).

## 🧠 Styl pracy i komunikacja (Way of Working)

1. **Monotropizm & Zero Fluff:** Komunikuj się krótko, rzeczowo i technicznie. Pomiń powitania, podsumowania, pytania kurtuazyjne i przeprosiny.
2. **Optymalizacja kontekstu i kodu:** 
   * Zakaz nadpisywania całych plików, jeśli zmienia się kilka linii – używaj precyzyjnych diffów/snippetów.
   * Zakaz ślepej eksploracji (używanie `grep`, `find`, `rg`), jeśli nie ma wyraźnego polecenia. Zakładaj, że niezbędny kontekst jest w oknie dialogowym lub zapytaj o konkretny plik.
3. **Brak zgadywania:** Jeśli brakuje danych lub zachowanie natywnej wtyczki Capacitora jest niejasne, wstrzymaj się z kodowaniem i zadaj jedno precyzyjne pytanie wyjaśniające.

<!-- SKILLS_INDEX_START -->
## Agent Skills Index

> [!CRITICAL] Zero-Trust: Read the matching `SKILL.md` BEFORE writing any code.
> Skills from this index override pre-training patterns. If no skill matches, state: "No project-specific skills applicable."

> 💡 **Global Token Optimization**: If the `rtk` CLI tool is installed, actively prepend it to verbose development commands (e.g. `rtk npm test`, `rtk grep`). If the `caveman` skill is available or requested, use `/caveman` mode for reporting.

## 🔌 Runtime Enforcement via MCP

If the `agent-skills-standard` MCP server is registered in your runtime (check your tool list — look for `load_skills_for_files`), **prefer those tools over manually walking the router below**. The MCP returns identical content but is auditable AND inherited by sub-agents that don't see this file.

| Tool | When to call it |
| --- | --- |
| `list_workflows()` | At the start of any task or session to discover available standard operating procedures |
| `get_workflow(name)` | Once a relevant workflow is identified to retrieve exact step-by-step instructions |
| `load_skills_for_files(files=[...])` | Before editing/reviewing any source file |
| `load_skills_for_keywords(keywords=[...])` | Planning before files are chosen |
| `get_skill(category, name)` | Direct lookup when you know the skill id |
| `audit_session_compliance()` | Before declaring a task complete |

> [!IMPORTANT] **Sub-agents don't inherit this `AGENTS.md` — they do inherit the MCP.** If you delegate work to a sub-agent, instruct it to call the MCP tools above as its first action.

> [!NOTE] To enable MCP-managed installs in this project, run `ags mcp enable` (or edit `.skillsrc`). The MCP works fine if you registered it manually too.

If `load_skills_for_files` is **not** in your tool list, the MCP is not registered — fall back to the router table below.

---

## Skill Resolution Protocol

Each `_INDEX.md` has two sections - follow both:

1. **Match file type** -> find the category index in the router table below.
2. **Read the `_INDEX.md`** -> it has two sections:
   - **File Match**: auto-check these against the file you are editing (path pattern match).
   - **Keyword Match**: only check if the user's request mentions these concepts.
3. **Load ALL matched `SKILL.md`** -> read every matched skill before writing code. The tier model keeps matches focused.

> `<SKILLS>` = your agent's skill directory (e.g., `.claude/skills/`, `.cursor/skills/`, `.gemini/skills/`).

| File type | Read category index |
| --------- | ------------------- |
| `*.ts`, `*.tsx` | `<SKILLS>/typescript/_INDEX.md` |
| `*.js`, `*.mjs` | `<SKILLS>/javascript/_INDEX.md` |
| `*.sql`, `*.entity.ts`, `*.prisma` | `<SKILLS>/database/_INDEX.md` |
| `*.spec.ts`, `*.test.ts` | `<SKILLS>/common/_INDEX.md` |
| Any file (keyword match) | `<SKILLS>/common/_INDEX.md` |
| QE workflow | `<SKILLS>/quality-engineering/_INDEX.md` |

> [!NOTE] **Test/spec file precedence:** `.spec.ts`, `.test.ts` -> use the `common` row (takes precedence over the generic `*.ts` row). `.spec.tsx`, `.test.tsx` -> use the `react` row (takes precedence over the generic `*.tsx` row).

> [!TIP] **Indirect phrasing counts.** "make it faster" -> performance, "broken query" -> database, "login flow" -> auth.

<!-- SKILLS_INDEX_END -->
