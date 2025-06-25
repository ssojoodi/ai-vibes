# Restaurant list maintained by admin via dropdown
from flask import (
    Flask,
    render_template_string,
    request,
    redirect,
    url_for,
    session,
    flash,
)
import sqlite3
from datetime import datetime, date
import os

app = Flask(__name__)
app.secret_key = "your_secret_key_here"  # Change this in production


def get_db():
    # Use data directory for database persistence in Docker
    db_path = (
        os.path.join("data", "lunch_auction.db")
        if os.path.exists("data")
        else "lunch_auction.db"
    )
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def get_today_auction():
    conn = get_db()
    today = date.today().isoformat()

    # Get or create today's auction
    auction = conn.execute("SELECT * FROM auctions WHERE date = ?", (today,)).fetchone()

    if not auction:
        conn.execute("INSERT INTO auctions (date) VALUES (?)", (today,))
        conn.commit()
        auction = conn.execute(
            "SELECT * FROM auctions WHERE date = ?", (today,)
        ).fetchone()

    conn.close()
    return auction


def check_auction_complete():
    conn = get_db()
    today = date.today().isoformat()

    # Count total users and bids for today
    total_users = conn.execute(
        "SELECT COUNT(*) as count FROM users WHERE is_admin = 0"
    ).fetchone()["count"]
    total_bids = conn.execute(
        """
        SELECT COUNT(*) as count FROM bids b
        JOIN auctions a ON b.auction_id = a.id
        WHERE a.date = ?
    """,
        (today,),
    ).fetchone()["count"]

    if total_bids == total_users:
        # All users have bid, find the highest bid amount
        highest_bid = conn.execute(
            """
            SELECT b.bid_amount, COUNT(*) as winner_count
            FROM bids b
            JOIN auctions a ON b.auction_id = a.id
            WHERE a.date = ?
            GROUP BY b.bid_amount
            ORDER BY b.bid_amount DESC
            LIMIT 1
        """,
            (today,),
        ).fetchone()

        if highest_bid:
            # Get all winners (in case of a tie)
            winners = conn.execute(
                """
                SELECT b.*, u.name 
                FROM bids b
                JOIN users u ON b.user_id = u.id
                JOIN auctions a ON b.auction_id = a.id
                WHERE a.date = ? AND b.bid_amount = ?
                ORDER BY b.created_at ASC
            """,
                (today, highest_bid["bid_amount"]),
            ).fetchall()

            if winners:
                # In case of a tie, use the first person's restaurant choice
                first_winner = winners[0]
                winner_count = highest_bid["winner_count"]
                points_to_deduct = (
                    highest_bid["bid_amount"] // winner_count
                )  # Split points among tied winners

                # Update auction with winner info
                conn.execute(
                    """
                    UPDATE auctions 
                    SET winner_id = ?, winning_restaurant = ?, winning_bid = ?, status = 'completed'
                    WHERE date = ?
                """,
                    (
                        first_winner["user_id"],
                        first_winner["restaurant"],
                        points_to_deduct,
                        today,
                    ),
                )

                # For tied winners, deduct split points
                winner_ids = [w["user_id"] for w in winners]
                placeholders = ",".join("?" * len(winner_ids))
                conn.execute(
                    f"""
                    UPDATE users 
                    SET current_points = current_points - ?
                    WHERE id IN ({placeholders})
                """,
                    [points_to_deduct] + winner_ids,
                )

                # For non-winners, deduct full bid amount
                conn.execute(
                    f"""
                    UPDATE users 
                    SET current_points = current_points - (
                        SELECT bid_amount FROM bids b
                        JOIN auctions a ON b.auction_id = a.id
                        WHERE b.user_id = users.id AND a.date = ?
                    )
                    WHERE id IN (
                        SELECT user_id FROM bids b
                        JOIN auctions a ON b.auction_id = a.id
                        WHERE a.date = ? AND b.user_id NOT IN ({placeholders})
                    )
                """,
                    [today, today] + winner_ids,
                )

                # Check if anyone has points left
                users_with_points = conn.execute(
                    "SELECT COUNT(*) as count FROM users WHERE current_points > 0"
                ).fetchone()["count"]

                # If no one has points, reset everyone to 15
                if users_with_points == 0:
                    user_count = conn.execute(
                        "SELECT COUNT(*) as count FROM users WHERE is_admin = 0"
                    ).fetchone()["count"]
                    initial_points = 15 * max(
                        1, user_count // 10
                    )  # Scale with team size
                    conn.execute(
                        "UPDATE users SET current_points = ? WHERE is_admin = 0",
                        (initial_points,),
                    )

                conn.commit()

    conn.close()


def require_login():
    if "user_id" not in session:
        return redirect(url_for("login"))
    return None


def require_admin():
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db()
    user = conn.execute(
        "SELECT is_admin FROM users WHERE id = ?", (session["user_id"],)
    ).fetchone()
    conn.close()

    if not user or not user["is_admin"]:
        flash("Admin access required")
        return redirect(url_for("dashboard"))
    return None


