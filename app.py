import os
import random
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from pymongo import MongoClient

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "change_this_secret")
app.config["DEBUG"] = True  # Remove or disable in production

# Connect to MongoDB Atlas (same as your Discord bot)
MONGODB_URI = os.environ["MONGODB_URI"]
client = MongoClient(MONGODB_URI)
db = client["discordbotdb"]
login_codes_col = db["login_codes"]
users_col = db["users"]

@app.route('/', methods=["GET", "POST"])
def login():
    """
    Login route where the user enters their Discord ID and login code.
    """
    if request.method == "POST":
        discord_id = request.form.get("discord_id")
        login_code = request.form.get("login_code")

        if not discord_id or not login_code:
            flash("Please enter both your Discord ID and login code.", "error")
            return redirect(url_for('login'))

        # Validate that Discord ID is numeric
        try:
            discord_id_int = int(discord_id)
        except ValueError:
            flash("Discord ID must be numeric.", "error")
            return redirect(url_for("login"))

        # Try to find the login code in MongoDB
        record = login_codes_col.find_one({"_id": discord_id_int})
        if record and record.get("code") == login_code:
            # Mark user as logged in by storing their Discord ID in the session
            session["discord_id"] = discord_id_int
            flash("Successfully logged in!", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid Discord ID or login code.", "error")
            return redirect(url_for("login"))
    return render_template("login.html")

@app.route('/dashboard')
def dashboard():
    """
    Dashboard showing the user’s balance and the Mine game.
    """
    if "discord_id" not in session:
        flash("Please log in first.", "error")
        return redirect(url_for("login"))

    discord_id = session["discord_id"]
    try:
        user_doc = users_col.find_one({"_id": discord_id})
        balance = user_doc.get("balance", 0) if user_doc else 0
    except Exception as e:
        return f"Database error: {str(e)}", 500

    return render_template("dashboard.html", discord_id=discord_id, balance=balance)

@app.route('/mine', methods=['POST'])
def mine():
    """
    Simple mine game endpoint.
    Randomly awards a reward and updates the user’s balance.
    """
    if "discord_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    discord_id = session["discord_id"]

    # 70% chance of winning a reward
    if random.random() > 0.3:
        reward = random.randint(5, 20)
    else:
        reward = 0

    # Update user's balance in the database
    user_doc = users_col.find_one({"_id": discord_id})
    if user_doc:
        new_balance = user_doc.get("balance", 0) + reward
        users_col.update_one({"_id": discord_id}, {"$set": {"balance": new_balance}})
    else:
        new_balance = reward
        users_col.insert_one({"_id": discord_id, "balance": new_balance})

    message = f"You mined {reward} credits!" if reward > 0 else "No luck this time. Try again!"
    return jsonify({"balance": new_balance, "reward": reward, "message": message})

@app.route('/logout')
def logout():
    """Log the user out."""
    session.pop("discord_id", None)
    flash("Logged out successfully.", "success")
    return redirect(url_for("login"))

if __name__ == '__main__':
    # For production, Railway will use a proper web server.
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
