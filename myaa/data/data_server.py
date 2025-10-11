import os
import sqlite3

from flask import Flask, jsonify, request

# ------------------------------------------------------
# Config & DB helpers
# ------------------------------------------------------
BASE_DIR = os.path.dirname(__file__)
DB_PATH = os.path.join(BASE_DIR, "users.db")


def get_conn():
    """Return a SQLite connection with row factory set for dict rows."""
    conn = sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create tables if they do not exist."""
    with get_conn() as conn:
        c = conn.cursor()
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                discord_name   TEXT UNIQUE,
                call_name      TEXT,
                style          TEXT,
                affinity       INTEGER,
                profile        TEXT
            )
            """
        )
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER,
                eval        TEXT CHECK(eval IN ('Perfect','Good','Bad')),
                summary     TEXT,
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            """
        )
        conn.commit()


# ------------------------------------------------------
# Flask application
# ------------------------------------------------------
app = Flask(__name__)

# Ensure DB exists on first import
os.makedirs(BASE_DIR, exist_ok=True)
init_db()


# Utility functions ----------------------------------------------------------


def _row_to_user_dict(row, conn):
    """Convert a user row to the expected JSON structure (with events)."""
    if row is None:
        return None
    c = conn.cursor()
    c.execute(
        """
        SELECT eval, summary, created_at
        FROM events
        WHERE user_id = ?
        ORDER BY created_at DESC
        LIMIT 3
        """,
        (row["id"],),
    )
    events = [{"eval": e["eval"], "summary": e["summary"]} for e in c.fetchall()]
    return {
        "discord_name": row["discord_name"],
        "call_name": row["call_name"],
        "style": row["style"],
        "affinity": row["affinity"],
        "profile": row["profile"],
        "events": events,
    }


# API routes -----------------------------------------------------------------


@app.route("/users", methods=["GET"])
def get_all_users():
    """Debug: return all users (without events)."""
    with get_conn() as conn:
        c = conn.cursor()
        rows = c.execute("SELECT * FROM users").fetchall()
        users = [_row_to_user_dict(r, conn) for r in rows]
        return jsonify(users)


@app.route("/users/<discord_name>", methods=["GET"])
def get_user(discord_name):
    with get_conn() as conn:
        c = conn.cursor()
        row = c.execute(
            "SELECT * FROM users WHERE discord_name = ?", (discord_name,)
        ).fetchone()
        if row is None:
            return jsonify({"error": "User not found"}), 404
        return jsonify(_row_to_user_dict(row, conn))


@app.route("/users/<discord_name>/update", methods=["POST"])
def update_user(discord_name):
    """Save new event & adjust affinity. Payload JSON:
    {
        "eval": "Perfect" | "Good" | "Bad",
        "summary": "<=30 chars",
        "affinity_delta": int,
        "call_name": optional str,
        "style": optional str,
        "profile": optional str "<=100 chars"
    }
    """
    data = request.get_json(silent=True) or {}
    eval_tag = data.get("eval")
    summary = (data.get("summary") or "")[:30]
    affinity_delta = int(data.get("affinity_delta", 0))  # default affinity: 0

    if eval_tag not in {"Perfect", "Good", "Bad"}:
        return jsonify({"error": "Invalid eval"}), 400

    with get_conn() as conn:
        c = conn.cursor()
        row = c.execute(
            "SELECT * FROM users WHERE discord_name = ?", (discord_name,)
        ).fetchone()

        # Create user on-the-fly if not exists
        if row is None:
            c.execute(
                """
                INSERT INTO users (discord_name, call_name, style, affinity, profile)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    discord_name,
                    data.get("call_name", discord_name),
                    data.get("style", "敬語"),
                    affinity_delta,
                    data.get("profile", ""),
                ),
            )
            user_id = c.lastrowid
        else:
            user_id = row["id"]
            new_affinity = row["affinity"] + affinity_delta
            c.execute(
                """
                UPDATE users
                SET affinity = ?,
                    call_name = ?,
                    style = ?,
                    profile = ?
                WHERE id = ?
                """,
                (
                    new_affinity,
                    data.get("call_name", row["call_name"]),
                    data.get("style", row["style"]),
                    data.get("profile", row["profile"]),
                    user_id,
                ),
            )

        # Insert new event
        c.execute(
            "INSERT INTO events (user_id, eval, summary) VALUES (?, ?, ?)",
            (user_id, eval_tag, summary),
        )
        # Keep only latest 3 events per user
        c.execute(
            """
            DELETE FROM events
            WHERE user_id = ?
              AND id NOT IN (
                SELECT id FROM events WHERE user_id = ? ORDER BY created_at DESC LIMIT 3
              )
            """,
            (user_id, user_id),
        )
        conn.commit()

        # Return updated user
        updated_row = c.execute(
            "SELECT * FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        return jsonify(_row_to_user_dict(updated_row, conn))


@app.route("/users/<discord_name>/events", methods=["DELETE"])
def delete_user_events(discord_name):
    """Delete all events for a given user."""
    with get_conn() as conn:
        c = conn.cursor()
        row = c.execute(
            "SELECT id FROM users WHERE discord_name = ?", (discord_name,)
        ).fetchone()
        if row is None:
            return jsonify({"error": "User not found"}), 404
        c.execute("DELETE FROM events WHERE user_id = ?", (row["id"],))
        conn.commit()
        return jsonify({"message": "Events deleted"})


# ------------------------------------------------------
# CLI helper
# ------------------------------------------------------
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="User Data Server (Flask + SQLite)")
    parser.add_argument("--host", default="0.0.0.0", help="Bind address")
    parser.add_argument("--port", type=int, default=5000, help="Port")
    args = parser.parse_args()

    app.run(host=args.host, port=args.port, debug=True)
