import os
import random
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from pymongo import MongoClient

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "change_this_secret")
app.config["DEBUG"] = True  # Disable in production

# Connect to MongoDB
MONGODB_URI = os.environ["MONGODB_URI"]
client = MongoClient(MONGODB_URI)
db = client["discordbotdb"]
login_codes_col = db["login_codes"]
users_col = db["users"]

# ---------------------------------
# Authentication & Basic Routes
# ---------------------------------
@app.route('/')
def index():
    """Root: redirect to home if logged in, else to login."""
    if "discord_id" in session:
        return redirect(url_for("home"))
    else:
        return redirect(url_for("login"))

@app.route('/login', methods=["GET", "POST"])
def login():
    """Login page."""
    if request.method == "POST":
        discord_id = request.form.get("discord_id")
        login_code = request.form.get("login_code")

        if not discord_id or not login_code:
            flash("Please enter both your Discord ID and login code.", "error")
            return redirect(url_for('login'))

        # Validate numeric Discord ID (adjust if IDs are strings)
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
    """Logout."""
    session.pop("discord_id", None)
    flash("Logged out successfully.", "success")
    return redirect(url_for("login"))

def login_required(route):
    """Decorator to ensure user is logged in."""
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
    """Simple homepage."""
    return render_template("home.html")

@app.route('/profile')
@login_required
def profile():
    """Profile page: show user data."""
    discord_id = session["discord_id"]
    user_doc = users_col.find_one({"_id": discord_id})
    profile_data = {
        "discord_id": discord_id,
        "balance": user_doc.get("balance", 0) if user_doc else 0,
    }
    return render_template("profile.html", profile=profile_data)

@app.route('/support')
@login_required
def support():
    """Support page."""
    return render_template("support.html")

# ---------------------------------
# Games Page & Mines Implementation
# ---------------------------------
@app.route('/games')
@login_required
def games():
    """
    Main games page: includes the 'Play Mines' button
    and a quick overview of the user's balance.
    """
    discord_id = session["discord_id"]
    user_doc = users_col.find_one({"_id": discord_id})
    balance = user_doc.get("balance", 0) if user_doc else 0
    return render_template("games.html", balance=balance)

@app.route('/games/mines')
@login_required
def mines_game():
    """
    Renders the Mines game page.
    We'll show a form for bet amount & mines,
    plus the 5x5 grid if a game is in progress.
    """
    discord_id = session["discord_id"]
    user_doc = users_col.find_one({"_id": discord_id})
    balance = user_doc.get("balance", 0) if user_doc else 0

    # Check if there's a game in progress stored in session
    current_game = session.get("mines_game")
    return render_template("mines_game.html", balance=balance, current_game=current_game)

@app.route('/games/mines/start', methods=['POST'])
@login_required
def start_mines():
    """
    Start a new Mines game:
    - Check bet + number of mines
    - Deduct bet from user balance
    - Randomly place bombs
    - Save game state in session
    """
    discord_id = session["discord_id"]
    user_doc = users_col.find_one({"_id": discord_id})
    balance = user_doc.get("balance", 0) if user_doc else 0

    try:
        bet_amount = float(request.form.get("bet_amount", 0))
        num_mines = int(request.form.get("mines", 1))
    except ValueError:
        flash("Invalid bet or mines input.", "error")
        return redirect(url_for("mines_game"))

    # Basic validations
    if bet_amount <= 0:
        flash("Bet amount must be greater than 0.", "error")
        return redirect(url_for("mines_game"))
    if num_mines < 1 or num_mines > 24:
        flash("Number of mines must be between 1 and 24.", "error")
        return redirect(url_for("mines_game"))
    if bet_amount > balance:
        flash("Insufficient balance to place this bet.", "error")
        return redirect(url_for("mines_game"))

    # Deduct bet from user balance
    new_balance = balance - bet_amount
    users_col.update_one({"_id": discord_id}, {"$set": {"balance": new_balance}})

    # Prepare 5x5 grid
    grid_size = 25  # 5x5
    bombs_positions = random.sample(range(grid_size), num_mines)  # unique bomb positions
    # Save game state in session
    session["mines_game"] = {
        "bet": bet_amount,
        "num_mines": num_mines,
        "bombs": bombs_positions,
        "revealed": [],
        "status": "ongoing",  # ongoing, lost, or cashed
        "picks": 0  # how many safe picks user has made
    }

    flash("New Mines game started!", "success")
    return redirect(url_for("mines_game"))

@app.route('/games/mines/reveal', methods=['POST'])
@login_required
def reveal_tile():
    """
    Reveal a tile in the Mines game.
    If it's a bomb -> game over.
    If it's safe -> increase picks.
    """
    tile_index = int(request.form.get("tile_index", -1))
    current_game = session.get("mines_game")

    if not current_game or current_game["status"] != "ongoing":
        return jsonify({"error": "No ongoing game."}), 400

    if tile_index < 0 or tile_index > 24:
        return jsonify({"error": "Invalid tile index."}), 400

    if tile_index in current_game["revealed"]:
        return jsonify({"error": "Tile already revealed."}), 400

    # Reveal the tile
    current_game["revealed"].append(tile_index)

    # Check if it's a bomb
    if tile_index in current_game["bombs"]:
        # Game over
        current_game["status"] = "lost"
        session["mines_game"] = current_game
        return jsonify({
            "result": "bomb",
            "message": "You hit a bomb! Game over."
        })
    else:
        # It's safe
        current_game["picks"] += 1
        session["mines_game"] = current_game
        return jsonify({
            "result": "safe",
            "message": "Safe pick! Keep going.",
            "picks": current_game["picks"]
        })

@app.route('/games/mines/cashout', methods=['POST'])
@login_required
def cashout_mines():
    """
    Let the user cash out based on how many picks they've made.
    Simple multiplier logic:
    - base multiplier ~ 1.0 at 0 picks
    - each safe pick increases multiplier
    - final payout = bet * multiplier
    """
    current_game = session.get("mines_game")
    if not current_game or current_game["status"] != "ongoing":
        return jsonify({"error": "No ongoing game to cash out from."}), 400

    picks = current_game["picks"]
    bet = current_game["bet"]

    # A simple example multiplier: 1.0 + (picks * 0.2)
    # You can make this more advanced or a table of multipliers
    multiplier = 1.0 + (picks * 0.2)
    payout = bet * multiplier

    # Update user's balance
    discord_id = session["discord_id"]
    user_doc = users_col.find_one({"_id": discord_id})
    balance = user_doc.get("balance", 0) if user_doc else 0
    new_balance = balance + payout
    users_col.update_one({"_id": discord_id}, {"$set": {"balance": new_balance}})

    # Mark game as cashed out
    current_game["status"] = "cashed"
    session["mines_game"] = current_game

    return jsonify({
        "message": f"You cashed out with {picks} safe picks! You won {payout:.2f} credits.",
        "new_balance": new_balance
    })

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
