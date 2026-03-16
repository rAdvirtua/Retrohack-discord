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
    db_url = os.environ.get("DATABASE_URL")
    
    try:
        conn = psycopg2.connect(db_url)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO teams (team_name, team_code) VALUES (%s, %s)", (team_name, team_code))
        conn.commit()
        return jsonify({"message": "Team registered successfully!"}), 200
    except psycopg2.IntegrityError:
        return jsonify({"message": "Code already in use!"}), 400
    except Exception as e:
        print(f"Web Registration Error: {e}")
        return jsonify({"message": "Server error"}), 500
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'conn' in locals(): conn.close()

def run():
    # Render explicitly looks for this PORT variable
    port = int(os.environ.get("PORT", 8080))
    print(f"Starting Flask on port {port}...")
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()
