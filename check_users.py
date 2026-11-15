from database import get_connection

connection = get_connection()

try:
    columns = connection.execute("PRAGMA table_info(users)").fetchall()

    print("\n=== USERS TABLE COLUMNS ===")

    if not columns:
        print("The users table does not exist.")
    else:
        for column in columns:
            print(column["name"])

        print("\n=== EXISTING USERNAMES AND ROLES ===")

        users = connection.execute(
            "SELECT * FROM users"
        ).fetchall()

        if not users:
            print("No users found.")
        else:
            for user in users:
                print({
                    key: user[key]
                    for key in ("id", "username", "role")
                    if key in user.keys()
                })

finally:
    connection.close()
