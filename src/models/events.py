EVENT_STATE_TABLE = """
CREATE TABLE IF NOT EXISTS event_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    last_announced_key TEXT
);
"""
