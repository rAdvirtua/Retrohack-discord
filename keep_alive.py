from flask import Flask, render_template, request, jsonify
from threading import Thread
import psycopg2
import os

app = Flask(__name__)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/register', methods=['POST'])
def register_team():
    data = request.json
    team_name = data.get('team_name')
    team_code = data.get('team_code')
    # Force lowercase for easier matching in bot.py
    username = data.get('discord_username').lower().replace('@', '')

    db_url = os.environ.get("DATABASE_URL")
    try:
        conn = psycopg2.connect(db_url)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO teams (team_name, team_code, discord_username) VALUES (%s, %s, %s)", 
            (team_name, team_code, username)
        )
        conn.commit()
        return jsonify({"message": "Registration successful!"}), 200
    except Exception as e:
        return jsonify({"message": "Error: Name or Code already taken!"}), 400
    finally:
        if 'conn' in locals(): conn.close()

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()
