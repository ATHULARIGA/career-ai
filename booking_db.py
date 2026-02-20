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
    link TEXT
)
""")

conn.commit()


def save_booking(name, email, topic, datetime, link):
    cursor.execute("""
    INSERT INTO bookings (name,email,topic,datetime,link)
    VALUES (?,?,?,?,?)
    """,(name,email,topic,datetime,link))
    conn.commit()


def get_bookings():
    cursor.execute("SELECT * FROM bookings")
    return cursor.fetchall()
