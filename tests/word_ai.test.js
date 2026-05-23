/**
 * @jest-environment jsdom
 */

global.fetch = jest.fn();

require("../static/js/word-ai.js");

const { pmReportWord, pmCheckWordReason } = globalThis;

describe("word-ai", () => {
    beforeEach(() => {
        fetch.mockReset();
    });

    test("pmReportWord posts payload", async () => {
        fetch.mockResolvedValue({
            ok: true,
            json: async () => ({ outcome: "created", suggestion_id: 1, message_pl: "ok" }),
        });
        const data = await pmReportWord({ word: "Wakanda", category: "Państwo", starting_letter: "w" });
        expect(data.outcome).toBe("created");
        expect(fetch).toHaveBeenCalledWith(
            "/api/dictionary/suggestions",
            expect.objectContaining({
                method: "POST",
                body: JSON.stringify({
                    word: "Wakanda",
                    category: "Państwo",
                    starting_letter: "w",
                }),
            }),
        );
    });

    test("pmReportWord surfaces 503 detail", async () => {
        fetch.mockResolvedValue({
            ok: false,
            json: async () => ({ detail: "wyłączona" }),
        });
        await expect(
            pmReportWord({ word: "Wakanda", category: "Państwo", starting_letter: "w" }),
        ).rejects.toThrow("wyłączona");
    });

    test("pmReportWord uses optional detail from JSON body", async () => {
        fetch.mockResolvedValue({
            ok: false,
            json: async () => ({ detail: "za długie" }),
        });
        await expect(
            pmReportWord({ word: "x", category: "Państwo", starting_letter: "x" }),
        ).rejects.toThrow("za długie");
    });

    test("pmCheckWordReason returns status", async () => {
        fetch.mockResolvedValue({
            ok: true,
            json: async () => ({ status: "pending", message_pl: "W kolejce" }),
        });
        const data = await pmCheckWordReason({ word: "Wakanda", category: "Państwo", starting_letter: "w" });
        expect(data.status).toBe("pending");
    });
});
