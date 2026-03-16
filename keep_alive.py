from flask import Flask, render_template, request, jsonify
import psycopg2
import os
from threading import Thread

app = Flask(__name__)

# Helper to get DB connection
def get_db_conn():
    return psycopg2.connect(os.environ.get("DATABASE_URL"))

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/register', methods=['POST'])
def register_team():
    data = request.json
    team_name = data.get('team_name')
    usernames = data.get('usernames', [])
    
    if not team_name or not usernames:
        return jsonify({"message": "Missing team name or members!"}), 400

    conn = None
    try:
        conn = get_db_conn()
        cur = conn.cursor()
        
        # 1. Check if team name is already taken
        cur.execute("SELECT id FROM teams WHERE team_name = %s LIMIT 1", (team_name,))
        if cur.fetchone():
            return jsonify({"message": "This Team Name is already taken!"}), 400

        # 2. Insert all members
        for user in usernames:
            clean_user = user.lower().replace('@', '').strip()
            cur.execute(
                "INSERT INTO teams (team_name, team_code, discord_username) VALUES (%s, %s, %s)",
                (team_name, "HACK26", clean_user)
            )
        
        conn.commit()
        return jsonify({"message": f"Success! Team '{team_name}' registered with {len(usernames)} members."}), 200
    
    except Exception as e:
        print(f"Registration Error: {e}")
        return jsonify({"message": "Database error. Please try again later."}), 500
    finally:
        if conn: conn.close()

@app.route('/status/<username>')
def check_status(username):
    # Decode and clean the username
    clean_user = username.lower().replace('@', '').strip()
    
    conn = None
    try:
        conn = get_db_conn()
        cur = conn.cursor()
        cur.execute("SELECT team_name FROM teams WHERE discord_username = %s", (clean_user,))
        res = cur.fetchone()
        
        if res:
            return jsonify({"message": f"Status: Registered! You belong to Team: {res[0]}"}), 200
        else:
            return jsonify({"message": "No registration found. Ask your leader to register you."}), 404
            
    except Exception as e:
        print(f"Status Error: {e}")
        return jsonify({"message": "Error checking status."}), 500
    finally:
        if conn: conn.close()

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run, daemon=True)
    t.start()