@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = get_db()
        user = conn.execute(
            "SELECT * FROM users WHERE name = ? AND password = ?", (username, password)
        ).fetchone()
        conn.close()

        if user:
            session["user_id"] = user["id"]
            session["username"] = user["name"]
            session["is_admin"] = user["is_admin"]
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid username or password")

    return render_template_string(LOGIN_TEMPLATE)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/dashboard")
def dashboard():
    redirect_response = require_login()
    if redirect_response:
        return redirect_response

    conn = get_db()
    user = conn.execute(
        "SELECT * FROM users WHERE id = ?", (session["user_id"],)
    ).fetchone()

    if user["is_admin"]:
        return redirect(url_for("admin"))

    auction = get_today_auction()

    # Get user's current bid for today
    user_bid = conn.execute(
        """
        SELECT b.*, u.name FROM bids b
        JOIN users u ON b.user_id = u.id
        WHERE b.auction_id = ? AND b.user_id = ?
    """,
        (auction["id"], session["user_id"]),
    ).fetchone()

    # Get active restaurants for the dropdown
    ideas = conn.execute(
        "SELECT name FROM ideas WHERE is_active = 1 ORDER BY name"
    ).fetchall()

    conn.close()

    return render_template_string(
        USER_DASHBOARD_TEMPLATE,
        user=user,
        user_bid=user_bid,
        auction=auction,
        restaurants=ideas,
        today=date.today().isoformat(),
    )


@app.route("/admin")
def admin():
    redirect_response = require_admin()
    if redirect_response:
        return redirect_response

    auction = get_today_auction()
    conn = get_db()

    # Get users with their current points
    users = conn.execute(
        "SELECT * FROM users WHERE is_admin = 0 ORDER BY name"
    ).fetchall()

    # Get today's bids
    bids = conn.execute(
        """
        SELECT b.*, u.name FROM bids b
        JOIN users u ON b.user_id = u.id
        WHERE b.auction_id = ?
        ORDER BY b.bid_amount DESC
    """,
        (auction["id"],),
    ).fetchall()

    # Get recent winners (last 7 days)
    recent_winners = conn.execute("""
        SELECT a.date, u.name, a.winning_restaurant, a.winning_bid
        FROM auctions a
        JOIN users u ON a.winner_id = u.id
        WHERE a.status = 'completed'
        ORDER BY a.date DESC
        LIMIT 7
    """).fetchall()

    # Get active restaurants for the dropdown
    ideas = conn.execute(
        "SELECT name FROM ideas WHERE is_active = 1 ORDER BY name"
    ).fetchall()

    conn.close()

    return render_template_string(
        ADMIN_TEMPLATE,
        users=users,
        bids=bids,
        auction=auction,
        recent_winners=recent_winners,
        restaurants=ideas,
        today=date.today().isoformat(),
    )


@app.route("/ideas")
def manage_ideas():
    redirect_response = require_admin()
    if redirect_response:
        return redirect_response

    conn = get_db()
    ideas = conn.execute("SELECT * FROM ideas ORDER BY name").fetchall()
    conn.close()

    return render_template_string(IDEAS_TEMPLATE, restaurants=ideas)


@app.route("/ideas/add", methods=["POST"])
def add_restaurant():
    redirect_response = require_admin()
    if redirect_response:
        return redirect_response

    name = request.form["name"].strip()
    if not name:
        flash("Restaurant name cannot be empty")
        return redirect(url_for("manage_ideas"))

    conn = get_db()
    try:
        conn.execute("INSERT INTO ideas (name) VALUES (?)", (name,))
        conn.commit()
        flash(f"Idea '{name}' added successfully!")
    except sqlite3.IntegrityError:
        flash("Idea already exists!")
    conn.close()

    return redirect(url_for("manage_ideas"))


@app.route("/ideas/toggle/<int:idea_id>", methods=["POST"])
def toggle_idea(idea_id):
    redirect_response = require_admin()
    if redirect_response:
        return redirect_response

    conn = get_db()
    restaurant = conn.execute("SELECT * FROM ideas WHERE id = ?", (idea_id,)).fetchone()

    if restaurant:
        new_status = not restaurant["is_active"]
        conn.execute(
            "UPDATE ideas SET is_active = ? WHERE id = ?",
            (new_status, idea_id),
        )
        conn.commit()
        status_text = "activated" if new_status else "deactivated"
        flash(f"Idea '{restaurant['name']}' {status_text}!")
    conn.close()

    return redirect(url_for("manage_ideas"))


@app.route("/ideas/delete/<int:idea_id>", methods=["POST"])
def delete_idea(idea_id):
    redirect_response = require_admin()
    if redirect_response:
        return redirect_response

    conn = get_db()
    idea = conn.execute("SELECT * FROM ideas WHERE id = ?", (idea_id,)).fetchone()

    if idea:
        conn.execute("DELETE FROM ideas WHERE id = ?", (idea_id,))
        conn.commit()
        flash(f"Idea '{idea['name']}' deleted!")
    conn.close()

    return redirect(url_for("manage_ideas"))


