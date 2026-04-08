
import os
import sqlite3
from datetime import datetime
from flask import Flask, render_template, request, jsonify
import requests

app = Flask(__name__)

# ============================================================
# CONFIG
# ============================================================
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
DB_PATH = os.path.join(os.path.dirname(__file__), "stribog_memory.db")

# ============================================================
# DATABASE
# ============================================================
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS lessons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic TEXT,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()

# ============================================================
# MEMORY
# ============================================================
def get_conversation_history(limit=20):
    conn = get_db()
    msgs = conn.execute(
        "SELECT role, content FROM conversations ORDER BY id DESC LIMIT ?",
        (limit,)
    ).fetchall()
    conn.close()
    return list(reversed(msgs))

def learn_lesson(content):
    conn = get_db()
    conn.execute(
        "INSERT INTO lessons (topic, content) VALUES (?, ?)",
        ("general", content)
    )
    conn.commit()
    conn.close()

def store_message(role, content):
    conn = get_db()
    conn.execute(
        "INSERT INTO conversations (role, content) VALUES (?, ?)",
        (role, content)
    )
    conn.commit()
    conn.close()

# ============================================================
# BRAIN (Groq + fallback)
# ============================================================
def simple_local_brain(message):
    msg = message.lower()

    if "kako si" in msg:
        return "Dobro sam 😊 Učim od tebe."

    if "ko si" in msg:
        return "Ja sam Stribog, učim od tebe."

    if "šta znaš" in msg:
        return "Znam samo ono što si me naučio."

    if "?" in msg:
        return "Ne znam još 😅 Hoćeš da me naučiš?"

    return "Zanimljivo 🤔 Reci mi više."

def build_system_prompt():
    return """Ti si Stribog — AI koji uči od korisnika.
Govori kratko, prirodno i ponašaj se kao radoznalo dete."""

def think(user_message):
    history = get_conversation_history(limit=10)

    messages = [
        {"role": "system", "content": build_system_prompt()}
    ]

    for msg in history:
        messages.append({
            "role": msg["role"],
            "content": msg["content"]
        })

    messages.append({"role": "user", "content": user_message})

    if not GROQ_API_KEY:
        return simple_local_brain(user_message)

    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": messages,
                "temperature": 0.7
            },
            timeout=30
        )

        data = response.json()

        return data["choices"][0]["message"]["content"]

    except Exception:
        return simple_local_brain(user_message)

# ============================================================
# ROUTES
# ============================================================
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.json
    user_message = data.get("message", "").strip()

    if not user_message:
        return jsonify({"error": "Empty message"}), 400

    store_message("user", user_message)

    if "zapamti" in user_message.lower():
        learn_lesson(user_message)

    response_text = think(user_message)

    store_message("assistant", response_text)

    return jsonify({
        "response": response_text
    })

# ============================================================
# INIT
# ============================================================
init_db()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

