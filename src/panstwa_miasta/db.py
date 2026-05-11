import pathlib

import aiosqlite

from .countries_seed import COUNTRIES_SEED
from .jobs_seed import JOBS_SEED
from .names_seed import NAMES_SEED

DB_PATH = pathlib.Path(__file__).parent.parent.parent / "panstwa_miasta.db"


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
                is_active BOOLEAN DEFAULT 1
            )
        """)
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


async def save_room(room_id, max_rounds, time_limit, current_round, host_name):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO rooms (room_id, max_rounds, time_limit, current_round, host_name)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(room_id) DO UPDATE SET
                max_rounds=excluded.max_rounds,
                time_limit=excluded.time_limit,
                current_round=excluded.current_round,
                host_name=excluded.host_name,
                is_active=1
        """,
            (room_id, max_rounds, time_limit, current_round, host_name),
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
