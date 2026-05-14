/**
 * Klient kolejki weryfikacji słów (RAG) — /api/words/report i /api/words/check-reason.
 */
async function pmReportWord({ word, category, starting_letter: startingLetter }) {
    const resp = await fetch("/api/words/report", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            word: String(word || "").trim(),
            category: String(category || "").trim(),
            starting_letter: String(startingLetter || "").trim(),
        }),
    });
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) {
        const detail = data && data.detail ? String(data.detail) : "Nie udało się zgłosić słowa.";
        throw new Error(detail);
    }
    return data;
}

async function pmCheckWordReason({ word, category, starting_letter: startingLetter }) {
    const resp = await fetch("/api/words/check-reason", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            word: String(word || "").trim(),
            category: String(category || "").trim(),
            starting_letter: String(startingLetter || "").trim(),
        }),
    });
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) {
        const detail = data && data.detail ? String(data.detail) : "Nie udało się sprawdzić statusu.";
        throw new Error(detail);
    }
    return data;
}

function pmWordReportStatusMessage(data) {
    if (!data || typeof data !== "object") return "Brak odpowiedzi serwera.";
    if (data.message_pl) return String(data.message_pl);
    return "Zgłoszenie zapisane.";
}

async function pmRequestPostgameWordReport(button) {
    const word = button.getAttribute("data-word") || "";
    const category = button.getAttribute("data-category") || "";
    const letter = button.getAttribute("data-letter") || "";
    const resultBox = button.parentElement?.querySelector(".postgame-word-report-result");
    if (!word || !category || !letter) return;
    button.disabled = true;
    if (resultBox) {
        resultBox.hidden = false;
        resultBox.textContent = "Wysyłanie zgłoszenia…";
    }
    try {
        const data = await pmReportWord({ word, category, starting_letter: letter });
        if (resultBox) resultBox.textContent = pmWordReportStatusMessage(data);
    } catch (err) {
        if (resultBox) resultBox.textContent = err && err.message ? err.message : "Błąd połączenia.";
        console.error("pmRequestPostgameWordReport failed:", err);
    } finally {
        button.disabled = false;
    }
}

function wirePostgameWordReportButtons(root) {
    if (!root) return;
    root.querySelectorAll(".postgame-word-report-btn").forEach((button) => {
        if (button.dataset.wordReportBound === "1") return;
        button.dataset.wordReportBound = "1";
        button.addEventListener("click", () => {
            pmRequestPostgameWordReport(button);
        });
    });
}

globalThis.pmReportWord = pmReportWord;
globalThis.pmCheckWordReason = pmCheckWordReason;
globalThis.wirePostgameWordReportButtons = wirePostgameWordReportButtons;
