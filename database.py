import sqlite3
from decimal import Decimal

from config import DATABASE_PATH


def get_connection():
    """
    Create and return a SQLite database connection.
    """

    connection = sqlite3.connect(
        str(DATABASE_PATH),
        timeout=10
    )

    connection.row_factory = sqlite3.Row

    # Enable foreign key validation.
    connection.execute("PRAGMA foreign_keys = ON")

    # Wait briefly if another operation is using the database.
    connection.execute("PRAGMA busy_timeout = 10000")

    return connection


def initialize_database():
    """
    Create the database tables and insert initial sample data.

    Existing records are preserved.
    """

    connection = get_connection()

    try:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );


            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                full_name TEXT NOT NULL,
                role TEXT NOT NULL
                    CHECK(role IN ('admin', 'cashier')),
                is_active INTEGER NOT NULL DEFAULT 1
                    CHECK(is_active IN (0, 1)),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );


            CREATE TABLE IF NOT EXISTS customers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                phone TEXT UNIQUE,
                email TEXT,
                address TEXT DEFAULT '',
                loyalty_points INTEGER NOT NULL DEFAULT 0
                    CHECK(loyalty_points >= 0),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );


            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL COLLATE NOCASE,
                barcode TEXT UNIQUE,
                category_id INTEGER,
                unit TEXT NOT NULL DEFAULT 'piece',
                purchase_price TEXT NOT NULL DEFAULT '0.00',
                selling_price TEXT NOT NULL,
                stock TEXT NOT NULL DEFAULT '0',
                reorder_level TEXT NOT NULL DEFAULT '10',
                tax_rate TEXT NOT NULL DEFAULT '0',
                expiry_date TEXT,
                is_active INTEGER NOT NULL DEFAULT 1
                    CHECK(is_active IN (0, 1)),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY (category_id)
                    REFERENCES categories(id)
                    ON DELETE RESTRICT
            );


            CREATE TABLE IF NOT EXISTS sales (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_number TEXT NOT NULL UNIQUE,
                customer_id INTEGER,
                cashier_id INTEGER,
                subtotal TEXT NOT NULL,
                discount_amount TEXT NOT NULL DEFAULT '0.00',
                taxable_value TEXT NOT NULL DEFAULT '0.00',
                cgst_amount TEXT NOT NULL DEFAULT '0.00',
                sgst_amount TEXT NOT NULL DEFAULT '0.00',
                igst_amount TEXT NOT NULL DEFAULT '0.00',
                tax_amount TEXT NOT NULL DEFAULT '0.00',
                total_amount TEXT NOT NULL,
                amount_paid TEXT NOT NULL DEFAULT '0.00',
                balance_due TEXT NOT NULL DEFAULT '0.00',
                status TEXT NOT NULL DEFAULT 'completed'
                    CHECK(status IN (
                        'completed',
                        'cancelled',
                        'partially_returned',
                        'returned'
                    )),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY (customer_id)
                    REFERENCES customers(id)
                    ON DELETE RESTRICT,

                FOREIGN KEY (cashier_id)
                    REFERENCES users(id)
                    ON DELETE RESTRICT
            );


            CREATE TABLE IF NOT EXISTS sale_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sale_id INTEGER NOT NULL,
                product_id INTEGER,
                product_name TEXT NOT NULL,
                quantity TEXT NOT NULL,
                unit TEXT NOT NULL,
                unit_price TEXT NOT NULL,
                discount_amount TEXT NOT NULL DEFAULT '0.00',
                taxable_value TEXT NOT NULL DEFAULT '0.00',
                tax_rate TEXT NOT NULL DEFAULT '0',
                tax_amount TEXT NOT NULL DEFAULT '0.00',
                line_total TEXT NOT NULL,
                returned_quantity TEXT NOT NULL DEFAULT '0',

                FOREIGN KEY (sale_id)
                    REFERENCES sales(id)
                    ON DELETE RESTRICT,

                FOREIGN KEY (product_id)
                    REFERENCES products(id)
                    ON DELETE RESTRICT
            );


            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sale_id INTEGER NOT NULL,
                payment_method TEXT NOT NULL,
                amount TEXT NOT NULL,
                reference_number TEXT,
                status TEXT NOT NULL DEFAULT 'recorded'
                    CHECK(status IN (
                        'recorded',
                        'refunded',
                        'cancelled'
                    )),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY (sale_id)
                    REFERENCES sales(id)
                    ON DELETE RESTRICT
            );


            CREATE TABLE IF NOT EXISTS returns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                return_number TEXT NOT NULL UNIQUE,
                sale_id INTEGER NOT NULL,
                refund_amount TEXT NOT NULL,
                reason TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'completed'
                    CHECK(status IN ('completed', 'cancelled')),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY (sale_id)
                    REFERENCES sales(id)
                    ON DELETE RESTRICT
            );


            CREATE TABLE IF NOT EXISTS return_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                return_id INTEGER NOT NULL,
                sale_item_id INTEGER NOT NULL,
                quantity TEXT NOT NULL,
                refund_amount TEXT NOT NULL,
                restock INTEGER NOT NULL DEFAULT 1
                    CHECK(restock IN (0, 1)),

                FOREIGN KEY (return_id)
                    REFERENCES returns(id)
                    ON DELETE RESTRICT,

                FOREIGN KEY (sale_item_id)
                    REFERENCES sale_items(id)
                    ON DELETE RESTRICT
            );


            CREATE TABLE IF NOT EXISTS stock_movements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL,
                movement_type TEXT NOT NULL,
                quantity_change TEXT NOT NULL,
                previous_stock TEXT NOT NULL,
                new_stock TEXT NOT NULL,
                reference_type TEXT DEFAULT '',
                reference_id INTEGER,
                notes TEXT DEFAULT '',
                user_id INTEGER,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY (product_id)
                    REFERENCES products(id)
                    ON DELETE RESTRICT,

                FOREIGN KEY (user_id)
                    REFERENCES users(id)
                    ON DELETE RESTRICT
            );


            CREATE TABLE IF NOT EXISTS saved_bills (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                draft_number TEXT NOT NULL UNIQUE,
                customer_id INTEGER,
                cart_json TEXT NOT NULL,
                discount_percent TEXT NOT NULL DEFAULT '0',
                budget_limit TEXT,
                notes TEXT DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY (customer_id)
                    REFERENCES customers(id)
                    ON DELETE RESTRICT
            );


            CREATE TABLE IF NOT EXISTS application_settings (
                setting_key TEXT PRIMARY KEY,
                setting_value TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );


            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                action TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                entity_id INTEGER,
                details TEXT DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY (user_id)
                    REFERENCES users(id)
                    ON DELETE RESTRICT
            );


            CREATE INDEX IF NOT EXISTS idx_products_name
                ON products(name);

            CREATE INDEX IF NOT EXISTS idx_products_category
                ON products(category_id);

            CREATE INDEX IF NOT EXISTS idx_sales_created_at
                ON sales(created_at);

            CREATE INDEX IF NOT EXISTS idx_sale_items_sale
                ON sale_items(sale_id);

            CREATE INDEX IF NOT EXISTS idx_payments_sale
                ON payments(sale_id);

            CREATE INDEX IF NOT EXISTS idx_stock_movements_product
                ON stock_movements(product_id);

            CREATE INDEX IF NOT EXISTS idx_returns_sale
                ON returns(sale_id);

            CREATE INDEX IF NOT EXISTS idx_audit_logs_created
                ON audit_logs(created_at);
            """
        )

        seed_categories(connection)
        seed_products(connection)
        seed_settings(connection)

        connection.commit()

        print("SmartCart AI database initialized successfully.")

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def seed_categories(connection):
    """
    Add sample categories only when they do not already exist.
    """

    categories = [
        ("Groceries", "Rice, grains, and daily essentials"),
        ("Dairy", "Milk and dairy products"),
        ("Fruits", "Fresh fruits"),
        ("Personal Care", "Soap and personal hygiene products"),
        ("Beverages", "Drinks and beverages"),
    ]

    connection.executemany(
        """
        INSERT OR IGNORE INTO categories (name, description)
        VALUES (?, ?)
        """,
        categories
    )


def seed_products(connection):
    """
    Insert sample products only if the products table is empty.
    """

    product_count = connection.execute(
        "SELECT COUNT(*) FROM products"
    ).fetchone()[0]

    if product_count > 0:
        return

    category_rows = connection.execute(
        "SELECT id, name FROM categories"
    ).fetchall()

    category_ids = {
        row["name"]: row["id"]
        for row in category_rows
    }

    products = [
        (
            "Rice",
            "8901000000001",
            "Groceries",
            "kg",
            "45.00",
            "60.00",
            "100",
            "15",
            "0",
            None,
        ),
        (
            "Milk",
            "8901000000002",
            "Dairy",
            "packet",
            "22.00",
            "30.00",
            "50",
            "10",
            "0",
            None,
        ),
        (
            "Apple",
            "8901000000003",
            "Fruits",
            "piece",
            "7.00",
            "10.00",
            "80",
            "15",
            "0",
            None,
        ),
        (
            "Soap",
            "8901000000004",
            "Personal Care",
            "piece",
            "18.00",
            "25.00",
            "40",
            "10",
            "0",
            None,
        ),
        (
            "Biscuit",
            "8901000000005",
            "Groceries",
            "packet",
            "8.00",
            "10.00",
            "100",
            "20",
            "0",
            None,
        ),
        (
            "Tea",
            "8901000000006",
            "Beverages",
            "kg",
            "180.00",
            "220.00",
            "25",
            "5",
            "0",
            None,
        ),
    ]

    for product in products:
        (
            name,
            barcode,
            category,
            unit,
            purchase_price,
            selling_price,
            stock,
            reorder_level,
            tax_rate,
            expiry_date,
        ) = product

        connection.execute(
            """
            INSERT OR IGNORE INTO products (
                name,
                barcode,
                category_id,
                unit,
                purchase_price,
                selling_price,
                stock,
                reorder_level,
                tax_rate,
                expiry_date
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                name,
                barcode,
                category_ids[category],
                unit,
                purchase_price,
                selling_price,
                stock,
                reorder_level,
                tax_rate,
                expiry_date,
            )
        )


