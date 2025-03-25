import os
import random
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from pymongo import MongoClient

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "change_this_secret")
app.config["DEBUG"] = True  # Disable debug in production

# Connect to MongoDB Atlas (set your MONGODB_URI in environment)
MONGODB_URI = os.environ["MONGODB_URI"]
client = MongoClient(MONGODB_URI)
db = client["discordbotdb"]
login_codes_col = db["login_codes"]
users_col = db["users"]

# ---------------------------------------
# Landing & Navigation Routes
# ---------------------------------------
@app.route('/')
def index():
    """If user is logged in, redirect to dashboard; otherwise, show landing page."""
    if session.get("discord_id"):
        return redirect(url_for("dashboard"))
    return render_template("index.html")

@app.route('/support')
def support():
    return render_template("support.html")

@app.route('/games_info')
def games_info():
    return render_template("games_info.html")

@app.route('/about')
def about():
    return render_template("about.html")

# ---------------------------------------
# Authentication Routes
# ---------------------------------------
@app.route('/login', methods=["GET", "POST"])
def login():
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
    session.pop("discord_id", None)
    flash("Logged out successfully.", "success")
    return redirect(url_for("index"))

def login_required(route):
    def wrapper(*args, **kwargs):
        if "discord_id" not in session:
            flash("Please log in first.", "error")
            return redirect(url_for("login"))
        return route(*args, **kwargs)
    wrapper.__name__ = route.__name__
    return wrapper

# ---------------------------------------
# Dashboard & Mines Game Routes
# ---------------------------------------
@app.route('/dashboard')
@login_required
def dashboard():
    discord_id = session["discord_id"]
    user_doc = users_col.find_one({"_id": discord_id})
    balance = user_doc.get("balance", 0) if user_doc else 0
    return render_template("dashboard.html", balance=balance)

@app.route('/games/mines')
@login_required
def mines_game():
    discord_id = session["discord_id"]
    user_doc = users_col.find_one({"_id": discord_id})
    balance = user_doc.get("balance", 0) if user_doc else 0
    current_game = session.get("mines_game")
    return render_template("mines_game.html", balance=balance, current_game=current_game)

@app.route('/games/mines/start', methods=['POST'])
@login_required
def start_mines():
    discord_id = session["discord_id"]
    user_doc = users_col.find_one({"_id": discord_id})
    balance = user_doc.get("balance", 0) if user_doc else 0
    try:
        bet_amount = float(request.form.get("bet_amount", 0))
        num_mines = int(request.form.get("mines", 1))
    except ValueError:
        flash("Invalid bet or mines input.", "error")
        return redirect(url_for("mines_game"))
    if bet_amount <= 0:
        flash("Bet amount must be greater than 0.", "error")
        return redirect(url_for("mines_game"))
    if num_mines < 1 or num_mines > 24:
        flash("Number of mines must be between 1 and 24.", "error")
        return redirect(url_for("mines_game"))
    if bet_amount > balance:
        flash("Insufficient balance to place this bet.", "error")
        return redirect(url_for("mines_game"))
    new_balance = balance - bet_amount
    users_col.update_one({"_id": discord_id}, {"$set": {"balance": new_balance}})
    grid_size = 25
    bombs_positions = random.sample(range(grid_size), num_mines)
    session["mines_game"] = {
        "bet": bet_amount,
        "num_mines": num_mines,
        "bombs": bombs_positions,
        "revealed": [],
        "status": "ongoing",
        "picks": 0
    }
    flash("New Mines game started!", "success")
    return redirect(url_for("mines_game"))

@app.route('/games/mines/reveal', methods=['POST'])
@login_required
def reveal_tile():
    tile_index = request.form.get("tile_index")
    if tile_index is None:
        return jsonify({"error": "No tile index provided"}), 400
    try:
        tile_index = int(tile_index)
    except ValueError:
        return jsonify({"error": "Invalid tile index"}), 400
    current_game = session.get("mines_game")
    if not current_game or current_game["status"] != "ongoing":
        return jsonify({"error": "No ongoing game."}), 400
    if tile_index < 0 or tile_index >= 25:
        return jsonify({"error": "Tile index out of range"}), 400
    if tile_index in current_game["revealed"]:
        return jsonify({"error": "Tile already revealed"}), 400
    current_game["revealed"].append(tile_index)
    if tile_index in current_game["bombs"]:
        current_game["status"] = "lost"
        session["mines_game"] = current_game
        return jsonify({"result": "bomb", "message": "You hit a bomb! Game over."})
    else:
        current_game["picks"] += 1
        session["mines_game"] = current_game
        return jsonify({"result": "safe", "message": "Safe pick! Keep going.", "picks": current_game["picks"]})

@app.route('/games/mines/cashout', methods=['POST'])
@login_required
def cashout_mines():
    current_game = session.get("mines_game")
    if not current_game or current_game["status"] != "ongoing":
        return jsonify({"error": "No ongoing game to cash out from."}), 400
    picks = current_game["picks"]
    bet = current_game["bet"]
    multiplier = 1.0 + (picks * 0.2)
    payout = bet * multiplier
    discord_id = session["discord_id"]
    user_doc = users_col.find_one({"_id": discord_id})
    balance = user_doc.get("balance", 0) if user_doc else 0
    new_balance = balance + payout
    users_col.update_one({"_id": discord_id}, {"$set": {"balance": new_balance}})
    current_game["status"] = "cashed"
    session["mines_game"] = current_game
    return jsonify({"message": f"You cashed out with {picks} safe picks! You won {payout:.2f} credits.", "new_balance": new_balance})

@app.route('/games/mines/new', methods=['POST'])
@login_required
def new_mines_game():
    session.pop("mines_game", None)
    return jsonify({"message": "New game ready."})

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
