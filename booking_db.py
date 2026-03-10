import sqlite3

conn = sqlite3.connect("bookings.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS bookings(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    email TEXT,
    topic TEXT,
    datetime TEXT,
    link TEXT,
    outcome TEXT,
    context_notes TEXT,
    brief TEXT,
    mentor_email TEXT
)
""")

conn.commit()


def _ensure_column(name, col_type):
    cursor.execute("PRAGMA table_info(bookings)")
    cols = [r[1] for r in cursor.fetchall()]
    if name not in cols:
        cursor.execute(f"ALTER TABLE bookings ADD COLUMN {name} {col_type}")
        conn.commit()


_ensure_column("outcome", "TEXT")
_ensure_column("context_notes", "TEXT")
_ensure_column("brief", "TEXT")
_ensure_column("mentor_email", "TEXT")


def save_booking(name, email, topic, datetime, link, outcome="", context_notes="", brief=""):
    cursor.execute("""
    INSERT INTO bookings (name,email,topic,datetime,link,outcome,context_notes,brief)
    VALUES (?,?,?,?,?,?,?,?)
    """,(name,email,topic,datetime,link,outcome,context_notes,brief))
    conn.commit()


def get_bookings():
    cursor.execute("SELECT * FROM bookings")
    return cursor.fetchall()


def get_booking(booking_id):
    cursor.execute("SELECT * FROM bookings WHERE id=?", (booking_id,))
    return cursor.fetchone()


def assign_mentor_email(booking_id, mentor_email):
    cursor.execute(
        "UPDATE bookings SET mentor_email=? WHERE id=?",
        (mentor_email, booking_id),
    )
    conn.commit()
