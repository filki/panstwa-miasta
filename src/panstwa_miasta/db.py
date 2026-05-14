import json
import pathlib
import time

import aiosqlite

from .cities_seed import CITIES_SEED
from .countries_seed import COUNTRIES_SEED
from .jobs_seed import JOBS_SEED
from .names_seed import NAMES_SEED

DB_PATH = pathlib.Path(__file__).parent.parent.parent / "panstwa_miasta.db"

# Opóźnienie przed trwałym usunięciem pokoju z SQLite po opuszczeniu przez
# wszystkich (reconnect w krótkim oknie odzyskuje stan z DB).
ROOM_EMPTY_GRACE_SECONDS = 90

# Publiczne lobby przed startem gry (runda 0, brak postępu w gotowości).
LOBBY_IDLE_TIMEOUT_SECONDS = 300

GAME_TRANSCRIPT_TTL_DAYS = 14


async def _ensure_rooms_visibility_column(db) -> None:
    """Migracja: kolumna visibility (publiczny / prywatny lobby)."""
    async with db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='rooms'") as cur:
        if not await cur.fetchone():
            return
    async with db.execute("PRAGMA table_info(rooms)") as cur:
        rows = await cur.fetchall()
    if any(row[1] == "visibility" for row in rows):
        return
    await db.execute("ALTER TABLE rooms ADD COLUMN visibility TEXT NOT NULL DEFAULT 'public'")


def _name_norm(name: str) -> str:
    """Normalisation kept in sync with ``manager.normalize_text``."""
    return name.strip().lower().replace("-", " ").replace("  ", " ")


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS rooms (
                room_id TEXT PRIMARY KEY,
                max_rounds INTEGER,
                time_limit INTEGER,
                current_round INTEGER DEFAULT 0,
                host_name TEXT,
                is_active BOOLEAN DEFAULT 1,
                visibility TEXT NOT NULL DEFAULT 'public'
            )
        """)
        await _ensure_rooms_visibility_column(db)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS players (
                room_id TEXT,
                player_name TEXT,
                score INTEGER DEFAULT 0,
                PRIMARY KEY (room_id, player_name),
                FOREIGN KEY (room_id) REFERENCES rooms (room_id) ON DELETE CASCADE
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS game_transcripts (
                room_id TEXT PRIMARY KEY,
                finished_at INTEGER NOT NULL,
                payload TEXT NOT NULL
            )
        """)
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_game_transcripts_finished ON game_transcripts(finished_at)"
        )
        await db.execute("""
            CREATE TABLE IF NOT EXISTS dictionary_suggestions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                status TEXT NOT NULL DEFAULT 'pending',
                category TEXT NOT NULL,
                proposed_norm TEXT NOT NULL,
                proposed_display TEXT NOT NULL,
                target_seed TEXT NOT NULL,
                room_id TEXT NOT NULL,
                player_name TEXT NOT NULL,
                letter TEXT NOT NULL DEFAULT '',
                round INTEGER NOT NULL DEFAULT 0,
                ai_explanation TEXT NOT NULL DEFAULT '',
                created_at INTEGER NOT NULL,
                reviewed_at INTEGER,
                review_note TEXT
            )
        """)
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_dictionary_suggestions_status ON dictionary_suggestions(status)"
        )
        await db.execute("""
            CREATE TABLE IF NOT EXISTS countries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                name_norm TEXT NOT NULL UNIQUE,
                continent TEXT,
                capital TEXT,
                area_km2 REAL,
                population INTEGER,
                density REAL,
                head_of_state TEXT,
                recognized INTEGER NOT NULL DEFAULT 1
            )
        """)
        await db.execute("CREATE INDEX IF NOT EXISTS idx_countries_norm ON countries(name_norm)")

        # Oddzielny commit schematu przed seedami: przy długim INSERT (np. cities) lub
        # przerwanym starcie jedna transakcja + commit na końcu potrafi zrolować też
        # CREATE TABLE rooms — wtedy WebSocket wpada w „no such table: rooms”.
        await db.commit()

        await db.executemany(
            """
            INSERT OR IGNORE INTO countries
                (name, name_norm, continent, capital, area_km2, population, density,
                 head_of_state, recognized)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    row["name"],
                    _name_norm(row["name"]),
                    row["continent"],
                    row["capital"],
                    row["area_km2"],
                    row["population"],
                    row["density"],
                    row["head_of_state"],
                    1 if row["recognized"] else 0,
                )
                for row in COUNTRIES_SEED
            ],
        )
        await db.execute("""
            CREATE TABLE IF NOT EXISTS cities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nazwa TEXT NOT NULL,
                nazwa_norm TEXT NOT NULL,
                kraj TEXT NOT NULL,
                kraj_norm TEXT NOT NULL,
                UNIQUE(nazwa_norm, kraj_norm)
            )
        """)
        await db.execute("CREATE INDEX IF NOT EXISTS idx_cities_nazwa ON cities(nazwa_norm)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_cities_kraj ON cities(kraj_norm)")
        await db.executemany(
            """
            INSERT OR IGNORE INTO cities (nazwa, nazwa_norm, kraj, kraj_norm)
            VALUES (?, ?, ?, ?)
            """,
            [
                (row["nazwa"], _name_norm(row["nazwa"]), row["kraj"], _name_norm(row["kraj"]))
                for row in CITIES_SEED
            ],
        )
        await db.execute("""
            CREATE TABLE IF NOT EXISTS names (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                imie TEXT NOT NULL,
                imie_norm TEXT NOT NULL,
                plec TEXT NOT NULL CHECK (plec IN ('M','K')),
                liczebnosc INTEGER NOT NULL,
                UNIQUE(imie_norm, plec)
            )
        """)
        await db.execute("CREATE INDEX IF NOT EXISTS idx_names_norm ON names(imie_norm)")
        await db.executemany(
            """
            INSERT OR IGNORE INTO names (imie, imie_norm, plec, liczebnosc)
            VALUES (?, ?, ?, ?)
            """,
            [
                (row["imie"], _name_norm(row["imie"]), row["plec"], row["liczebnosc"])
                for row in NAMES_SEED
            ],
        )
        await db.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kod TEXT,
                opis TEXT NOT NULL,
                opis_norm TEXT NOT NULL,
                UNIQUE(opis_norm)
            )
        """)
        await db.execute("CREATE INDEX IF NOT EXISTS idx_jobs_kod ON jobs(kod)")
        await db.executemany(
            """
            INSERT OR IGNORE INTO jobs (kod, opis, opis_norm)
            VALUES (?, ?, ?)
            """,
            [(row["kod"], row["opis"], _name_norm(row["opis"])) for row in JOBS_SEED],
        )
        await db.commit()


