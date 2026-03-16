from flask import Flask, render_template, request, jsonify
import psycopg2
import os
from threading import Thread

app = Flask(__name__)

def get_db_conn():
    return psycopg2.connect(os.environ.get("DATABASE_URL"))

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/register', methods=['POST'])
def register_team():
    data = request.json
    team_name = data.get('team_name', '').strip()
    usernames = data.get('usernames', [])
    
    if not team_name or not usernames:
        return jsonify({"message": "Fill in all fields!"}), 400

    conn = None
    try:
        conn = get_db_conn()
        cur = conn.cursor()
        cur.execute("SELECT id FROM teams WHERE team_name = %s LIMIT 1", (team_name,))
        if cur.fetchone():
            return jsonify({"message": "Team Name already taken!"}), 400

        for user in usernames:
            clean_user = user.lower().replace('@', '').strip()
            cur.execute(
                "INSERT INTO teams (team_name, team_code, discord_username) VALUES (%s, %s, %s)",
                (team_name, "HACK26", clean_user)
            )
        conn.commit()
        return jsonify({"message": f"Team {team_name} is being built in Discord!"}), 200
    except Exception as e:
        return jsonify({"message": "Database Error"}), 500
    finally:
        if conn: conn.close()

@app.route('/status/<username>')
def check_status(username):
    clean_user = username.lower().replace('@', '').strip()
    conn = None
    try:
        conn = get_db_conn()
        cur = conn.cursor()
        cur.execute("SELECT team_name FROM teams WHERE discord_username = %s", (clean_user,))
        res = cur.fetchone()
        if res:
            return jsonify({"message": f"Verified! You are in Team: {res[0]}"}), 200
        return jsonify({"message": "No registration found."}), 404
    except Exception as e:
        return jsonify({"message": "Error"}), 500
    finally:
        if conn: conn.close()

def run():
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))

def keep_alive():
    Thread(target=run, daemon=True).start()