def seed_settings(connection):
    """
    Insert default application settings without replacing
    existing settings.
    """

    settings = [
        ("shop_name", "SmartCart Supermarket"),
        ("shop_address", "Tamil Nadu, India"),
        ("currency", "INR"),
        ("invoice_prefix", "SC"),
        ("return_policy", "Please retain your invoice for returns."),
        ("default_low_stock_level", "10"),
        ("tax_mode", "exclusive"),
        ("default_budget_limit", "1000"),
    ]

    connection.executemany(
        """
        INSERT OR IGNORE INTO application_settings (
            setting_key,
            setting_value
        )
        VALUES (?, ?)
        """,
        settings
    )


def get_products():
    """
    Return all active products with their category names.
    """

    connection = get_connection()

    try:
        products = connection.execute(
            """
            SELECT
                products.*,
                categories.name AS category_name
            FROM products
            LEFT JOIN categories
                ON products.category_id = categories.id
            WHERE products.is_active = 1
            ORDER BY products.name
            """
        ).fetchall()

        return [dict(product) for product in products]

    finally:
        connection.close()


def get_product_by_barcode(barcode):
    """
    Find an active product using its barcode.
    """

    connection = get_connection()

    try:
        product = connection.execute(
            """
            SELECT *
            FROM products
            WHERE barcode = ?
              AND is_active = 1
            """,
            (barcode,)
        ).fetchone()

        return dict(product) if product else None

    finally:
        connection.close()