async def deactivate_room(room_id: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE rooms SET is_active = 0 WHERE room_id = ?", (room_id,))
        await db.commit()


async def save_room(
    room_id, max_rounds, time_limit, current_round, host_name, visibility: str = "public"
):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO rooms (room_id, max_rounds, time_limit, current_round, host_name, visibility)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(room_id) DO UPDATE SET
                max_rounds=excluded.max_rounds,
                time_limit=excluded.time_limit,
                current_round=excluded.current_round,
                host_name=excluded.host_name,
                is_active=1,
                visibility=excluded.visibility
        """,
            (room_id, max_rounds, time_limit, current_round, host_name, visibility),
        )
        await db.commit()


async def save_player_score(room_id, player_name, score):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO players (room_id, player_name, score)
            VALUES (?, ?, ?)
            ON CONFLICT(room_id, player_name) DO UPDATE SET score=excluded.score
        """,
            (room_id, player_name, score),
        )
        await db.commit()


async def delete_room(room_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM rooms WHERE room_id = ?", (room_id,))
        await db.commit()


async def fetch_room_snapshot(room_id: str) -> dict[str, object] | None:
    """Zwraca wiersz ``rooms`` + ``players`` jako słownik, albo ``None`` gdy brak pokoju."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM rooms WHERE room_id = ?", (room_id,)) as cur:
            row = await cur.fetchone()
        if row is None:
            return None
        out: dict[str, object] = dict(row)
        async with db.execute(
            "SELECT player_name, score FROM players WHERE room_id = ?",
            (room_id,),
        ) as pcur:
            players = await pcur.fetchall()
        out["players"] = {str(p["player_name"]): int(p["score"]) for p in players}
        return out


async def room_id_exists(room_id: str) -> bool:
    """Czy ``room_id`` jest już zajęty w SQLite (aktywny pokój lub transkrypt)."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT 1 FROM rooms WHERE room_id = ? LIMIT 1",
            (room_id,),
        ) as cur:
            if await cur.fetchone():
                return True
        async with db.execute(
            "SELECT 1 FROM game_transcripts WHERE room_id = ? LIMIT 1",
            (room_id,),
        ) as cur:
            return await cur.fetchone() is not None


async def remove_player(room_id: str, player_name: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM players WHERE room_id = ? AND player_name = ?",
            (room_id, player_name),
        )
        await db.commit()


