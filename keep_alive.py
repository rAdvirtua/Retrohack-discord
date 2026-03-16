from flask import Flask, render_template, request, jsonify
from threading import Thread
import psycopg2
import os

app = Flask(__name__)

# Route to serve the HTML website
@app.route('/')
def home():
    # Make sure index.html is inside a folder named 'templates'!
    return render_template('index.html')

# API Route to handle form submissions
@app.route('/register', methods=['POST'])
def register_team():
    data = request.json
    team_name = data.get('team_name')
    team_code = data.get('team_code')

    DATABASE_URL = os.environ.get("DATABASE_URL")
    
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        
        # Insert the new team into PostgreSQL
        cursor.execute(
            "INSERT INTO teams (team_name, team_code) VALUES (%s, %s)", 
            (team_name, team_code)
        )
        conn.commit()
        success = True
        message = "Team registered successfully! Head over to Discord to verify."
    except psycopg2.IntegrityError:
        # This catches if someone tries to use a team code that already exists
        success = False
        message = "That Team Code is already in use!"
    except Exception as e:
        print(f"Database error: {e}")
        success = False
        message = "An error occurred while saving to the database."
    finally:
        # Always close the connection to avoid maxing out your Neon limits
        if 'cursor' in locals(): cursor.close()
        if 'conn' in locals(): conn.close()

    if success:
        return jsonify({"message": message}), 200
    else:
        return jsonify({"message": message}), 400

def run():
    # Render assigns a dynamic port, so we must use os.environ.get
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()
