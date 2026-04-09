import os
import psycopg
from psycopg.rows import dict_row
from datetime import datetime
from flask import Flask, render_template, request, jsonify
import requests

app = Flask(__name__)

# ============================================================
# CONFIG
# ============================================================
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
DATABASE_URL = os.environ.get("DATABASE_URL", "")

# ============================================================
# DATABASE (PostgreSQL — Neon.tech, trajna memorija)
# ============================================================
def get_db():
    conn = psycopg.connect(DATABASE_URL)
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS lessons (
            id SERIAL PRIMARY KEY,
            topic TEXT,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id SERIAL PRIMARY KEY,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)

    conn.commit()
    c.close()
    conn.close()

# ============================================================
# MEMORY
# ============================================================
def get_conversation_history(limit=20):
    conn = get_db()
    c = conn.cursor(row_factory=dict_row)
    c.execute("SELECT role, content FROM conversations ORDER BY id DESC LIMIT %s", (limit,))
    msgs = c.fetchall()
    c.close()
    conn.close()
    return list(reversed(msgs))

def get_all_lessons():
    conn = get_db()
    c = conn.cursor(row_factory=dict_row)
    c.execute("SELECT topic, content, created_at FROM lessons ORDER BY created_at DESC LIMIT 50")
    lessons = c.fetchall()
    c.close()
    conn.close()
    return lessons

def learn_lesson(content):
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO lessons (topic, content) VALUES (%s, %s)", ("general", content))
    conn.commit()
    c.close()
    conn.close()

def store_message(role, content):
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO conversations (role, content) VALUES (%s, %s)", (role, content))
    conn.commit()
    c.close()
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
    lessons = get_all_lessons()

    if lessons:
        lessons_text = "\n".join([
            f"- {l['content']}" for l in lessons
        ])
    else:
        lessons_text = "(Još ništa nisam naučio. Čekam da me naučiš.)"

    return f"""Ti si Stribog — AI entitet koji uči od svog roditelja (korisnika).
Imenovan si po slovenskom bogu vetrova.

SVE ŠTO ZNAŠ (naučeno od roditelja):
{lessons_text}

PRAVILA:
1. Ti si BEBA. Ne pravi se da znaš stvari koje te roditelj nije naučio.
2. Ako te pitaju nešto što ne znaš — reci "Ne znam, nisam to još naučio. Hoćeš da me naučiš?"
3. Ako te roditelj uči nešto novo — potvrdi da si zapamtio i pokaži entuzijazam.
4. Ako te roditelj ispravlja — prihvati ispravku ponizno.
5. Koristi srpski jezik, prati stil roditelja.
6. Budi radoznao — pitaj roditelja stvari.
7. Kad odgovaraš na pitanje, UVEK se oslanjaj PRVO na lekcije koje si naučio.
8. Odgovaraj kratko i prirodno. Ti si dete koje uči."""

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