async def get_active_rooms():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM rooms WHERE is_active = 1") as cursor:
            rooms = await cursor.fetchall()
            result = []
            for r in rooms:
                room_data = dict(r)
                async with db.execute(
                    "SELECT player_name, score FROM players WHERE room_id = ?", (r["room_id"],)
                ) as p_cursor:
                    players = await p_cursor.fetchall()
                    room_data["players"] = {p["player_name"]: p["score"] for p in players}
                result.append(room_data)
            return result


async def load_country_norms() -> set[str]:
    """Return the set of normalised country names for in-memory validation."""
    async with (
        aiosqlite.connect(DB_PATH) as db,
        db.execute("SELECT name_norm FROM countries") as cursor,
    ):
        rows = await cursor.fetchall()
        return {row[0] for row in rows}


async def load_name_norms() -> set[str]:
    """Return the set of normalised first names for in-memory validation."""
    async with (
        aiosqlite.connect(DB_PATH) as db,
        db.execute("SELECT imie_norm FROM names") as cursor,
    ):
        rows = await cursor.fetchall()
        return {row[0] for row in rows}


async def load_job_norms() -> list[str]:
    """Zwraca listę znormalizowanych opisów zawodów (kolejność bez znaczenia)."""
    async with (
        aiosqlite.connect(DB_PATH) as db,
        db.execute("SELECT opis_norm FROM jobs") as cursor,
    ):
        rows = await cursor.fetchall()
        return [row[0] for row in rows]


async def load_city_norms() -> set[str]:
    """Znormalizowane nazwy miast (walidacja kategorii „Miasto”)."""
    async with (
        aiosqlite.connect(DB_PATH) as db,
        db.execute("SELECT nazwa_norm FROM cities") as cursor,
    ):
        rows = await cursor.fetchall()
        return {row[0] for row in rows}


async def purge_stale_game_transcripts(max_age_days: int = GAME_TRANSCRIPT_TTL_DAYS) -> None:
    cutoff = int(time.time()) - max_age_days * 86_400
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM game_transcripts WHERE finished_at < ?", (cutoff,))
        await db.commit()


async def save_game_transcript(room_id: str, payload: dict) -> None:
    await purge_stale_game_transcripts()
    finished_at = int(time.time())
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO game_transcripts (room_id, finished_at, payload)
            VALUES (?, ?, ?)
            ON CONFLICT(room_id) DO UPDATE SET
                finished_at = excluded.finished_at,
                payload = excluded.payload
            """,
            (room_id, finished_at, json.dumps(payload, ensure_ascii=False)),
        )
        await db.commit()


async def fetch_game_transcript(room_id: str) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT payload FROM game_transcripts WHERE room_id = ?",
            (room_id,),
        ) as cursor:
            row = await cursor.fetchone()
            if row is None:
                return None
            return json.loads(row["payload"])


async def insert_dictionary_suggestion(
    *,
    category: str,
    proposed_norm: str,
    proposed_display: str,
    target_seed: str,
    room_id: str,
    player_name: str,
    letter: str,
    round_no: int,
    ai_explanation: str,
) -> int:
    created_at = int(time.time())
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            INSERT INTO dictionary_suggestions (
                status, category, proposed_norm, proposed_display, target_seed,
                room_id, player_name, letter, round, ai_explanation, created_at
            ) VALUES ('pending', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                category,
                proposed_norm,
                proposed_display,
                target_seed,
                room_id,
                player_name,
                letter,
                round_no,
                ai_explanation,
                created_at,
            ),
        )
        await db.commit()
        row_id = cursor.lastrowid
        if row_id is None:
            raise RuntimeError("insert_dictionary_suggestion: missing row id")
        return int(row_id)


async def list_dictionary_suggestions(status: str = "pending") -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """
            SELECT id, status, category, proposed_norm, proposed_display, target_seed,
                   room_id, player_name, letter, round, ai_explanation, created_at,
                   reviewed_at, review_note
            FROM dictionary_suggestions
            WHERE status = ?
            ORDER BY created_at ASC, id ASC
            """,
            (status,),
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def fetch_dictionary_suggestion(suggestion_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """
            SELECT id, status, category, proposed_norm, proposed_display, target_seed,
                   room_id, player_name, letter, round, ai_explanation, created_at,
                   reviewed_at, review_note
            FROM dictionary_suggestions
            WHERE id = ?
            """,
            (suggestion_id,),
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row is not None else None


async def set_dictionary_suggestion_status(
    suggestion_id: int,
    status: str,
    *,
    review_note: str | None = None,
) -> bool:
    reviewed_at = int(time.time())
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            UPDATE dictionary_suggestions
            SET status = ?, reviewed_at = ?, review_note = ?
            WHERE id = ?
            """,
            (status, reviewed_at, review_note, suggestion_id),
        )
        await db.commit()
        return cursor.rowcount > 0
