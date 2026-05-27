import json
import os
import pathlib
import time
from typing import Literal

import aiosqlite

from .cities_seed import CITIES_SEED
from .countries_seed import COUNTRIES_SEED
from .db_backend import connect, connect_dictionary
from .db_redis import (
    redis_configured,
    redis_delete_room,
    redis_fetch_room_snapshot,
    redis_get_active_rooms,
    redis_remove_player,
    redis_room_id_exists,
    redis_save_player_score,
    redis_save_room,
)
from .jobs_seed import JOBS_SEED
from .logger import get_logger
from .names_seed import NAMES_SEED

logger = get_logger(__name__)


def _resolve_db_path() -> pathlib.Path:
    """Prefer repo DB when writable; otherwise use a user-local SQLite file."""
    repo_db = pathlib.Path(__file__).parent.parent.parent / "panstwa_miasta.db"
    if repo_db.exists():
        if os.access(repo_db, os.W_OK):
            return repo_db
    elif os.access(repo_db.parent, os.W_OK):
        return repo_db
    user_db = pathlib.Path.home() / ".local" / "share" / "panstwa-miasta" / "panstwa_miasta.db"
    user_db.parent.mkdir(parents=True, exist_ok=True)
    return user_db


DB_PATH = _resolve_db_path()

# Opóźnienie przed trwałym usunięciem pokoju z SQLite po opuszczeniu przez
# wszystkich (reconnect w krótkim oknie odzyskuje stan z DB).
ROOM_EMPTY_GRACE_SECONDS = 90

# Publiczne lobby przed startem gry (runda 0, brak postępu w gotowości).
LOBBY_IDLE_TIMEOUT_SECONDS = 300

GAME_TRANSCRIPT_TTL_DAYS = 30

DICTIONARY_SUGGESTION_STATUSES = frozenset({"pending", "accepted", "rejected", "error"})


def normalize_dictionary_suggestion_status(status: str) -> str:
    """Mapuje historyczne ``approved`` na ``accepted``."""
    if status == "approved":
        return "accepted"
    return status


async def _migrate_dictionary_suggestion_statuses(db) -> None:
    await db.execute(
        "UPDATE dictionary_suggestions SET status = 'accepted' WHERE status = 'approved'"
    )


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


async def _ensure_rooms_stop_mechanism_column(db) -> None:
    """Migracja: kolumna stop_mechanism (głosowanie Stop)."""
    async with db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='rooms'") as cur:
        if not await cur.fetchone():
            return
    async with db.execute("PRAGMA table_info(rooms)") as cur:
        rows = await cur.fetchall()
    if any(row[1] == "stop_mechanism" for row in rows):
        return
    await db.execute("ALTER TABLE rooms ADD COLUMN stop_mechanism INTEGER NOT NULL DEFAULT 1")


def _name_norm(name: str) -> str:
    """Normalisation kept in sync with ``manager.normalize_text``."""
    return name.strip().lower().replace("-", " ").replace("  ", " ")


async def _table_nonempty(db, table: str) -> bool:
    """True if ``table`` exists and has at least one row (skip redundant seed on restart)."""
    async with db.execute(f"SELECT 1 FROM {table} LIMIT 1") as cur:
        return await cur.fetchone() is not None


_NORM_SEED_BATCH = 500


async def _seed_executemany_if_empty(
    db,
    table: str,
    sql: str,
    rows: list[tuple],
) -> None:
    if await _table_nonempty(db, table):
        logger.info("Skipping %s seed (already populated)", table)
        return
    if rows:
        await _seed_executemany_batched(db, table, sql, rows)


async def _seed_executemany_batched(
    db,
    table: str,
    sql: str,
    rows: list[tuple],
) -> None:
    """Insert in chunks with commit — single executemany of ~20k rows blocks Turso for minutes."""
    total = 0
    for i in range(0, len(rows), _NORM_SEED_BATCH):
        chunk = rows[i : i + _NORM_SEED_BATCH]
        await db.executemany(sql, chunk)
        await db.commit()
        total += len(chunk)
        logger.info("%s seed progress: %d rows", table, total)


