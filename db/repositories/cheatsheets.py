"""Repository for user interview cheat sheet persistence and revision tracking."""

import json
import time
from typing import Any, Optional

import db.backend as db
from core.config import logger

_cheatsheet_table_initialized = False
_global_decks_table_initialized = False
_card_states_table_initialized = False


def ensure_global_cheatsheet_decks_table() -> None:
    """Initializes the global_cheatsheet_decks shared cache table idempotently."""
    global _global_decks_table_initialized
    if _global_decks_table_initialized:
        return
    conn = db.get_conn()
    cur = conn.cursor()
    try:
        db.execute(
            cur,
            """
            CREATE TABLE IF NOT EXISTS global_cheatsheet_decks(
                tech_key TEXT PRIMARY KEY,
                tech_name TEXT NOT NULL,
                blueprint_json TEXT NOT NULL,
                deck_json TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'ai_unreviewed',
                updated_ts INTEGER NOT NULL
            )
            """,
        )
        conn.commit()
        _global_decks_table_initialized = True
    except Exception as exc:
        conn.rollback()
        logger.warning("ensure_global_cheatsheet_decks_table deferred: %s", exc)
    finally:
        conn.close()


def get_global_cheatsheet_deck(tech_key: str) -> Optional[dict[str, Any]]:
    """Fetches a globally cached blueprint and deck for a custom technology."""
    key = (tech_key or "").strip().lower()
    if not key:
        return None
    ensure_global_cheatsheet_decks_table()
    conn = db.get_conn()
    cur = conn.cursor()
    try:
        db.execute(
            cur,
            "SELECT tech_name, blueprint_json, deck_json, status, updated_ts FROM global_cheatsheet_decks WHERE tech_key=?",
            (key,),
        )
        row = cur.fetchone()
    except Exception as exc:
        conn.rollback()
        logger.warning("get_global_cheatsheet_deck failed: %s", exc)
        row = None
    finally:
        conn.close()
    if not row:
        return None
    try:
        return {
            "tech_name": row[0],
            "blueprint": json.loads(row[1] or "{}"),
            "deck": json.loads(row[2] or "{}"),
            "status": row[3] or "ai_unreviewed",
            "updated_ts": row[4],
        }
    except Exception:
        return None


def save_global_cheatsheet_deck(
    tech_key: str,
    tech_name: str,
    blueprint: dict[str, Any],
    deck: dict[str, Any],
    status: str = "ai_unreviewed",
) -> None:
    """Upserts a validated blueprint and deck into the global shared cache."""
    key = (tech_key or "").strip().lower()
    if not key or not deck or not deck.get("cards"):
        return
    ensure_global_cheatsheet_decks_table()
    conn = db.get_conn()
    cur = conn.cursor()
    now = int(time.time())
    bp_json = json.dumps(blueprint or {})
    dk_json = json.dumps(deck or {})
    try:
        db.execute(cur, "SELECT tech_key FROM global_cheatsheet_decks WHERE tech_key=?", (key,))
        row = cur.fetchone()
        if row:
            db.execute(
                cur,
                "UPDATE global_cheatsheet_decks SET tech_name=?, blueprint_json=?, deck_json=?, status=?, updated_ts=? WHERE tech_key=?",
                (tech_name, bp_json, dk_json, status, now, key),
            )
        else:
            db.execute(
                cur,
                "INSERT INTO global_cheatsheet_decks (tech_key, tech_name, blueprint_json, deck_json, status, updated_ts) VALUES (?, ?, ?, ?, ?, ?)",
                (key, tech_name, bp_json, dk_json, status, now),
            )
        conn.commit()
    except Exception as exc:
        conn.rollback()
        logger.warning("save_global_cheatsheet_deck failed: %s", exc)
    finally:
        conn.close()


