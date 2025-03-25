import os
import random
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from pymongo import MongoClient

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "change_this_secret")
app.config["DEBUG"] = True  # Remove in production

# Connect to MongoDB Atlas (ensure MONGODB_URI is set in your environment)
MONGODB_URI = os.environ["MONGODB_URI"]
client = MongoClient(MONGODB_URI)
db = client["discordbotdb"]
login_codes_col = db["login_codes"]
users_col = db["users"]

# ---------------------
# Authentication Routes
# ---------------------
@app.route('/')
def index():
    """
    Root route: if logged in, show home page; otherwise, show login page.
    """
    if "discord_id" in session:
        return redirect(url_for("home"))
    else:
        return redirect(url_for("login"))

@app.route('/login', methods=["GET", "POST"])
def login():
    """
    Login page: users enter their Discord ID and login code.
    """
    if request.method == "POST":
        discord_id = request.form.get("discord_id")
        login_code = request.form.get("login_code")

        if not discord_id or not login_code:
            flash("Please enter both your Discord ID and login code.", "error")
            return redirect(url_for('login'))

        # Validate that Discord ID is numeric (adjust if IDs are alphanumeric)
        try:
            discord_id_int = int(discord_id)
        except ValueError:
            flash("Discord ID must be numeric.", "error")
            return redirect(url_for("login"))

        record = login_codes_col.find_one({"_id": discord_id_int})
        if record and record.get("code") == login_code:
            session["discord_id"] = discord_id_int
            flash("Successfully logged in!", "success")
            return redirect(url_for("home"))
        else:
            flash("Invalid Discord ID or login code.", "error")
            return redirect(url_for("login"))
    return render_template("login.html")

@app.route('/logout')
def logout():
    """Log the user out."""
    session.pop("discord_id", None)
    flash("Logged out successfully.", "success")
    return redirect(url_for("login"))

# ---------------------
# Main Application Routes
# ---------------------
def login_required(route):
    """Decorator to ensure a user is logged in."""
    def wrapper(*args, **kwargs):
        if "discord_id" not in session:
            flash("Please log in first.", "error")
            return redirect(url_for("login"))
        return route(*args, **kwargs)
    wrapper.__name__ = route.__name__
    return wrapper

@app.route('/home')
@login_required
def home():
    """Home page with an overview and navigation."""
    discord_id = session["discord_id"]
    return render_template("home.html", discord_id=discord_id)

@app.route('/profile')
@login_required
def profile():
    """Profile page: show user's details and balance."""
    discord_id = session["discord_id"]
    user_doc = users_col.find_one({"_id": discord_id})
    profile_data = {
        "discord_id": discord_id,
        "balance": user_doc.get("balance", 0) if user_doc else 0,
        # Additional profile data can be added here.
    }
    return render_template("profile.html", profile=profile_data)

@app.route('/games')
@login_required
def games():
    """Games page: list available games (including the mine game)."""
    discord_id = session["discord_id"]
    user_doc = users_col.find_one({"_id": discord_id})
    balance = user_doc.get("balance", 0) if user_doc else 0
    return render_template("games.html", balance=balance)

@app.route('/support')
@login_required
def support():
    """Support page: contact or support info."""
    return render_template("support.html")

# ---------------------
# Mine Game Endpoint
# ---------------------
@app.route('/mine', methods=['POST'])
@login_required
def mine():
    """
    Simple mine game: randomly award credits and update balance.
    """
    discord_id = session["discord_id"]
    reward = random.randint(5, 20) if random.random() > 0.3 else 0

    user_doc = users_col.find_one({"_id": discord_id})
    if user_doc:
        new_balance = user_doc.get("balance", 0) + reward
        users_col.update_one({"_id": discord_id}, {"$set": {"balance": new_balance}})
    else:
        new_balance = reward
        users_col.insert_one({"_id": discord_id, "balance": new_balance})

    message = f"You mined {reward} credits!" if reward > 0 else "No luck this time. Try again!"
    return jsonify({"balance": new_balance, "reward": reward, "message": message})

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
