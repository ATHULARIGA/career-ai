from db import backend as db


def init_booking_tables() -> None:
    conn = db.get_conn()
    cur = conn.cursor()
    id_col = db.id_pk_col()
    db.execute(
        cur,
        f"""
        CREATE TABLE IF NOT EXISTS bookings(
            id {id_col},
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
        """,
    )
    conn.commit()
    db.ensure_column(conn, "bookings", "outcome", "TEXT")
    db.ensure_column(conn, "bookings", "context_notes", "TEXT")
    db.ensure_column(conn, "bookings", "brief", "TEXT")
    db.ensure_column(conn, "bookings", "mentor_email", "TEXT")
    conn.close()


def save_booking(name, email, topic, datetime, link, outcome="", context_notes="", brief=""):
    conn = db.get_conn()
    cur = conn.cursor()
    db.execute(
        cur,
        """
        INSERT INTO bookings (name,email,topic,datetime,link,outcome,context_notes,brief)
        VALUES (?,?,?,?,?,?,?,?)
        """,
        (name, email, topic, datetime, link, outcome, context_notes, brief),
    )
    conn.commit()
    conn.close()


def get_bookings():
    conn = db.get_conn()
    cur = conn.cursor()
    db.execute(cur, "SELECT * FROM bookings")
    rows = cur.fetchall()
    conn.close()
    return rows


def get_booking(booking_id):
    conn = db.get_conn()
    cur = conn.cursor()
    db.execute(cur, "SELECT * FROM bookings WHERE id=?", (booking_id,))
    row = cur.fetchone()
    conn.close()
    return row


def assign_mentor_email(booking_id, mentor_email):
    conn = db.get_conn()
    cur = conn.cursor()
    db.execute(
        cur,
        "UPDATE bookings SET mentor_email=? WHERE id=?",
        (mentor_email, booking_id),
    )
    conn.commit()
    conn.close()


init_booking_tables()
