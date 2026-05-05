from flask import Flask, request, jsonify
import sqlite3
import os
import threading
import subprocess
import time
import datetime

app = Flask(__name__)

@app.route('/')
def health():
    return "OK", 200

@app.route('/check', methods=['GET'])
def check():
    key_code = request.args.get('key')
    hwid = request.args.get('hwid')
    
    print(f"API: Request for key='{key_code}', hwid='{hwid}'")
    
    if not key_code or not hwid:
        return jsonify({"valid": False, "reason": "Missing key or HWID"}), 400
    
    key_code = key_code.strip()
    hwid = hwid.strip()
    
    try:
        conn = sqlite3.connect("vanity.db")
        cursor = conn.cursor()
        
        # Check if key exists
        cursor.execute("SELECT is_redeemed, redeemed_by, hwid, expiration FROM keys WHERE key = ?", (key_code,))
        row = cursor.fetchone()
        
        if not row:
            conn.close()
            return jsonify({"valid": False, "reason": "Invalid key"}), 200
        
        is_redeemed, user_id, saved_hwid, expiration = row
        
        # Check Expiration
        if expiration is not None:
            # SQLite stores datetime as string. Convert to datetime object.
            # Format usually 'YYYY-MM-DD HH:MM:SS.mmmmmm'
            try:
                exp_dt = datetime.datetime.fromisoformat(expiration)
                if datetime.datetime.now() > exp_dt:
                    conn.close()
                    return jsonify({"valid": False, "reason": "Key expired"}), 200
            except:
                pass # If parsing fails, assume lifetime or malformed
        
        if is_redeemed == 0:
            conn.close()
            return jsonify({"valid": False, "reason": "Key not redeemed yet"}), 200
        
        # Check blacklist
        cursor.execute("SELECT user_id FROM blacklists WHERE user_id = ?", (user_id,))
        if cursor.fetchone():
            conn.close()
            return jsonify({"valid": False, "reason": "Blacklisted user"}), 200
            
        # Check HWID
        if saved_hwid is None:
            # Bind HWID on first use
            cursor.execute("UPDATE keys SET hwid = ? WHERE key = ?", (hwid, key_code))
            conn.commit()
            print(f"API: Bound key {key_code} to HWID {hwid}")
        elif saved_hwid != hwid:
            conn.close()
            return jsonify({"valid": False, "reason": "HWID mismatch"}), 200
            
        conn.close()
        return jsonify({"valid": True, "reason": "success"}), 200
        
    except Exception as e:
        print(f"API Error: {e}")
        return jsonify({"valid": False, "reason": f"Internal server error: {e}"}), 500

def init_db():
    print("API: Initializing Database...")
    conn = sqlite3.connect("vanity.db")
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS keys (
        key TEXT PRIMARY KEY,
        duration TEXT,
        expiration TIMESTAMP,
        is_redeemed INTEGER DEFAULT 0,
        redeemed_by INTEGER,
        hwid TEXT
    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS blacklists (
        user_id INTEGER PRIMARY KEY
    )''')
    conn.commit()
    conn.close()
    print("API: Database ready.")

def run_bot():
    print("API: Starting Discord Bot...")
    try:
        # Use sys.executable to ensure we use the same python interpreter
        import sys
        subprocess.run([sys.executable, "bot.py"])
    except Exception as e:
        print(f"API: Bot failed to start: {e}")

if __name__ == '__main__':
    init_db()
    
    # Start bot in background
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    
    port = int(os.getenv('PORT', 8080))
    print(f"API: Listening on port {port}")
    
    # Use threaded=True to handle concurrent requests better
    app.run(host='0.0.0.0', port=port, threaded=True)
