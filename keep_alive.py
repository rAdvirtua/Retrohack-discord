from flask import Flask, render_template, request, jsonify
import psycopg2, os
from threading import Thread

app = Flask(__name__)

def get_db():
    return psycopg2.connect(os.environ.get("DATABASE_URL"))

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/register', methods=['POST'])
def register():
    data = request.json
    t_name = data.get('team_name', '').strip()
    users = list(set([u.lower().replace('@','').strip() for u in data.get('usernames', []) if u]))
    
    if not t_name or not users: return jsonify({"message": "Incomplete data!"}), 400

    conn = None
    try:
        conn = get_db(); cur = conn.cursor()
        
        # Check Team Name
        cur.execute("SELECT id FROM teams WHERE team_name = %s LIMIT 1", (t_name,))
        if cur.fetchone(): return jsonify({"message": "Team name taken!"}), 400

        # Anti-Spam Check
        cur.execute("SELECT discord_username FROM teams WHERE discord_username IN %s", (tuple(users),))
        exist = cur.fetchall()
        if exist:
            names = ", ".join([x[0] for x in exist])
            return jsonify({"message": f"Users already on teams: {names}"}), 400

        for u in users:
            cur.execute("INSERT INTO teams (team_name, team_code, discord_username) VALUES (%s, %s, %s)", (t_name, "HACK26", u))
        
        conn.commit()
        return jsonify({"message": f"Team {t_name} is being built!"}), 200
    except Exception as e:
        return jsonify({"message": "Error registering team."}), 500
    finally:
        if conn: conn.close()

@app.route('/status/<user>')
def status(user):
    u = user.lower().replace('@','').strip()
    conn = None
    try:
        conn = get_db(); cur = conn.cursor()
        cur.execute("SELECT team_name FROM teams WHERE discord_username = %s", (u,))
        res = cur.fetchone()
        if res: return jsonify({"message": f"You are in Team: {res[0]}"}), 200
        return jsonify({"message": "No registration found."}), 404
    finally:
        if conn: conn.close()

def run():
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))

def keep_alive():
    Thread(target=run, daemon=True).start()
