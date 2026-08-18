from app import app, db, User, UserRole

def check_admin():
    with app.app_context():
        admin = User.query.filter_by(username="admin").first()
        if admin:
            print(f"Admin user exists:")
            print(f"Username: {admin.username}")
            print(f"Role: {admin.role}")
            print(f"Is Active: {admin.is_active}")
            print(f"Role comparison: {admin.role == UserRole.ADMIN}")
        else:
            print("Admin user does not exist!")

if __name__ == "__main__":
    check_admin()
