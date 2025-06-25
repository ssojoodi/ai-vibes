import sqlite3
from datetime import datetime


def setup_database():
    # Use data directory for database persistence in Docker
    import os

    db_path = (
        os.path.join("data", "lunch_auction.db")
        if os.path.exists("data")
        else "lunch_auction.db"
    )
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Check if users table exists and get its schema
    cursor.execute("PRAGMA table_info(users)")
    columns = [row[1] for row in cursor.fetchall()]

    # Create users table if it doesn't exist
    if not columns:
        cursor.execute("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                current_points INTEGER DEFAULT 15,
                is_admin BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    else:
        # Add missing columns if they don't exist
        if "password" not in columns:
            cursor.execute(
                "ALTER TABLE users ADD COLUMN password TEXT DEFAULT 'temp123'"
            )
        if "is_admin" not in columns:
            cursor.execute(
                "ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT FALSE"
            )

    # Create auctions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS auctions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date DATE UNIQUE NOT NULL,
            winner_id INTEGER,
            winning_restaurant TEXT,
            winning_bid INTEGER,
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (winner_id) REFERENCES users (id)
        )
    """)

    # Create restaurants table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ideas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Create bids table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bids (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            auction_id INTEGER,
            user_id INTEGER,
            restaurant TEXT NOT NULL,
            bid_amount INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (auction_id) REFERENCES auctions (id),
            FOREIGN KEY (user_id) REFERENCES users (id),
            UNIQUE(auction_id, user_id)
        )
    """)

    # Insert sample users with passwords (you can modify these)
    sample_users = [
        ("Alice", "alice123", False),
        ("Bob", "bob123", False),
        ("Charlie", "charlie123", False),
        ("Diana", "diana123", False),
        ("Admin", "admin123", True),
    ]

    for name, password, is_admin in sample_users:
        # Check if user exists
        existing_user = cursor.execute(
            "SELECT id FROM users WHERE name = ?", (name,)
        ).fetchone()
        if existing_user:
            # Update existing user with password and admin status
            cursor.execute(
                "UPDATE users SET password = ?, is_admin = ? WHERE name = ?",
                (password, is_admin, name),
            )
        else:
            # Insert new user
            cursor.execute(
                "INSERT INTO users (name, password, is_admin) VALUES (?, ?, ?)",
                (name, password, is_admin),
            )

    # Insert sample restaurants
    sample_restaurants = [
        "Pizza Palace",
        "Burger Bar",
        "Sushi Express",
        "Thai Garden",
        "Mexican Cantina",
        "Italian Bistro",
        "Indian Spice",
        "Chinese Dragon",
        "Mediterranean Grill",
        "American Diner",
    ]

    for restaurant_name in sample_restaurants:
        # Check if restaurant exists
        existing_restaurant = cursor.execute(
            "SELECT id FROM ideas WHERE name = ?", (restaurant_name,)
        ).fetchone()
        if not existing_restaurant:
            # Insert new restaurant
            cursor.execute("INSERT INTO ideas (name) VALUES (?)", (restaurant_name,))

    conn.commit()
    conn.close()
    print("Database setup complete!")


if __name__ == "__main__":
    setup_database()
