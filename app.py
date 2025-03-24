import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
from pymongo import MongoClient

app = Flask(__name__)


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

        # Try to find the login code in MongoDB
        record = login_codes_col.find_one({"_id": int(discord_id)})
        if record and record.get("code") == login_code:
            # Mark user as logged in

            flash("Successfully logged in!", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid Discord ID or login code.", "error")
            return redirect(url_for("login"))
    return render_template("login.html")

@app.route('/dashboard')
def dashboard():
    """
    Dashboard showing the user’s balance.
    """
    if "discord_id" not in session:
        flash("Please log in first.", "error")
        return redirect(url_for("login"))

    discord_id = session["discord_id"]
    # Fetch user document from the users collection
    user_doc = users_col.find_one({"_id": discord_id})
    balance = user_doc.get("balance", 0) if user_doc else 0

    return render_template("dashboard.html", discord_id=discord_id, balance=balance)

@app.route('/logout')
def logout():
    """Log the user out."""

    flash("Logged out successfully.", "success")
    return redirect(url_for("login"))

if __name__ == '__main__':
    # For production, Railway will use a proper web server.
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
