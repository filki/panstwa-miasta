import pathlib

import aiosqlite

DB_PATH = pathlib.Path(__file__).parent.parent.parent / "panstwa_miasta.db"


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
