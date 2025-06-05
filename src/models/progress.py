COLLECTION_REWARDS_TABLE = """
CREATE TABLE IF NOT EXISTS collection_rewards (
    user_id INTEGER,
    collection_id INTEGER,
    PRIMARY KEY (user_id, collection_id)
);
"""
