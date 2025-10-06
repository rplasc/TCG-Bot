import csv
import asyncio
import aiosqlite

async def insert_from_csv(csv_path):
    async with aiosqlite.connect("data/cards.db") as db:
        with open(csv_path, newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                await db.execute(
                    "INSERT INTO cards (name, rarity, attack, defense, hp, image_url, collection) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (row["name"], row["rarity"].lower(), int(row["attack"]), int(row["defense"]), int(row["hp"]), row["image_url"], row["collection"])
                )
        await db.commit()

asyncio.run(insert_from_csv("cards.csv"))