def ensure_user_card_states_table() -> None:
    """Initializes the user_card_states table for spaced repetition / study ratings."""
    global _card_states_table_initialized
    if _card_states_table_initialized:
        return
    conn = db.get_conn()
    cur = conn.cursor()
    id_col = db.id_pk_col()
    try:
        db.execute(
            cur,
            f"""
            CREATE TABLE IF NOT EXISTS user_card_states(
                id {id_col},
                user_email TEXT NOT NULL,
                tech_name TEXT NOT NULL,
                states_json TEXT NOT NULL DEFAULT '{{}}',
                updated_ts INTEGER NOT NULL
            )
            """,
        )
        conn.commit()
        try:
            db.execute(cur, "CREATE INDEX IF NOT EXISTS idx_user_card_states ON user_card_states(user_email, tech_name)")
            conn.commit()
        except Exception:
            conn.rollback()
        _card_states_table_initialized = True
    except Exception as exc:
        conn.rollback()
        logger.warning("ensure_user_card_states_table deferred: %s", exc)
    finally:
        conn.close()


def get_user_card_states(user_email: str, tech_name: str) -> dict[str, str]:
    """Returns {card_id: rating} for a user and technology."""
    email = (user_email or "").strip().lower()
    t_name = (tech_name or "").strip()
    if not email or not t_name:
        return {}
    ensure_user_card_states_table()
    conn = db.get_conn()
    cur = conn.cursor()
    try:
        db.execute(
            cur,
            "SELECT states_json FROM user_card_states WHERE user_email=? AND LOWER(tech_name)=LOWER(?)",
            (email, t_name),
        )
        row = cur.fetchone()
    except Exception as exc:
        conn.rollback()
        logger.warning("get_user_card_states failed: %s", exc)
        row = None
    finally:
        conn.close()
    if not row:
        return {}
    try:
        parsed = json.loads(row[0] or "{}")
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def save_user_card_states(user_email: str, tech_name: str, states: dict[str, str]) -> None:
    """Upserts {card_id: rating} for a user and technology."""
    email = (user_email or "").strip().lower()
    t_name = (tech_name or "").strip()
    if not email or not t_name:
        return
    ensure_user_card_states_table()
    conn = db.get_conn()
    cur = conn.cursor()
    now = int(time.time())
    states_json = json.dumps(states or {})
    try:
        db.execute(cur, "SELECT id FROM user_card_states WHERE user_email=? AND LOWER(tech_name)=LOWER(?)", (email, t_name))
        row = cur.fetchone()
        if row:
            db.execute(cur, "UPDATE user_card_states SET states_json=?, updated_ts=? WHERE id=?", (states_json, now, row[0]))
        else:
            db.execute(
                cur,
                "INSERT INTO user_card_states (user_email, tech_name, states_json, updated_ts) VALUES (?, ?, ?, ?)",
                (email, t_name, states_json, now),
            )
        conn.commit()
    except Exception as exc:
        conn.rollback()
        logger.warning("save_user_card_states failed: %s", exc)
    finally:
        conn.close()


def ensure_user_cheatsheets_table() -> None:
    """Initializes the user_cheatsheets table and index idempotently."""
    global _cheatsheet_table_initialized
    if _cheatsheet_table_initialized:
        return
    conn = db.get_conn()
    cur = conn.cursor()
    id_col = db.id_pk_col()
    try:
        db.execute(
            cur,
            f"""
            CREATE TABLE IF NOT EXISTS user_cheatsheets(
                id {id_col},
                user_email TEXT NOT NULL,
                tech_name TEXT NOT NULL,
                is_custom INTEGER DEFAULT 0,
                revised_indices_json TEXT DEFAULT '[]',
                cheatsheet_json TEXT NOT NULL,
                created_ts INTEGER NOT NULL,
                updated_ts INTEGER NOT NULL
            )
            """,
        )
        conn.commit()
        try:
            db.execute(cur, "CREATE INDEX IF NOT EXISTS idx_user_cheatsheets ON user_cheatsheets(user_email, tech_name)")
            conn.commit()
        except Exception:
            conn.rollback()
        _cheatsheet_table_initialized = True
    except Exception as exc:
        conn.rollback()
        logger.warning("ensure_user_cheatsheets_table deferred: %s", exc)
    finally:
        conn.close()


