from app import app, db, User, UserRole
from werkzeug.security import generate_password_hash


def init_database():
    with app.app_context():
        # Create all tables
        db.create_all()

        # Check if admin already exists
        if not User.query.filter_by(username="admin").first():
            # Create admin user
            admin = User(
                username="admin",
                email="admin@example.com",
                password_hash=generate_password_hash("adminpass"),
                first_name="Admin",
                last_name="User",
                role=UserRole.ADMIN,
                is_active=True,
            )

            # Add to database
            db.session.add(admin)
            db.session.commit()
            print("Admin user created successfully!")
            print("Username: admin")
            print("Password: adminpass")
        else:
            print("Admin user already exists")