async def _seed_norms_from_iter(
    db,
    table: str,
    sql: str,
    norms,
) -> None:
    if await _table_nonempty(db, table):
        logger.info("Skipping %s seed (already populated)", table)
        return
    batch: list[tuple[str]] = []
    total = 0
    for norm in norms:
        batch.append((norm,))
        if len(batch) >= _NORM_SEED_BATCH:
            await db.executemany(sql, batch)
            await db.commit()
            total += len(batch)
            logger.info("%s seed progress: %d rows", table, total)
            batch.clear()
    if batch:
        await db.executemany(sql, batch)
        await db.commit()
        total += len(batch)
        logger.info("%s seed progress: %d rows (done)", table, total)


async def _seed_animal_norms(db) -> None:
    from .seed_data_loader import iter_animal_norms_from_seed_file, seed_data_path

    if await _table_nonempty(db, "animal_norms"):
        logger.info("Skipping animal_norms seed (already populated)")
        return
    if not seed_data_path("animals_norms.jsonl.gz").is_file():
        logger.warning(
            "animal_norms empty — run scripts/export_norms_seed_data.py "
            "or restore scripts/seed_data/animals_norms.jsonl.gz"
        )
        return
    await _seed_norms_from_iter(
        db,
        "animal_norms",
        "INSERT OR IGNORE INTO animal_norms (norm) VALUES (?)",
        iter_animal_norms_from_seed_file(),
    )


async def _seed_plant_norms(db) -> None:
    from .seed_data_loader import iter_plant_norms_from_seed_file, seed_data_path

    if await _table_nonempty(db, "plant_norms"):
        logger.info("Skipping plant_norms seed (already populated)")
        return
    if not seed_data_path("plants_norms.jsonl.gz").is_file():
        logger.warning(
            "plant_norms empty — run scripts/export_norms_seed_data.py "
            "or restore scripts/seed_data/plants_norms.jsonl.gz"
        )
        return
    await _seed_norms_from_iter(
        db,
        "plant_norms",
        "INSERT OR IGNORE INTO plant_norms (norm) VALUES (?)",
        iter_plant_norms_from_seed_file(),
    )


