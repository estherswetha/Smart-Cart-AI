from database import get_connection

connection = get_connection()

try:
    for table_name in ("sales", "products", "sale_items"):
        print(f"\n--- {table_name.upper()} ---")

        columns = connection.execute(
            f"PRAGMA table_info({table_name})"
        ).fetchall()

        if columns:
            for column in columns:
                print(column["name"])
        else:
            print("Table not found or has no columns.")

finally:
    connection.close()
