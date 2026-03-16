from flask import Flask, render_template, request, jsonify
import psycopg2
import os
from threading import Thread

app = Flask(__name__)

# --- DATABASE HELPER ---
def get_db_conn():
    return psycopg2.connect(os.environ.get("DATABASE_URL"))

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/register', methods=['POST'])
def register_team():
    data = request.json
    team_name = data.get('team_name', '').strip()
    
    # Clean, lowercase, and deduplicate the input usernames
    raw_usernames = data.get('usernames', [])
    # Set comprehension handles deduplication automatically
    usernames = list({str(u).lower().replace('@', '').strip() for u in raw_usernames if u})

    # --- VALIDATION ---
    if not team_name or not usernames:
        return jsonify({"message": "Error: Team name and at least one user are required!"}), 400
    
    if len(usernames) > 5:
        return jsonify({"message": "Error: Maximum of 5 members allowed per team."}), 400

    conn = None
    try:
        conn = get_db_conn()
        cur = conn.cursor()

        # 1. ANTI-SPAM: Check if Team Name exists (Case-Insensitive)
        cur.execute("SELECT 1 FROM teams WHERE LOWER(team_name) = LOWER(%s) LIMIT 1", (team_name,))
        if cur.fetchone():
            return jsonify({"message": f"The team name '{team_name}' is already taken!"}), 400

        # 2. THE IRONCLAD CHECK: Is ANY submitted username already registered?
        # Using '= ANY(%s)' is the most reliable way to check a list against a column
        cur.execute("SELECT discord_username FROM teams WHERE discord_username = ANY(%s)", (usernames,))
        existing_users = cur.fetchall()
        
        if existing_users:
            # Create a string of the usernames that are already taken
            taken_names = ", ".join([row[0] for row in existing_users])
            return jsonify({
                "message": f"Registration Denied: {taken_names} already belong to a team!"
            }), 400

        # 3. INSERTION: Only runs if all checks above passed
        for user in usernames:
            cur.execute(
                "INSERT INTO teams (team_name, team_code, discord_username) VALUES (%s, %s, %s)",
                (team_name, "HACK26", user)
            )
        
        conn.commit()
        return jsonify({"message": f"Success! Team '{team_name}' registered. Join the Discord!"}), 200

    except Exception as e:
        print(f"CRITICAL REGISTRATION ERROR: {e}")
        return jsonify({"message": "Server error. Please try again later."}), 500
    finally:
        if conn:
            conn.close()

@app.route('/status/<username>')
def check_status(username):
    # Clean the username for the check
    user_to_check = str(username).lower().replace('@', '').strip()
    
    conn = None
    try:
        conn = get_db_conn()
        cur = conn.cursor()
        cur.execute("SELECT team_name FROM teams WHERE discord_username = %s", (user_to_check,))
        res = cur.fetchone()
        
        if res:
            return jsonify({"message": f"Verified! You are in Team: {res[0]}"}), 200
        else:
            return jsonify({"message": "No registration found. Ask your leader to register you."}), 404
            
    except Exception as e:
        print(f"STATUS CHECK ERROR: {e}")
        return jsonify({"message": "Error checking status."}), 500
    finally:
        if conn:
            conn.close()

# --- SERVER STARTUP ---
def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run, daemon=True)
    t.start()
