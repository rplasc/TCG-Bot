import asyncio
import aiosqlite

async def insert_from_txt(file_path):
    async with aiosqlite.connect("data/cards.db") as db:
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split(",")
                if len(parts) != 6:
                    continue
                name, rarity, atk, defn, hp, url, collection_id = parts
                cursor = await db.execute("SELECT id FROM collections WHERE name = 'Default'")
                result = await cursor.fetchone()
                default_collection_id = result[0] if result else None
                await db.execute(
                    "INSERT INTO cards (name, rarity, attack, defense, hp, image_url, collection_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (name, rarity, atk, defn, hp, url, collection_id or default_collection_id)
                )
        await db.commit()

asyncio.run(insert_from_txt("cards.txt"))