@app.route("/bid", methods=["POST"])
def place_bid():
    redirect_response = require_login()
    if redirect_response:
        return redirect_response

    restaurant = request.form["restaurant"]
    bid_amount = int(request.form["bid_amount"])
    user_id = session["user_id"]

    auction = get_today_auction()
    conn = get_db()

    # Check if user has enough points
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if user["current_points"] < bid_amount:
        flash("Not enough points for this bid!")
        conn.close()
        return redirect(url_for("dashboard"))

    # Place or update bid
    conn.execute(
        """
        INSERT OR REPLACE INTO bids (auction_id, user_id, restaurant, bid_amount)
        VALUES (?, ?, ?, ?)
    """,
        (auction["id"], user_id, restaurant, bid_amount),
    )

    conn.commit()
    conn.close()

    # Check if auction is complete
    check_auction_complete()

    flash("Bid placed successfully!")
    return redirect(url_for("dashboard"))


@app.route("/admin/bid", methods=["POST"])
def admin_place_bid():
    redirect_response = require_admin()
    if redirect_response:
        return redirect_response

    restaurant = request.form["restaurant"]
    bid_amount = int(request.form["bid_amount"])
    target_user_id = int(request.form["user_id"])

    auction = get_today_auction()
    conn = get_db()

    # Verify target user exists and is not an admin
    target_user = conn.execute(
        "SELECT * FROM users WHERE id = ? AND is_admin = 0", (target_user_id,)
    ).fetchone()

    if not target_user:
        flash("Invalid user selected!")
        conn.close()
        return redirect(url_for("admin"))

    # Check if user has enough points
    if target_user["current_points"] < bid_amount:
        flash(
            f"Not enough points for this bid! {target_user['name']} only has {target_user['current_points']} points."
        )
        conn.close()
        return redirect(url_for("admin"))

    # Place or update bid
    conn.execute(
        """
        INSERT OR REPLACE INTO bids (auction_id, user_id, restaurant, bid_amount)
        VALUES (?, ?, ?, ?)
    """,
        (auction["id"], target_user_id, restaurant, bid_amount),
    )

    conn.commit()
    conn.close()

    # Check if auction is complete
    check_auction_complete()

    flash(f"Bid placed successfully on behalf of {target_user['name']}!")
    return redirect(url_for("admin"))


LOGIN_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🍽️ Team Lunch Auction - Login</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        :root {
            --primary-50: #f8fafc;
            --primary-100: #f1f5f9;
            --primary-200: #e2e8f0;
            --primary-300: #cbd5e1;
            --primary-400: #94a3b8;
            --primary-500: #64748b;
            --primary-600: #475569;
            --primary-700: #334155;
            --primary-800: #1e293b;
            --primary-900: #0f172a;
            --accent-500: #3b82f6;
            --success-500: #22c55e;
            --error-500: #ef4444;
        }
        
        body {
            font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: linear-gradient(to bottom right, var(--primary-50), var(--primary-100));
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            color: var(--primary-800);
        }
        
        .login-container {
            background: white;
            border-radius: 20px;
            padding: 48px;
            box-shadow: 0 10px 25px rgba(0, 0, 0, 0.1);
            border: 1px solid var(--primary-200);
            width: 100%;
            max-width: 400px;
        }
        
        .login-header {
            text-align: center;
            margin-bottom: 32px;
        }
        
        .login-header h1 {
            font-size: 2rem;
            font-weight: 600;
            color: var(--primary-900);
            margin-bottom: 8px;
        }
        
        .login-header p {
            color: var(--primary-600);
            font-size: 15px;
        }
        
        .login-form {
            display: grid;
            gap: 20px;
        }
        
        .form-group {
            display: grid;
            gap: 8px;
        }
        
        .form-group label {
            font-weight: 500;
            color: var(--primary-700);
            font-size: 14px;
        }
        
        .form-group input {
            padding: 14px 16px;
            border: 1.5px solid var(--primary-300);
            border-radius: 12px;
            font-size: 15px;
            transition: all 0.2s ease;
            background: white;
            color: var(--primary-800);
            font-family: inherit;
        }
        
        .form-group input:focus {
            outline: none;
            border-color: var(--accent-500);
            box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.08);
        }
        
        .btn {
            background: var(--primary-900);
            color: white;
            border: none;
            padding: 16px 24px;
            border-radius: 12px;
            font-size: 15px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s ease;
            font-family: inherit;
        }
        
        .btn:hover {
            background: var(--primary-800);
            transform: translateY(-1px);
        }
        
        .flash-messages {
            margin-bottom: 20px;
        }
        
        .flash-error {
            background: rgba(239, 68, 68, 0.1);
            color: var(--error-500);
            padding: 12px;
            border-radius: 8px;
            border: 1px solid rgba(239, 68, 68, 0.2);
            font-size: 14px;
        }
        
        .demo-info {
            margin-top: 24px;
            padding: 16px;
            background: var(--primary-50);
            border-radius: 12px;
            border: 1px solid var(--primary-200);
        }
        
        .demo-info h3 {
            font-size: 14px;
            font-weight: 600;
            color: var(--primary-800);
            margin-bottom: 8px;
        }
        
        .demo-info p {
            font-size: 13px;
            color: var(--primary-600);
            margin-bottom: 4px;
        }
    </style>
