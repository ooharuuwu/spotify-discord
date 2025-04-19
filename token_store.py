import sqlite3
import time 
import os 

DB_PATH = os.getenv("TOKEN_DB_PATH", "tokens.db") #try to understand this later

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS spotify_tokens (
            discord_id TEXT PRIMARY KEY,
            access_token TEXT NOT NULL,
            refresh_token TEXT NOT NULL,
            expires_at INTEGER NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

def save_token(discord_id, token_info):

    expired_at = int(time.time()) + token_info.get("expires_in", 3600)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor() 
    c.execute('''
        INSERT INTO spotify_tokens (discord_id, access_token, refresh_token, expires_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(discord_id) DO UPDATE SET
            access_token=excluded.access_token,
            refresh_token=excluded.refresh_token,
            expires_at=excluded.expires_at
    ''', (
        discord_id, 
        token_info["access_token"],
        token_info["refresh_token"],
        expired_at
    ))
    conn.commit()
    conn.close()

def get_token(discord_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT access_token, refresh_token, expires_at"
        " FROM spotify_tokens WHERE discord_id = ?", (discord_id,)
    )
    row = c.fetchone()
    conn.close()

    if not row: 
        return None
    
    access_token, refresh_token, expires_at = row

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_at": expires_at
    }

init_db()