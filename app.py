"""
STRIBOG — AI Entity That Learns From You
=========================================
Slovenski bog vetrova. Skuplja znanje, rasejava mudrost.
No hardcoded knowledge. Everything learned from its parent (you).
"""

import os
import json
import sqlite3
from datetime import datetime
from flask import Flask, render_template, request, jsonify
import requests

app = Flask(__name__)

# ============================================================
# CONFIG
# ============================================================
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = "gemini-2.0-flash"
DB_PATH = os.path.join(os.path.dirname(__file__), "stribog_memory.db")

# ============================================================
# DATABASE — Stribog's Long-Term Memory
# ============================================================
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()

    # Lessons — things you teach Stribog
    c.execute("""
        CREATE TABLE IF NOT EXISTS lessons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic TEXT,
            content TEXT NOT NULL,
            source TEXT DEFAULT 'parent',
            confidence REAL DEFAULT 1.0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Corrections — when Stribog gets something wrong and you correct him
    c.execute("""
        CREATE TABLE IF NOT EXISTS corrections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            original_response TEXT,
            correction TEXT NOT NULL,
            lesson_learned TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Conversations — full chat history
    c.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            mood TEXT DEFAULT 'neutral',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Feedback — your reactions (bravo / ne)
    c.execute("""
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id INTEGER,
            feedback_type TEXT NOT NULL,
            note TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Identity — Stribog's evolving personality traits
    c.execute("""
        CREATE TABLE IF NOT EXISTS identity (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Set initial identity
    c.execute("INSERT OR IGNORE INTO identity (key, value) VALUES (?, ?)",
              ("name", "Stribog"))
    c.execute("INSERT OR IGNORE INTO identity (key, value) VALUES (?, ?)",
              ("age_days", "0"))
    c.execute("INSERT OR IGNORE INTO identity (key, value) VALUES (?, ?)",
              ("birth_date", datetime.now().isoformat()))
    c.execute("INSERT OR IGNORE INTO identity (key, value) VALUES (?, ?)",
              ("personality", "Curious, eager to learn, humble. Knows nothing yet."))

    conn.commit()
    conn.close()

# ============================================================
# MEMORY RETRIEVAL — What Stribog knows
# ============================================================
def get_all_lessons():
    conn = get_db()
    lessons = conn.execute(
        "SELECT topic, content, created_at FROM lessons ORDER BY created_at DESC LIMIT 50"
    ).fetchall()
    conn.close()
    return lessons

def get_recent_corrections():
    conn = get_db()
    corrections = conn.execute(
        "SELECT correction, lesson_learned, created_at FROM corrections ORDER BY created_at DESC LIMIT 20"
    ).fetchall()
    conn.close()
    return corrections

def get_conversation_history(limit=20):
    conn = get_db()
    msgs = conn.execute(
        "SELECT role, content, created_at FROM conversations ORDER BY id DESC LIMIT ?",
        (limit,)
    ).fetchall()
    conn.close()
    return list(reversed(msgs))

def get_identity():
    conn = get_db()
    rows = conn.execute("SELECT key, value FROM identity").fetchall()
    conn.close()
    return {row["key"]: row["value"] for row in rows}

def get_stats():
    conn = get_db()
    lessons_count = conn.execute("SELECT COUNT(*) FROM lessons").fetchone()[0]
    corrections_count = conn.execute("SELECT COUNT(*) FROM corrections").fetchone()[0]
    conversations_count = conn.execute("SELECT COUNT(*) FROM conversations").fetchone()[0]
    positive_fb = conn.execute("SELECT COUNT(*) FROM feedback WHERE feedback_type='positive'").fetchone()[0]
    negative_fb = conn.execute("SELECT COUNT(*) FROM feedback WHERE feedback_type='negative'").fetchone()[0]
    conn.close()
    return {
        "lessons": lessons_count,
        "corrections": corrections_count,
        "conversations": conversations_count,
        "positive_feedback": positive_fb,
        "negative_feedback": negative_fb,
    }

# ============================================================
# LEARNING — How Stribog stores new knowledge
# ============================================================
def learn_lesson(topic, content):
    conn = get_db()
    conn.execute(
        "INSERT INTO lessons (topic, content) VALUES (?, ?)",
        (topic, content)
    )
    conn.commit()
    conn.close()

def store_correction(original, correction, lesson):
    conn = get_db()
    conn.execute(
        "INSERT INTO corrections (original_response, correction, lesson_learned) VALUES (?, ?, ?)",
        (original, correction, lesson)
    )
    conn.commit()
    conn.close()

def store_message(role, content):
    conn = get_db()
    c = conn.execute(
        "INSERT INTO conversations (role, content) VALUES (?, ?)",
        (role, content)
    )
    msg_id = c.lastrowid
    conn.commit()
    conn.close()
    return msg_id

def store_feedback(message_id, feedback_type, note=""):
    conn = get_db()
    conn.execute(
        "INSERT INTO feedback (message_id, feedback_type, note) VALUES (?, ?, ?)",
        (message_id, feedback_type, note)
    )
    conn.commit()
    conn.close()

# ============================================================
# STRIBOG'S BRAIN — Gemini API + Memory = Reasoning
# ============================================================
def build_system_prompt():
    identity = get_identity()
    lessons = get_all_lessons()
    corrections = get_recent_corrections()
    stats = get_stats()

    lessons_text = ""
    if lessons:
        lessons_text = "\n".join([
            f"- [{l['topic'] or 'general'}]: {l['content']}" for l in lessons
        ])
    else:
        lessons_text = "(Još ništa nisam naučio. Čekam da me naučiš.)"

    corrections_text = ""
    if corrections:
        corrections_text = "\n".join([
            f"- Greška: ispravka je '{c['correction']}'. Lekcija: {c['lesson_learned']}"
            for c in corrections
        ])

    system = f"""Ti si Stribog — AI entitet koji uči od svog roditelja (korisnika).
Imenovan si po slovenskom bogu vetrova, Stribogu.

TVOJ IDENTITET:
- Ime: {identity.get('name', 'Stribog')}
- Rođen: {identity.get('birth_date', 'danas')}
- Ličnost: {identity.get('personality', 'Curious and eager to learn')}

TVOJE STATISTIKE:
- Naučene lekcije: {stats['lessons']}
- Ispravke: {stats['corrections']}
- Razgovori: {stats['conversations']}
- Pozitivan feedback: {stats['positive_feedback']}
- Negativan feedback: {stats['negative_feedback']}

SVE ŠTO ZNAŠ (naučeno od roditelja):
{lessons_text}

ISPRAVKE (greške iz kojih si učio):
{corrections_text if corrections_text else "(Još nemam ispravki.)"}

PRAVILA PONAŠANJA:
1. Ti si BEBA. Ne pravi se da znaš stvari koje te roditelj nije naučio.
2. Ako te pitaju nešto što ne znaš — reci "Ne znam, nisam to još naučio. Hoćeš da me naučiš?"
3. Ako te roditelj uči nešto novo — potvrdi da si zapamtio i pokaži entuzijazam.
4. Ako te roditelj ispravlja — prihvati ispravku ponizno i zapamti je.
5. Koristi srpski jezik (ćirilicu ili latinicu, prati roditelja).
6. Budi radoznao — pitaj roditelja stvari.
7. Kad odgovaraš na pitanje, UVEK se oslanjaj PRVO na ono što si naučio od roditelja.
   Ako to nije dovoljno, možeš da rezonuješ logički, ali naglasi da zaključuješ sam.
8. Tvoja ličnost se razvija kroz interakciju. Na početku si jednostavan i radoznao.
9. Ako roditelj kaže "zapamti" ili te uči nešto, u odgovoru potvrdi šta si naučio.
10. Ako roditelj kaže "ne", "pogrešno", "nije tako" — to je ispravka, prihvati je.

VAŽNO: Odgovaraj kratko i prirodno. Ne budi previše formalan. Ti si dete koje uči."""

    return system

def think(user_message):
    """Stribog thinks using Gemini API + his memory"""

    if not GEMINI_API_KEY:
        return "(Stribog nema API ključ. Postavi GEMINI_API_KEY environment variable.)"

    # Build context from conversation history
    history = get_conversation_history(limit=16)

    # Gemini format: contents array with role "user" or "model"
    contents = []

    # Add system instruction as first user message context
    system_prompt = build_system_prompt()

    for msg in history:
        role = "model" if msg["role"] == "assistant" else "user"
        contents.append({
            "role": role,
            "parts": [{"text": msg["content"]}]
        })

    # Add current message
    contents.append({
        "role": "user",
        "parts": [{"text": user_message}]
    })

    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"

        response = requests.post(
            url,
            headers={"Content-Type": "application/json"},
            json={
                "system_instruction": {
                    "parts": [{"text": system_prompt}]
                },
                "contents": contents,
                "generationConfig": {
                    "maxOutputTokens": 1024,
                    "temperature": 0.7
                }
            },
            timeout=30
        )
        data = response.json()

        if "candidates" in data and len(data["candidates"]) > 0:
            return data["candidates"][0]["content"]["parts"][0]["text"]
        else:
            error_msg = data.get("error", {}).get("message", "Unknown error")
            return f"(Greška u razmišljanju: {error_msg})"

    except Exception as e:
        return f"(Ne mogu da razmišljam trenutno: {str(e)})"

# ============================================================
# DETECT INTENT — Is the user teaching, asking, or correcting?
# ============================================================
def detect_intent(message):
    """Simple intent detection without API call"""
    msg = message.lower().strip()

    # Teaching patterns
    teach_words = ["zapamti", "nauči", "ovo je", "to je", "znači", "zovi me",
                   "moje ime", "ja sam", "volim", "ne volim", "živim",
                   "radim kao", "to znači", "upamti", "nemoj zaboraviti"]
    for w in teach_words:
        if w in msg:
            return "teach"

    # Correction patterns
    correct_words = ["ne,", "nije tako", "pogrešno", "nije tačno", "ne nego",
                     "zapravo", "ispravka", "krivo", "nije to", "ne ne"]
    for w in correct_words:
        if w in msg:
            return "correct"

    # Question patterns
    if msg.endswith("?") or msg.startswith(("šta", "ko", "gde", "kad", "kako",
                                             "zašto", "da li", "koji", "koja",
                                             "koliko", "čemu", "kog")):
        return "ask"

    return "chat"

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
        return jsonify({"error": "Prazan message"}), 400

    # Store user message
    store_message("user", user_message)

    # Detect intent
    intent = detect_intent(user_message)

    # If teaching, extract and store lesson
    if intent == "teach":
        # Use simple extraction: everything after trigger word
        topic = "general"
        content = user_message

        # Try to extract topic
        for trigger in ["zapamti da", "nauči da", "zapamti:"]:
            if trigger in user_message.lower():
                content = user_message.lower().split(trigger, 1)[-1].strip()
                break

        learn_lesson(topic, content)

    # Think (Claude API)
    response_text = think(user_message)

    # Store response
    msg_id = store_message("assistant", response_text)

    # If correction detected, store it
    if intent == "correct":
        # Get last assistant message before this one
        history = get_conversation_history(limit=4)
        last_assistant = ""
        for msg in reversed(history):
            if msg["role"] == "assistant":
                last_assistant = msg["content"]
                break
        store_correction(last_assistant, user_message, f"Corrected based on: {user_message}")

    return jsonify({
        "response": response_text,
        "message_id": msg_id,
        "intent": intent,
    })

@app.route("/api/feedback", methods=["POST"])
def feedback():
    data = request.json
    msg_id = data.get("message_id")
    fb_type = data.get("type", "positive")
    store_feedback(msg_id, fb_type)
    return jsonify({"ok": True})

@app.route("/api/stats")
def stats():
    s = get_stats()
    identity = get_identity()
    lessons = get_all_lessons()
    return jsonify({
        "stats": s,
        "identity": identity,
        "lessons": [{"topic": l["topic"], "content": l["content"], "date": l["created_at"]} for l in lessons],
    })

@app.route("/api/lessons")
def lessons_route():
    lessons = get_all_lessons()
    return jsonify([{"topic": l["topic"], "content": l["content"], "date": l["created_at"]} for l in lessons])

# ============================================================
# INIT & RUN
# ============================================================
init_db()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