def get_setting(setting_key, default=None):
    """
    Read a setting from the database.
    """

    connection = get_connection()

    try:
        result = connection.execute(
            """
            SELECT setting_value
            FROM application_settings
            WHERE setting_key = ?
            """,
            (setting_key,)
        ).fetchone()

        return result["setting_value"] if result else default

    finally:
        connection.close()


if __name__ == "__main__":
    initialize_database()

    print("\nSample products:")

    for product in get_products():
        print(
            f"{product['name']} | "
            f"Price: ₹{product['selling_price']} | "
            f"Stock: {product['stock']} {product['unit']}"
        )
# ==========================================
# SUPPLIER AND PURCHASE MANAGEMENT TABLES
# ==========================================

def initialize_shop_management_tables():
    connection = get_connection()

    try:
        connection.executescript("""
            CREATE TABLE IF NOT EXISTS suppliers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                phone TEXT,
                email TEXT,
                address TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS purchases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_number TEXT NOT NULL UNIQUE,
                supplier_id INTEGER NOT NULL,
                subtotal NUMERIC NOT NULL DEFAULT 0,
                amount_paid NUMERIC NOT NULL DEFAULT 0,
                balance_due NUMERIC NOT NULL DEFAULT 0,
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
            );

            CREATE TABLE IF NOT EXISTS purchase_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                purchase_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                product_name TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                unit TEXT,
                unit_cost NUMERIC NOT NULL,
                line_total NUMERIC NOT NULL,
                FOREIGN KEY (purchase_id) REFERENCES purchases(id),
                FOREIGN KEY (product_id) REFERENCES products(id)
            );
        """)

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()