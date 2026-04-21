"""db/setup.py — DB path, connection, schema, auth helpers."""

import sqlite3, os, hashlib, datetime

DB_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "india_carbon_emissions.db")
)

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def hash_password(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def ensure_schema():
    conn = get_connection()
    conn.execute("""CREATE TABLE IF NOT EXISTS users (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        username        TEXT NOT NULL UNIQUE,
        password_hash   TEXT NOT NULL,
        display_name    TEXT,
        city            TEXT DEFAULT 'Chennai',
        grid_region     TEXT DEFAULT 'Southern Grid',
        daily_target_kg REAL DEFAULT 5.2
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS user_logs (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id       INTEGER NOT NULL DEFAULT 1,
        activity_id   INTEGER NOT NULL,
        activity_name TEXT NOT NULL,
        category      TEXT NOT NULL,
        quantity      REAL NOT NULL,
        unit          TEXT NOT NULL,
        emission_kg   REAL NOT NULL,
        region_name   TEXT,
        is_recurring  INTEGER DEFAULT 0,
        logged_at     TEXT NOT NULL
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS user_goals (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id   INTEGER NOT NULL,
        goal_type TEXT NOT NULL,
        target_kg REAL NOT NULL,
        period    TEXT DEFAULT 'weekly'
    )""")
    conn.commit()
    conn.close()

# alias used by old code
ensure_user_logs_table = ensure_schema

def create_user(username, password, display_name="", city="Chennai", grid_region="Southern Grid"):
    ensure_schema()
    conn = get_connection()
    try:
        cur = conn.execute(
            "INSERT INTO users (username, password_hash, display_name, city, grid_region) VALUES (?,?,?,?,?)",
            (username.lower().strip(), hash_password(password),
             display_name or username, city, grid_region)
        )
        conn.commit()
        return cur.lastrowid
    except sqlite3.IntegrityError:
        return -1
    finally:
        conn.close()

def verify_user(username, password):
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM users WHERE username=? AND password_hash=?",
        (username.lower().strip(), hash_password(password))
    ).fetchone()
    conn.close()
    return dict(row) if row else None

def get_user(user_id):
    conn = get_connection()
    row  = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def update_user_profile(user_id, **kwargs):
    allowed = {"display_name","city","grid_region","daily_target_kg"}
    fields  = {k:v for k,v in kwargs.items() if k in allowed}
    if not fields: return
    sql = "UPDATE users SET " + ", ".join(f"{k}=?" for k in fields) + " WHERE id=?"
    conn = get_connection()
    conn.execute(sql, list(fields.values()) + [user_id])
    conn.commit()
    conn.close()

def now_str():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

if __name__ == "__main__":
    ensure_schema()
    print(f"DB ready: {DB_PATH}")