def get_user_cheatsheets(user_email: str) -> list[dict[str, Any]]:
    """Returns all saved cheat sheet records for a user email."""
    email = (user_email or "").strip().lower()
    if not email:
        return []
    ensure_user_cheatsheets_table()
    conn = db.get_conn()
    cur = conn.cursor()
    try:
        db.execute(
            cur,
            """
            SELECT tech_name, is_custom, revised_indices_json, cheatsheet_json, updated_ts
            FROM user_cheatsheets
            WHERE user_email=?
            ORDER BY is_custom ASC, updated_ts DESC
            """,
            (email,),
        )
        rows = cur.fetchall()
    except Exception as exc:
        conn.rollback()
        logger.warning("get_user_cheatsheets query fallback: %s", exc)
        rows = []
    finally:
        conn.close()

    results: list[dict[str, Any]] = []
    for row in rows:
        try:
            revised = json.loads(row[2] or "[]")
        except Exception:
            revised = []
        try:
            data = json.loads(row[3] or "{}")
        except Exception:
            data = {}
        results.append({
            "tech_name": row[0],
            "is_custom": bool(row[1]),
            "revised_indices": revised,
            "cheatsheet": data,
            "updated_ts": row[4],
        })
    return results


def save_user_cheatsheet(
    user_email: str,
    tech_name: str,
    cheatsheet_data: dict[str, Any],
    is_custom: bool = False,
    revised_indices: Optional[list[int]] = None,
) -> None:
    """Upserts a generated or customized cheat sheet for a user."""
    email = (user_email or "").strip().lower()
    t_name = (tech_name or "").strip()
    if not email or not t_name:
        return
    ensure_user_cheatsheets_table()
    conn = db.get_conn()
    cur = conn.cursor()
    now = int(time.time())
    revised_json = json.dumps(revised_indices or [])
    data_json = json.dumps(cheatsheet_data or {})
    try:
        db.execute(cur, "SELECT id FROM user_cheatsheets WHERE user_email=? AND LOWER(tech_name)=LOWER(?)", (email, t_name))
        row = cur.fetchone()
        if row:
            db.execute(
                cur,
                """
                UPDATE user_cheatsheets
                SET cheatsheet_json=?, revised_indices_json=?, updated_ts=?
                WHERE id=?
                """,
                (data_json, revised_json, now, row[0]),
            )
        else:
            db.execute(
                cur,
                """
                INSERT INTO user_cheatsheets (user_email, tech_name, is_custom, revised_indices_json, cheatsheet_json, created_ts, updated_ts)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (email, t_name, 1 if is_custom else 0, revised_json, data_json, now, now),
            )
        conn.commit()
    except Exception as exc:
        conn.rollback()
        logger.warning("save_user_cheatsheet failed: %s", exc)
    finally:
        conn.close()


def update_cheatsheet_revised(user_email: str, tech_name: str, revised_indices: list[int]) -> None:
    """Updates the revised card index list for a user's cheat sheet."""
    email = (user_email or "").strip().lower()
    t_name = (tech_name or "").strip()
    if not email or not t_name:
        return
    ensure_user_cheatsheets_table()
    conn = db.get_conn()
    cur = conn.cursor()
    now = int(time.time())
    revised_json = json.dumps(revised_indices or [])
    try:
        db.execute(
            cur,
            """
            UPDATE user_cheatsheets
            SET revised_indices_json=?, updated_ts=?
            WHERE user_email=? AND LOWER(tech_name)=LOWER(?)
            """,
            (revised_json, now, email, t_name),
        )
        conn.commit()
    except Exception as exc:
        conn.rollback()
        logger.warning("update_cheatsheet_revised failed: %s", exc)
    finally:
        conn.close()


def delete_user_cheatsheet(user_email: str, tech_name: str) -> None:
    """Deletes a saved cheat sheet for a user."""
    email = (user_email or "").strip().lower()
    t_name = (tech_name or "").strip()
    if not email or not t_name:
        return
    ensure_user_cheatsheets_table()
    conn = db.get_conn()
    cur = conn.cursor()
    try:
        db.execute(cur, "DELETE FROM user_cheatsheets WHERE user_email=? AND LOWER(tech_name)=LOWER(?)", (email, t_name))
        conn.commit()
    except Exception as exc:
        conn.rollback()
        logger.warning("delete_user_cheatsheet failed: %s", exc)
    finally:
        conn.close()
