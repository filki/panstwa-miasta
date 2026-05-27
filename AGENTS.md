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

