from flask import Flask, render_template, request, jsonify
import psycopg2
import os
from threading import Thread

app = Flask(__name__)

# --- DATABASE HELPER ---
def get_db_conn():
    # Hugging Face will pull this from your "Secrets" tab
    return psycopg2.connect(os.environ.get("DATABASE_URL"))

@app.route('/')
def home():
    # Renders your glassmorphic index.html from /templates
    return render_template('index.html')

@app.route('/register', methods=['POST'])
def register_team():
    data = request.json
    team_name = data.get('team_name', '').strip()
    
    # Clean, lowercase, and deduplicate the input usernames
    raw_usernames = data.get('usernames', [])
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

        # 1. ANTI-SPAM: Check if Team Name exists
        cur.execute("SELECT 1 FROM teams WHERE LOWER(team_name) = LOWER(%s) LIMIT 1", (team_name,))
        if cur.fetchone():
            return jsonify({"message": f"The team name '{team_name}' is already taken!"}), 400

        # 2. THE IRONCLAD CHECK: Is ANY submitted username already registered?
        cur.execute("SELECT discord_username FROM teams WHERE discord_username = ANY(%s)", (usernames,))
        existing_users = cur.fetchall()
        
        if existing_users:
            taken_names = ", ".join([row[0] for row in existing_users])
            return jsonify({
                "message": f"Registration Denied: {taken_names} already belong to a team!"
            }), 400

        # 3. INSERTION: Commit to the Grid
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
    # MANDATORY: Hugging Face Spaces strictly requires port 7860
    # The SDK will fail to build if this is anything else.
    port = 7860
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    # Daemon thread ensures the server doesn't block the bot's hunter loop
    t = Thread(target=run, daemon=True)
    t.start()
