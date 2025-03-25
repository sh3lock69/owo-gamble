import os
import random
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from pymongo import MongoClient

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "change_this_secret")
app.config["DEBUG"] = True  # Remove debug in production

# Connect to MongoDB Atlas (ensure MONGODB_URI is set in environment)
MONGODB_URI = os.environ["MONGODB_URI"]
client = MongoClient(MONGODB_URI)
db = client["discordbotdb"]
login_codes_col = db["login_codes"]
users_col = db["users"]

# ---------------------------------------
# Landing Page & Navigation Routes
# ---------------------------------------
@app.route('/')
def index():
    """Landing page with slider and top navigation."""
    return render_template("index.html")

@app.route('/support')
def support():
    """Support page."""
    return render_template("support.html")

@app.route('/games_info')
def games_info():
    """Games Info page."""
    return render_template("games_info.html")

@app.route('/about')
def about():
    """About page."""
    return render_template("about.html")

# ---------------------------------------
# Authentication Routes
# ---------------------------------------
@app.route('/login', methods=["GET", "POST"])
def login():
    """Login page."""
    if request.method == "POST":
        discord_id = request.form.get("discord_id")
        login_code = request.form.get("login_code")

        if not discord_id or not login_code:
            flash("Please enter both your Discord ID and login code.", "error")
            return redirect(url_for('login'))

        try:
            discord_id_int = int(discord_id)
        except ValueError:
            flash("Discord ID must be numeric.", "error")
            return redirect(url_for("login"))

        record = login_codes_col.find_one({"_id": discord_id_int})
        if record and record.get("code") == login_code:
            session["discord_id"] = discord_id_int
            flash("Successfully logged in!", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid Discord ID or login code.", "error")
            return redirect(url_for("login"))
    return render_template("login.html")

@app.route('/logout')
def logout():
    """Log the user out and return to landing page."""
    session.pop("discord_id", None)
    flash("Logged out successfully.", "success")
    return redirect(url_for("index"))

def login_required(route):
    """Decorator to require login."""
    def wrapper(*args, **kwargs):
        if "discord_id" not in session:
            flash("Please log in first.", "error")
            return redirect(url_for("login"))
        return route(*args, **kwargs)
    wrapper.__name__ = route.__name__
    return wrapper

# ---------------------------------------
# Dashboard & Mines Game Integration
# ---------------------------------------
@app.route('/dashboard')
@login_required
def dashboard():
    """Dashboard page showing user balance and featured Mine Game."""
    discord_id = session["discord_id"]
    user_doc = users_col.find_one({"_id": discord_id})
    balance = user_doc.get("balance", 0) if user_doc else 0
    return render_template("dashboard.html", balance=balance)

# (The routes for the mines game, e.g., /games/mines, /games/mines/start, etc., would be here.
# For brevity, they are omitted. You can integrate your previous mines game routes.)

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