</head>
<body>
    <div class="login-container">
        <div class="login-header">
            <h1>🍽️ Lunch Auction</h1>
            <p>Sign in to place your bid</p>
        </div>
        
        {% with messages = get_flashed_messages() %}
            {% if messages %}
                <div class="flash-messages">
                    {% for message in messages %}
                        <div class="flash-error">{{ message }}</div>
                    {% endfor %}
                </div>
            {% endif %}
        {% endwith %}
        
        <form method="POST" class="login-form">
            <div class="form-group">
                <label for="username">Username</label>
                <input type="text" id="username" name="username" required>
            </div>
            
            <div class="form-group">
                <label for="password">Password</label>
                <input type="password" id="password" name="password" required>
            </div>
            
            <button type="submit" class="btn">Sign In</button>
        </form>
        
    </div>
</body>
</html>
"""

"""
        <div class="demo-info">
            <h3>Demo Accounts</h3>
            <p>👤 Alice / alice123</p>
            <p>👤 Bob / bob123</p>
            <p>👤 Charlie / charlie123</p>
            <p>👤 Diana / diana123</p>
            <p>🔑 Admin / admin123</p>
        </div>
"""

USER_DASHBOARD_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🍽️ Team Lunch Auction</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        :root {
            --primary-50: #f8fafc;
            --primary-100: #f1f5f9;
            --primary-200: #e2e8f0;
            --primary-300: #cbd5e1;
            --primary-400: #94a3b8;
            --primary-500: #64748b;
            --primary-600: #475569;
            --primary-700: #334155;
            --primary-800: #1e293b;
            --primary-900: #0f172a;
            --accent-500: #3b82f6;
            --success-500: #22c55e;
            --error-500: #ef4444;
        }
        
        body {
            font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: linear-gradient(to bottom right, var(--primary-50), var(--primary-100));
            min-height: 100vh;
            color: var(--primary-800);
            line-height: 1.7;
        }
        
        .container {
            max-width: 800px;
            margin: 0 auto;
            padding: 32px 24px;
        }
        
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 32px;
            padding-bottom: 24px;
            border-bottom: 1px solid var(--primary-200);
        }
        
        .header h1 {
            font-size: 2rem;
            font-weight: 600;
            color: var(--primary-900);
        }
        
        .nav-links {
            display: flex;
            gap: 12px;
        }
        
        .nav-links a {
            background: var(--primary-200);
            color: var(--primary-700);
            padding: 8px 16px;
            border-radius: 8px;
            text-decoration: none;
            font-size: 14px;
            font-weight: 500;
            transition: all 0.2s ease;
        }
        
        .nav-links a:hover {
            background: var(--primary-300);
            color: var(--primary-800);
        }
        
        .card {
            background: white;
            border-radius: 20px;
            padding: 32px;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
            border: 1px solid var(--primary-200);
            margin-bottom: 24px;
        }
        
        .card h2 {
            font-size: 1.25rem;
            font-weight: 600;
            color: var(--primary-900);
            margin-bottom: 20px;
        }
        
        .bid-form {
            display: grid;
            gap: 20px;
        }
        
        select, input[type="number"] {
            padding: 12px 16px;
            border: 1.5px solid var(--primary-300);
            border-radius: 8px;
            font-size: 15px;
        }
        
        .btn {
            background: var(--primary-900);
            color: white;
            border: none;
            padding: 12px 20px;
            border-radius: 8px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s ease;
        }
        
        .btn:hover {
            background: var(--primary-800);
        }
        
        .points-badge {
            background: var(--primary-800);
            color: white;
            padding: 6px 14px;
            border-radius: 20px;
            font-weight: 600;
            font-size: 13px;
        }
        
        .status {
            text-align: center;
            padding: 24px;
            margin: 32px 0;
            border-radius: 16px;
            font-size: 16px;
            font-weight: 500;
        }
        
        .status.completed {
            background: var(--success-500);
            color: white;
        }
        
        .status.active {
            background: rgba(59, 130, 246, 0.1);
            color: var(--primary-800);
            border: 1px solid var(--accent-500);
        }
        
        .current-bid {
            background: var(--primary-50);
            padding: 20px;
            border-radius: 16px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border: 1px solid var(--primary-200);
            margin-bottom: 20px;
        }
        
        .current-bid .bid-details {
            text-align: right;
        }
        
        .current-bid .bid-amount {
            font-size: 18px;
            font-weight: 700;
            color: var(--primary-900);
        }
        
        .flash-messages {
            margin-bottom: 20px;
        }
        
        .flash-message {
            padding: 12px 16px;
            border-radius: 8px;
            margin-bottom: 8px;
        }
        
        .flash-success {
            background: rgba(34, 197, 94, 0.1);
            color: var(--success-500);
            border: 1px solid rgba(34, 197, 94, 0.2);
        }
        
        .flash-error {
            background: rgba(239, 68, 68, 0.1);
            color: var(--error-500);
            border: 1px solid rgba(239, 68, 68, 0.2);
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div>
                <h1>🍽️ Team Lunch Auction</h1>
                <div class="points-badge">{{ user.current_points }} points available</div>
            </div>
            <div class="nav-links">
                <a href="{{ url_for('logout') }}">Logout</a>
            </div>
        </div>
        
        {% with messages = get_flashed_messages() %}
            {% if messages %}
                <div class="flash-messages">
                    {% for message in messages %}
                        <div class="flash-message flash-success">{{ message }}</div>
                    {% endfor %}
                </div>
            {% endif %}
        {% endwith %}
        
        {% if auction.status == 'completed' %}
            <div class="status completed">
                🎉 Today's winner: <strong>{{ auction.winning_restaurant }}</strong>
            </div>
        {% else %}
            <div class="status active">
                🔥 Auction in progress
            </div>
            
            <div class="card">
                <h2>Place Your Bid</h2>
                {% if user_bid %}
                    <div class="current-bid">
                        <div>
                            <div style="font-weight: 600; font-size: 16px; color: var(--primary-900);">
                                {{ user_bid.restaurant }}
                            </div>
                            <div style="color: var(--primary-600); font-size: 14px;">Your current bid</div>
                        </div>
                        <div class="bid-details">
                            <div class="bid-amount">{{ user_bid.bid_amount }} pts</div>
                        </div>
                    </div>
                {% endif %}
                
                <form method="POST" action="/bid" class="bid-form">
                    <select name="restaurant" required>
                        <option value="">Select a restaurant</option>
                        {% for restaurant in restaurants %}
                        <option value="{{ restaurant[0] }}">{{ restaurant[0] }}</option>
                        {% endfor %}
                    </select>
                    <input type="number" name="bid_amount" placeholder="Bid amount" min="1" max="{{ user.current_points }}" required>
                    <button type="submit" class="btn">Place Bid 🚀</button>
                </form>
            </div>
        {% endif %}
    </div>
</body>
</html>
"""

