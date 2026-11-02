import sqlite3
from pathlib import Path

database_path = Path("instance") / "smartcart.db"

if not database_path.exists():
    print("Database not found!")
    print("Please initialize the database first.")
else:
    connection = sqlite3.connect(database_path)

    query = """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
        ORDER BY name;
    """

    tables = connection.execute(query).fetchall()

    print("\nSMARTCART AI DATABASE CHECK")
    print("-" * 35)

    if tables:
        for table in tables:
            print(table[0])
        print("\nDatabase check completed!")
    else:
        print("No tables found. Database initialization is required.")

    connection.close()