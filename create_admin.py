from getpass import getpass
from werkzeug.security import generate_password_hash
from database import get_connection


def create_admin():
    print("\n=== SMARTCART AI - CREATE ADMIN ===")

    username = input("Enter admin username: ").strip()
    full_name = input("Enter admin full name: ").strip()

    if not username or not full_name:
        print("Username and full name are required.")
        return

    password = getpass("Create admin password: ")
    confirm_password = getpass("Confirm admin password: ")

    if password != confirm_password:
        print("Passwords do not match.")
        return

    if len(password) < 12:
        print("Password must contain at least 12 characters.")
        return

    connection = get_connection()

    try:
        existing = connection.execute(
            "SELECT id FROM users WHERE username = ?",
            (username,)
        ).fetchone()

        if existing:
            print("This username already exists.")
            return

        password_hash = generate_password_hash(password)

        connection.execute(
            """
            INSERT INTO users
            (username, password_hash, full_name, role, is_active)
            VALUES (?, ?, ?, 'admin', 1)
            """,
            (username, password_hash, full_name)
        )

        connection.commit()

        print("\nAdministrator created successfully!")
        print("Username:", username)
        print("Role: admin")

    except Exception as error:
        connection.rollback()
        print("Error:", error)

    finally:
        connection.close()


if __name__ == "__main__":
    create_admin()