async def init_db():
    async with connect() as db:
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
        await _ensure_rooms_stop_mechanism_column(db)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS custom_category_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                entry TEXT NOT NULL,
                entry_norm TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                room_id TEXT NOT NULL
            )
        """)
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_custom_cat_entries ON custom_category_entries(category, entry_norm)"
        )
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
        await _migrate_dictionary_suggestion_statuses(db)
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

        await _seed_executemany_if_empty(
            db,
            "countries",
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
        await _seed_executemany_if_empty(
            db,
            "cities",
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
        await _seed_executemany_if_empty(
            db,
            "names",
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
        await _seed_executemany_if_empty(
            db,
            "jobs",
            """
                INSERT OR IGNORE INTO jobs (kod, opis, opis_norm)
                VALUES (?, ?, ?)
                """,
            [(row["kod"], row["opis"], _name_norm(row["opis"])) for row in JOBS_SEED],
        )
        await db.execute("""
            CREATE TABLE IF NOT EXISTS things (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rzecz TEXT NOT NULL,
                rzecz_norm TEXT NOT NULL UNIQUE,
                created_at INTEGER NOT NULL
            )
        """)
        await db.execute("CREATE INDEX IF NOT EXISTS idx_things_norm ON things(rzecz_norm)")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS animal_norms (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                norm TEXT NOT NULL UNIQUE
            )
        """)
        await db.execute("CREATE INDEX IF NOT EXISTS idx_animal_norms ON animal_norms(norm)")
        await _seed_animal_norms(db)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS plant_norms (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                norm TEXT NOT NULL UNIQUE
            )
        """)
        await db.execute("CREATE INDEX IF NOT EXISTS idx_plant_norms ON plant_norms(norm)")
        await _seed_plant_norms(db)
        await db.commit()


async def deactivate_room(room_id: str) -> None:
    if redis_configured():
        return
    async with connect() as db:
        await db.execute("UPDATE rooms SET is_active = 0 WHERE room_id = ?", (room_id,))
        await db.commit()


async def save_room(
    room_id,
    max_rounds,
    time_limit,
    current_round,
    host_name,
    visibility: str = "public",
    stop_mechanism: int = 1,
):
    if redis_configured():
        await redis_save_room(
            room_id,
            max_rounds,
            time_limit,
            current_round,
            host_name,
            visibility,
            stop_mechanism=stop_mechanism,
        )
        return
    async with connect() as db:
        await db.execute(
            """
            INSERT INTO rooms (room_id, max_rounds, time_limit, current_round, host_name, visibility, stop_mechanism)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(room_id) DO UPDATE SET
                max_rounds=excluded.max_rounds,
                time_limit=excluded.time_limit,
                current_round=excluded.current_round,
                host_name=excluded.host_name,
                is_active=1,
                visibility=excluded.visibility,
                stop_mechanism=excluded.stop_mechanism
        """,
            (room_id, max_rounds, time_limit, current_round, host_name, visibility, stop_mechanism),
        )
        await db.commit()


async def save_player_score(room_id, player_name, score):
    if redis_configured():
        await redis_save_player_score(room_id, player_name, score)
        return
    async with connect() as db:
        await db.execute(
            """
            INSERT INTO players (room_id, player_name, score)
            VALUES (?, ?, ?)
            ON CONFLICT(room_id, player_name) DO UPDATE SET score=excluded.score
        """,
            (room_id, player_name, score),
        )
        await db.commit()


async def save_custom_category_entry(
    room_id: str, category: str, entry: str, entry_norm: str
) -> None:
    async with connect() as db:
        await db.execute(
            "INSERT OR IGNORE INTO custom_category_entries (category, entry, entry_norm, created_at, room_id) VALUES (?, ?, ?, ?, ?)",
            (category, entry, entry_norm, int(time.time()), room_id),
        )
        await db.commit()


async def delete_room(room_id):
    if redis_configured():
        await redis_delete_room(room_id)
        return
    async with connect() as db:
        await db.execute("DELETE FROM rooms WHERE room_id = ?", (room_id,))
        await db.commit()


async def fetch_room_snapshot(room_id: str) -> dict[str, object] | None:
    """Zwraca wiersz ``rooms`` + ``players`` jako słownik, albo ``None`` gdy brak pokoju."""
    if redis_configured():
        return await redis_fetch_room_snapshot(room_id)
    async with connect() as db:
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
    if redis_configured():
        return await redis_room_id_exists(room_id)
    async with connect() as db:
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
    if redis_configured():
        await redis_remove_player(room_id, player_name)
        return
    async with connect() as db:
        await db.execute(
            "DELETE FROM players WHERE room_id = ? AND player_name = ?",
            (room_id, player_name),
        )
        await db.commit()


async def get_active_rooms():
    if redis_configured():
        return await redis_get_active_rooms()
    async with connect() as db:
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
        connect() as db,
        db.execute("SELECT name_norm FROM countries") as cursor,
    ):
        rows = await cursor.fetchall()
        return {row[0] for row in rows}


async def load_name_norms() -> set[str]:
    """Return the set of normalised first names for in-memory validation."""
    async with (
        connect() as db,
        db.execute("SELECT imie_norm FROM names") as cursor,
    ):
        rows = await cursor.fetchall()
        return {row[0] for row in rows}


async def load_job_norms() -> list[str]:
    """Zwraca listę znormalizowanych opisów zawodów (kolejność bez znaczenia)."""
    async with (
        connect() as db,
        db.execute("SELECT opis_norm FROM jobs") as cursor,
    ):
        rows = await cursor.fetchall()
        return [row[0] for row in rows]


async def load_thing_norms() -> set[str]:
    """Znormalizowane odpowiedzi z kategorii „Rzecz” zaakceptowane w grze."""
    async with (
        connect() as db,
        db.execute("SELECT rzecz_norm FROM things") as cursor,
    ):
        rows = await cursor.fetchall()
        return {row[0] for row in rows}


async def upsert_thing(display: str, norm: str) -> bool:
    """Insert a new accepted thing; returns True when a row was created."""
    async with connect() as db:
        async with db.execute(
            """
            INSERT OR IGNORE INTO things (rzecz, rzecz_norm, created_at)
            VALUES (?, ?, ?)
            """,
            (display, norm, int(time.time())),
        ) as _insert_cur:
            await _insert_cur.close()
        async with db.execute("SELECT changes()") as cur:
            row = await cur.fetchone()
        await db.commit()
        return bool(row and int(row[0]) > 0)


async def load_city_norms() -> set[str]:
    """Znormalizowane nazwy miast (walidacja kategorii „Miasto”)."""
    async with (
        connect() as db,
        db.execute("SELECT nazwa_norm FROM cities") as cursor,
    ):
        rows = await cursor.fetchall()
        return {row[0] for row in rows}


async def load_animal_norms() -> set[str]:
    async with (
        connect() as db,
        db.execute("SELECT norm FROM animal_norms") as cursor,
    ):
        rows = await cursor.fetchall()
        return {row[0] for row in rows}


async def load_plant_norms() -> set[str]:
    async with (
        connect() as db,
        db.execute("SELECT norm FROM plant_norms") as cursor,
    ):
        rows = await cursor.fetchall()
        return {row[0] for row in rows}


async def purge_stale_game_transcripts(max_age_days: int = GAME_TRANSCRIPT_TTL_DAYS) -> None:
    cutoff = int(time.time()) - max_age_days * 86_400
    async with connect() as db:
        await db.execute("DELETE FROM game_transcripts WHERE finished_at < ?", (cutoff,))
        await db.commit()


async def save_game_transcript(room_id: str, payload: dict) -> None:
    await purge_stale_game_transcripts()
    finished_at = int(time.time())
    async with connect() as db:
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
    async with connect() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT payload FROM game_transcripts WHERE room_id = ?",
            (room_id,),
        ) as cursor:
            row = await cursor.fetchone()
            if row is None:
                return None
            return json.loads(row["payload"])


async def fetch_community_stats_30_days() -> dict[str, int]:
    cutoff = int(time.time()) - 30 * 86_400
    unique_players = set()
    total_games = 0

    async with connect() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT payload FROM game_transcripts WHERE finished_at >= ?",
            (cutoff,),
        ) as cursor:
            async for row in cursor:
                try:
                    payload = json.loads(row["payload"])
                    rounds = payload.get("rounds", [])
                    if not rounds:
                        continue
                    total_games += 1
                    # Zbieramy graczy z pierwszej rundy danej gry
                    answers = rounds[0].get("answers", {})
                    if isinstance(answers, dict):
                        unique_players.update(answers.keys())
                except (json.JSONDecodeError, TypeError, KeyError):
                    continue

    return {
        "unique_players": len(unique_players),
        "total_games": total_games,
    }


def _configure_dictionary_rows(db) -> None:
    if hasattr(db, "row_factory"):
        db.row_factory = aiosqlite.Row


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
    async with connect_dictionary() as db:
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
    async with connect_dictionary() as db:
        _configure_dictionary_rows(db)
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


async def list_pending_dictionary_suggestions(
    *,
    limit: int = 20,
    after_id: int = 0,
) -> list[dict]:
    bounded = max(1, min(limit, 100))
    async with connect_dictionary() as db:
        _configure_dictionary_rows(db)
        async with db.execute(
            """
            SELECT id, status, category, proposed_norm, proposed_display, target_seed,
                   room_id, player_name, letter, round, ai_explanation, created_at,
                   reviewed_at, review_note
            FROM dictionary_suggestions
            WHERE status = 'pending' AND id > ?
            ORDER BY id ASC
            LIMIT ?
            """,
            (after_id, bounded),
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def fetch_dictionary_suggestion(suggestion_id: int) -> dict | None:
    async with connect_dictionary() as db:
        _configure_dictionary_rows(db)
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
            if row is None:
                return None
            data = dict(row)
            data["status"] = normalize_dictionary_suggestion_status(str(data["status"]))
            return data


async def fetch_pending_dictionary_suggestion(
    *,
    category: str,
    proposed_norm: str,
    letter: str,
) -> dict | None:
    async with connect_dictionary() as db:
        _configure_dictionary_rows(db)
        async with db.execute(
            """
            SELECT id, status, category, proposed_norm, proposed_display, target_seed,
                   room_id, player_name, letter, round, ai_explanation, created_at,
                   reviewed_at, review_note
            FROM dictionary_suggestions
            WHERE status = 'pending' AND category = ? AND proposed_norm = ? AND letter = ?
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            """,
            (category, proposed_norm, letter),
        ) as cursor:
            row = await cursor.fetchone()
            if row is None:
                return None
            data = dict(row)
            data["status"] = normalize_dictionary_suggestion_status(str(data["status"]))
            return data


async def fetch_latest_dictionary_suggestion(
    *,
    category: str,
    proposed_norm: str,
    letter: str,
) -> dict | None:
    async with connect_dictionary() as db:
        _configure_dictionary_rows(db)
        async with db.execute(
            """
            SELECT id, status, category, proposed_norm, proposed_display, target_seed,
                   room_id, player_name, letter, round, ai_explanation, created_at,
                   reviewed_at, review_note
            FROM dictionary_suggestions
            WHERE category = ? AND proposed_norm = ? AND letter = ?
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            """,
            (category, proposed_norm, letter),
        ) as cursor:
            row = await cursor.fetchone()
            if row is None:
                return None
            data = dict(row)
            data["status"] = normalize_dictionary_suggestion_status(str(data["status"]))
            return data


async def report_dictionary_suggestion(
    *,
    category: str,
    word: str,
    letter: str,
    target_seed: str,
    room_id: str = "",
    player_name: str = "",
) -> tuple[Literal["created", "exists"], int]:
    proposed_norm = _name_norm(word)
    proposed_display = word.strip()
    pending = await fetch_pending_dictionary_suggestion(
        category=category,
        proposed_norm=proposed_norm,
        letter=letter,
    )
    if pending is not None:
        return "exists", int(pending["id"])
    suggestion_id = await insert_dictionary_suggestion(
        category=category,
        proposed_norm=proposed_norm,
        proposed_display=proposed_display,
        target_seed=target_seed,
        room_id=room_id,
        player_name=player_name,
        letter=letter,
        round_no=0,
        ai_explanation="",
    )
    return "created", suggestion_id


async def set_dictionary_suggestion_status(
    suggestion_id: int,
    status: str,
    *,
    review_note: str | None = None,
    ai_explanation: str | None = None,
) -> bool:
    status = normalize_dictionary_suggestion_status(status)
    reviewed_at = int(time.time())
    async with connect_dictionary() as db:
        cursor = await db.execute(
            """
            UPDATE dictionary_suggestions
            SET status = ?, reviewed_at = ?, review_note = ?,
                ai_explanation = COALESCE(?, ai_explanation)
            WHERE id = ?
            """,
            (status, reviewed_at, review_note, ai_explanation, suggestion_id),
        )
        await db.commit()
        return cursor.rowcount > 0


async def decide_pending_dictionary_suggestion(
    suggestion_id: int,
    status: str,
    *,
    review_note: str | None = None,
    ai_explanation: str | None = None,
) -> Literal["updated", "not_pending", "missing"]:
    row = await fetch_dictionary_suggestion(suggestion_id)
    if row is None:
        return "missing"
    if str(row["status"]) != "pending":
        return "not_pending"
    status = normalize_dictionary_suggestion_status(status)
    if status not in DICTIONARY_SUGGESTION_STATUSES or status == "pending":
        raise ValueError(f"invalid decision status: {status}")
    ok = await set_dictionary_suggestion_status(
        suggestion_id,
        status,
        review_note=review_note,
        ai_explanation=ai_explanation,
    )
    return "updated" if ok else "missing"