IDEAS_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🍽️ Restaurant Management</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        :root {
            --primary-50: #f8fafc;
            --primary-100: #f1f5f9;
            --primary-200: #e2e8f0;
            --primary-300: #cbd5e1;
            --primary-400: #94a3b8;
            --primary-500: #64748b;
            --primary-600: #475569;
            --primary-700: #334155;
            --primary-800: #1e293b;
            --primary-900: #0f172a;
            --success-500: #22c55e;
            --success-600: #16a34a;
            --error-500: #ef4444;
            --warning-500: #f59e0b;
        }
        
        body {
            font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: linear-gradient(to bottom right, var(--primary-50), var(--primary-100));
            min-height: 100vh;
            color: var(--primary-800);
            line-height: 1.7;
            font-size: 15px;
        }
        
        .container {
            max-width: 800px;
            margin: 0 auto;
            padding: 32px 24px;
        }
        
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 32px;
            padding-bottom: 24px;
            border-bottom: 1px solid var(--primary-200);
        }
        
        .header h1 {
            font-size: 2rem;
            font-weight: 600;
            color: var(--primary-900);
        }
        
        .nav-links {
            display: flex;
            gap: 12px;
        }
        
        .nav-links a {
            background: var(--primary-200);
            color: var(--primary-700);
            padding: 8px 16px;
            border-radius: 8px;
            text-decoration: none;
            font-size: 14px;
            font-weight: 500;
            transition: all 0.2s ease;
        }
        
        .nav-links a:hover {
            background: var(--primary-300);
            color: var(--primary-800);
        }
        
        .card {
            background: white;
            border-radius: 20px;
            padding: 32px;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
            border: 1px solid var(--primary-200);
            margin-bottom: 24px;
        }
        
        .card h2 {
            font-size: 1.25rem;
            font-weight: 600;
            color: var(--primary-900);
            margin-bottom: 20px;
        }
        
        .add-form {
            display: flex;
            gap: 12px;
            margin-bottom: 24px;
        }
        
        .add-form input {
            flex: 1;
            padding: 12px 16px;
            border: 1.5px solid var(--primary-300);
            border-radius: 8px;
            font-size: 15px;
        }
        
        .btn {
            background: var(--primary-900);
            color: white;
            border: none;
            padding: 12px 20px;
            border-radius: 8px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s ease;
        }
        
        .btn:hover {
            background: var(--primary-800);
        }
        
        .btn-small {
            padding: 6px 12px;
            font-size: 12px;
            margin: 0 4px;
        }
        
        .btn-success {
            background: var(--success-500);
        }
        
        .btn-success:hover {
            background: var(--success-600);
        }
        
        .btn-warning {
            background: var(--warning-500);
        }
        
        .btn-danger {
            background: var(--error-500);
        }
        
        .restaurants-list {
            display: grid;
            gap: 12px;
        }
        
        .restaurant-item {
            background: var(--primary-50);
            padding: 16px;
            border-radius: 12px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border: 1px solid var(--primary-200);
        }
        
        .restaurant-item.inactive {
            opacity: 0.6;
            background: var(--primary-100);
        }
        
        .restaurant-name {
            font-weight: 500;
            color: var(--primary-900);
        }
        
        .restaurant-actions {
            display: flex;
            gap: 8px;
        }
        
        .flash-messages {
            margin-bottom: 20px;
        }
        
        .flash-message {
            padding: 12px 16px;
            border-radius: 8px;
            margin-bottom: 8px;
        }
        
        .flash-success {
            background: rgba(34, 197, 94, 0.1);
            color: var(--success-500);
            border: 1px solid rgba(34, 197, 94, 0.2);
        }
        
        .flash-error {
            background: rgba(239, 68, 68, 0.1);
            color: var(--error-500);
            border: 1px solid rgba(239, 68, 68, 0.2);
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🍽️ Restaurant Management</h1>
            <div class="nav-links">
                <a href="{{ url_for('admin') }}">← Back to Admin</a>
                <a href="{{ url_for('logout') }}">Logout</a>
            </div>
        </div>
        
        {% with messages = get_flashed_messages() %}
            {% if messages %}
                <div class="flash-messages">
                    {% for message in messages %}
                        <div class="flash-message flash-success">{{ message }}</div>
                    {% endfor %}
                </div>
            {% endif %}
        {% endwith %}
        
        <div class="card">
            <h2>Add New Restaurant</h2>
            <form method="POST" action="{{ url_for('add_restaurant') }}" class="add-form">
                <input type="text" name="name" placeholder="Restaurant name" required>
                <button type="submit" class="btn">Add Restaurant</button>
            </form>
        </div>
        
        <div class="card">
            <h2>Manage Restaurants ({{ restaurants|length }})</h2>
            <div class="restaurants-list">
                {% for restaurant in restaurants %}
                <div class="restaurant-item {% if not restaurant.is_active %}inactive{% endif %}">
                    <div class="restaurant-name">
                        {{ restaurant.name }}
                        {% if not restaurant.is_active %}<small>(Inactive)</small>{% endif %}
                    </div>
                    <div class="restaurant-actions">
                        <form method="POST" action="{{ url_for('toggle_idea', idea_id=restaurant.id) }}" style="display: inline;">
                            <button type="submit" class="btn btn-small {% if restaurant.is_active %}btn-warning{% else %}btn-success{% endif %}">
                                {% if restaurant.is_active %}Deactivate{% else %}Activate{% endif %}
                            </button>
                        </form>
                        <form method="POST" action="{{ url_for('delete_idea', idea_id=restaurant.id) }}" 
                              style="display: inline;" 
                              onsubmit="return confirm('Are you sure you want to delete {{ restaurant.name }}?')">
                            <button type="submit" class="btn btn-small btn-danger">Delete</button>
                        </form>
                    </div>
                </div>
                {% endfor %}
            </div>
        </div>
    </div>
</body>
</html>
"""

ADMIN_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🍽️ Team Lunch Auction</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        :root {
            --primary-50: #f8fafc;
            --primary-100: #f1f5f9;
            --primary-200: #e2e8f0;
            --primary-300: #cbd5e1;
            --primary-400: #94a3b8;
            --primary-500: #64748b;
            --primary-600: #475569;
            --primary-700: #334155;
            --primary-800: #1e293b;
            --primary-900: #0f172a;
            
            --accent-400: #60a5fa;
            --accent-500: #3b82f6;
            --accent-600: #2563eb;
            
            --success-400: #4ade80;
            --success-500: #22c55e;
            --success-600: #16a34a;
            
            --warning-400: #fbbf24;
            --warning-500: #f59e0b;
        }
        
        body {
            font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, "Noto Sans", sans-serif, "Apple Color Emoji", "Segoe UI Emoji", "Segoe UI Symbol", "Noto Color Emoji";
            background: linear-gradient(to bottom right, var(--primary-50), var(--primary-100));
            min-height: 100vh;
            color: var(--primary-800);
            line-height: 1.7;
            font-size: 15px;
            letter-spacing: -0.025em;
        }
        
        .container {
            max-width: 1280px;
            margin: 0 auto;
            padding: 32px 24px;
        }
        
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 56px;
            padding-bottom: 24px;
            border-bottom: 1px solid var(--primary-200);
        }
        
        .header > div:first-child {
            text-align: left;
        }
        
        .header h1 {
            font-size: 2.75rem;
            font-weight: 600;
            margin-bottom: 16px;
            color: var(--primary-900);
            letter-spacing: -0.05em;
        }
        
        .date-badge {
            background: var(--primary-800);
            color: white;
            padding: 10px 20px;
            border-radius: 24px;
            display: inline-block;
            font-weight: 500;
            font-size: 14px;
            letter-spacing: 0.025em;
        }
        
        .grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 32px;
            margin-bottom: 48px;
        }
        
        .card {
            background: white;
            border-radius: 20px;
            padding: 36px;
            box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px -1px rgba(0, 0, 0, 0.1);
            border: 1px solid var(--primary-200);
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        }
        
        .card:hover {
            box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -4px rgba(0, 0, 0, 0.1);
        }
        
        .card h2 {
            font-size: 1.375rem;
            margin-bottom: 24px;
            color: var(--primary-900);
            font-weight: 600;
            letter-spacing: -0.025em;
        }
        
        .bid-form {
            display: grid;
            gap: 20px;
        }
        
        select, input[type="text"], input[type="number"] {
            padding: 14px 16px;
            border: 1.5px solid var(--primary-300);
            border-radius: 12px;
            font-size: 15px;
            transition: all 0.2s ease;
            background: white;
            color: var(--primary-800);
            font-family: inherit;
        }
        
        select:focus, input:focus {
            outline: none;
            border-color: var(--accent-500);
            box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.08);
        }
        
        .btn {
            background: var(--primary-900);
            color: white;
            border: none;
            padding: 16px 24px;
            border-radius: 12px;
            font-size: 15px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s ease;
            font-family: inherit;
            letter-spacing: -0.025em;
        }
        
        .btn:hover {
            background: var(--primary-800);
            transform: translateY(-1px);
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -2px rgba(0, 0, 0, 0.1);
        }
        
        .btn:active {
            transform: translateY(0);
        }
        
        .user-points {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 16px;
            margin-bottom: 20px;
        }
        
        .user-card {
            background: var(--primary-50);
            padding: 18px 20px;
            border-radius: 16px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border: 1px solid var(--primary-200);
            transition: all 0.2s ease;
        }
        
        .user-card:hover {
            background: var(--primary-100);
            border-color: var(--primary-300);
        }
        
        .user-card span:first-child {
            font-weight: 500;
            color: var(--primary-800);
        }
        
        .points-badge {
            background: var(--primary-800);
            color: white;
            padding: 6px 14px;
            border-radius: 20px;
            font-weight: 600;
            font-size: 13px;
            letter-spacing: 0.025em;
        }
        
        .bids-list {
            display: grid;
            gap: 12px;
        }
        
        .bid-item {
            background: var(--primary-50);
            padding: 20px;
            border-radius: 16px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border: 1px solid var(--primary-200);
            transition: all 0.2s ease;
        }
        
        .bid-item:hover {
            background: var(--primary-100);
            border-color: var(--primary-300);
        }
        
        .bid-item.winner {
            background: var(--success-500);
            color: white;
            border-color: var(--success-600);
        }
        
        .bid-item.winner:hover {
            background: var(--success-600);
        }
        
        .bid-restaurant {
            font-weight: 600;
            font-size: 16px;
            color: var(--primary-900);
            margin-bottom: 2px;
        }
        
        .bid-item.winner .bid-restaurant {
            color: white;
        }
        
        .bid-user {
            color: var(--primary-600);
            font-size: 14px;
        }
        
        .bid-item.winner .bid-user {
            color: rgba(255, 255, 255, 0.9);
        }
        
        .bid-details {
            text-align: right;
        }
        
        .bid-amount {
            font-size: 18px;
            font-weight: 700;
            color: var(--primary-900);
            margin-bottom: 2px;
        }
        
        .bid-item.winner .bid-amount {
            color: white;
        }
        
        .status {
            text-align: center;
            padding: 24px;
            margin: 32px 0;
            border-radius: 16px;
            font-size: 16px;
            font-weight: 500;
            letter-spacing: -0.025em;
        }
        
        .status.completed {
            background: var(--success-500);
            color: white;
            border: 1px solid var(--success-600);
        }
        
        .status.active {
            background: rgba(251, 191, 36, 0.1);
            color: var(--primary-800);
            border: 1px solid var(--warning-400);
        }
        
        .winners-history {
            margin-top: 48px;
        }
        
        .winner-item {
            background: white;
            padding: 20px;
            border-radius: 16px;
            margin-bottom: 12px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border: 1px solid var(--primary-200);
            transition: all 0.2s ease;
        }
        
        .winner-item:hover {
            background: var(--primary-50);
            border-color: var(--primary-300);
        }
        
        .winner-item strong {
            color: var(--primary-900);
            font-weight: 600;
        }
        
        .winner-item div:first-child {
            color: var(--primary-700);
        }
        
        .winner-item div:last-child {
            color: var(--primary-600);
            font-weight: 500;
        }
        
        .admin-bid-form {
            margin-top: 32px;
            padding-top: 32px;
            border-top: 1px solid var(--primary-200);
        }
        
        .admin-bid-form h3 {
            font-size: 1.25rem;
            margin-bottom: 20px;
            color: var(--primary-900);
            font-weight: 600;
        }
        
        .form-grid {
            display: grid;
            grid-template-columns: 1fr 1fr 1fr auto;
            gap: 16px;
            align-items: end;
        }
        
        .form-group {
            display: grid;
            gap: 8px;
        }
        
        .form-group label {
            font-size: 14px;
            font-weight: 500;
            color: var(--primary-700);
        }
        
        @media (max-width: 768px) {
            .container { padding: 24px 16px; }
            .grid { grid-template-columns: 1fr; gap: 24px; }
            .user-points { grid-template-columns: 1fr; }
            .header h1 { font-size: 2.25rem; }
            .card { padding: 24px; }
        }
        
        @media (max-width: 480px) {
            .header h1 { font-size: 2rem; }
            .card { padding: 20px; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div>
                <h1>🍽️ Team Lunch Auction - Admin</h1>
                <div class="date-badge">{{ today }}</div>
            </div>
            <div style="display: flex; gap: 12px;">
                <a href="{{ url_for('manage_ideas') }}" style="background: var(--primary-200); color: var(--primary-700); padding: 8px 16px; border-radius: 8px; text-decoration: none; font-size: 14px; font-weight: 500;">Manage Ideas</a>
                <a href="{{ url_for('logout') }}" style="background: var(--primary-200); color: var(--primary-700); padding: 8px 16px; border-radius: 8px; text-decoration: none; font-size: 14px; font-weight: 500;">Logout</a>
            </div>
        </div>
        
        {% if auction.status == 'completed' %}
            <div class="status completed">
                🎉 Today's winner: <strong>{{ auction.winning_restaurant }}</strong> 
                ({{ bids[0].name }} - {{ auction.winning_bid }} points)
            </div>
        {% else %}
            <div class="status active">
                🔥 Auction in progress - {{ bids|length }}/{{ users|length }} bids placed
            </div>
        {% endif %}
        
        <div class="grid">
            <div class="card">
                <h2>💰 Team Points</h2>
                <div class="user-points">
                    {% for user in users %}
                    <div class="user-card">
                        <span>{{ user.name }}</span>
                        <span class="points-badge">{{ user.current_points }} pts</span>
                    </div>
                    {% endfor %}
                </div>
                
                <div class="admin-bid-form">
                    <h3>🎯 Place Bid for User</h3>
                    {% if auction.status != 'completed' %}
                    <form method="POST" action="/admin/bid" class="form-grid">
                        <div class="form-group">
                            <label for="user_id">Select User</label>
                            <select name="user_id" id="user_id" required>
                                <option value="">Choose user...</option>
                                {% for user in users %}
                                <option value="{{ user.id }}">{{ user.name }}</option>
                                {% endfor %}
                            </select>
                        </div>
                        <div class="form-group">
                            <label for="restaurant">Restaurant Choice</label>
                            <select name="restaurant" id="restaurant" required>
                                <option value="">Choose restaurant...</option>
                                {% for r in restaurants %}
                                <option value="{{ r.name }}">{{ r.name }}</option>
                                {% endfor %}
                            </select>
                        </div>
                        <div class="form-group">
                            <label for="bid_amount">Bid Amount</label>
                            <input type="number" name="bid_amount" id="bid_amount" required min="1" step="1">
                        </div>
                        <button type="submit" class="btn">Place Bid</button>
                    </form>
                    {% else %}
                    <p>Today's auction is complete.</p>
                    {% endif %}
                </div>
            </div>
            
            <div class="card">
                <h2>📊 Today's Bids</h2>
                <div class="bids-list">
                    {% for bid in bids %}
                    <div class="bid-item {% if loop.first and auction.status == 'completed' %}winner{% endif %}">
                        <div>
                            <div class="bid-restaurant">{{ bid.restaurant }}</div>
                            <div class="bid-user">{{ bid.name }}</div>
                        </div>
                        <div class="bid-details">
                            <div class="bid-amount">{{ bid.bid_amount }} pts</div>
                            {% if loop.first and auction.status == 'completed' %}
                            <div style="font-size: 14px; font-weight: 500;">👑 Winner!</div>
                            {% endif %}
                        </div>
                    </div>
                    {% endfor %}
                </div>
            </div>
        </div>
        
        {% if recent_winners %}
        <div class="winners-history">
            <div class="card">
                <h2>🏆 Recent Winners</h2>
                {% for winner in recent_winners %}
                <div class="winner-item">
                    <div>
                        <strong>{{ winner.date }}</strong> - {{ winner.winning_restaurant }}
                    </div>
                    <div>
                        {{ winner.name }} ({{ winner.winning_bid }} pts)
                    </div>
                </div>
                {% endfor %}
            </div>
        </div>
        {% endif %}
    </div>
</body>
</html>
"""

if __name__ == "__main__":
    # Check for database in data directory or current directory
    db_path = (
        os.path.join("data", "lunch_auction.db")
        if os.path.exists("data")
        else "lunch_auction.db"
    )

    if not os.path.exists(db_path):
        print("Database not found. Running setup...")
        from setup import setup_database

        setup_database()
        print("Database initialized successfully!")

    app.run(debug=True, host="0.0.0.0", port=5000)
