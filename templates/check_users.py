from database import get_connection

connection = get_connection()

try:
    columns = connection.execute(
        "PRAGMA table_info(users)"
    ).fetchall()

    print("\nSMARTCART AI - USERS TABLE")
    print("-" * 35)

    if columns:
        for column in columns:
            print(f"Column: {column['name']}")
    else:
        print("The users table does not exist.")

    print("\nExisting users:")

    if columns:
        users = connection.execute(
            "SELECT * FROM users"
        ).fetchall()

        if users:
            for user in users:
                print(dict(user))
        else:
            print("No users found.")

finally:
    connection.close()