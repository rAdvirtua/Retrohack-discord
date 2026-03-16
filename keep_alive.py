from flask import Flask, render_template, request, jsonify
import psycopg2
import os
from threading import Thread

app = Flask(__name__)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/register', methods=['POST'])
def register_team():
    data = request.json
    team_name = data.get('team_name')
    usernames = data.get('usernames') # This is a list now
    
    db_url = os.environ.get("DATABASE_URL")
    try:
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        
        # Insert each member as a separate row tied to the same team name
        for user in usernames:
            cur.execute(
                "INSERT INTO teams (team_name, team_code, discord_username) VALUES (%s, %s, %s)",
                (team_name, "AUTO", user) # 'AUTO' placeholder as bot handles creation
            )
        conn.commit()
        return jsonify({"message": f"Team {team_name} registered! Everyone can now join Discord."}), 200
    except Exception as e:
        return jsonify({"message": "Team name already exists or database error."}), 400
    finally:
        if 'conn' in locals(): conn.close()

@app.route('/status/<username>')
def check_status(username):
    db_url = os.environ.get("DATABASE_URL")
    try:
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        cur.execute("SELECT team_name FROM teams WHERE discord_username = %s", (username.lower(),))
        res = cur.fetchone()
        if res:
            return jsonify({"message": f"Verified! You are in Team: **{res[0]}**"}), 200
        return jsonify({"message": "No team found for this username. Ask your leader to register you!"}), 404
    finally:
        if 'conn' in locals(): conn.close()

def run():
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))

def keep_alive():
    Thread(target=run, daemon=True).start()
