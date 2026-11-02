from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    jsonify,
    flash,
)
from database import (
    initialize_database,
    initialize_shop_management_tables,
    get_connection,
)
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from datetime import datetime
import sqlite3


# =========================================================
# APPLICATION CONFIGURATION
# =========================================================

app = Flask(__name__)

app.secret_key = "smartcart-local-dev-key-change-before-deployment"
app.config["MAX_CONTENT_LENGTH"] = 1 * 1024 * 1024


# =========================================================
# DATABASE INITIALIZATION
# =========================================================

initialize_database()
initialize_shop_management_tables()


# =========================================================
# HELPER FUNCTIONS
# =========================================================

def money(value):
    """Convert a value to a Decimal rounded to two decimal places."""
    try:
        return Decimal(str(value or 0)).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("0.00")


def parse_money(value, field_name="Amount"):
    """Validate a non-negative monetary value."""
    try:
        result = Decimal(str(value or "0").strip())

        if not result.is_finite() or result < 0:
            raise ValueError(f"{field_name} must be a non-negative number.")

        return result.quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )

    except (InvalidOperation, ValueError, TypeError) as exc:
        if isinstance(exc, ValueError) and str(exc).startswith(field_name):
            raise
        raise ValueError(f"Enter a valid value for {field_name}.")


def parse_integer(value, field_name, minimum=0):
    """Validate an integer field."""
    try:
        text = str(value).strip()

        if not text:
            raise ValueError

        number = int(text)

        if number < minimum:
            raise ValueError

        return number

    except (TypeError, ValueError):
        raise ValueError(
            f"{field_name} must be a whole number greater than "
            f"or equal to {minimum}."
        )


def validate_phone(phone):
    """Validate an optional phone number."""
    phone = (phone or "").strip()

    if not phone:
        return True

    digits = "".join(character for character in phone if character.isdigit())

    return 7 <= len(digits) <= 15


def json_error(message, status=400):
    """Return a consistent JSON error response."""
    return jsonify({
        "success": False,
        "error": message,
    }), status


def table_exists(connection, table_name):
    """Check whether a database table exists."""
    result = connection.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table' AND name = ?
        """,
        (table_name,),
    ).fetchone()

    return result is not None


def get_table_columns(connection, table_name):
    """Return the column names of an existing table."""
    if not table_exists(connection, table_name):
        return set()

    return {
        row["name"]
        for row in connection.execute(
            f'PRAGMA table_info("{table_name}")'
        ).fetchall()
    }


def get_existing_column(connection, table_name, candidates):
    """Return the first matching column name from a list."""
    columns = get_table_columns(connection, table_name)

    for candidate in candidates:
        if candidate in columns:
            return candidate

    return None


# =========================================================
# HOME / BILLING DASHBOARD
# =========================================================

@app.route("/")
def home():
    connection = get_connection()

    try:
        product_rows = connection.execute(
            """
            SELECT *
            FROM products
            WHERE is_active = 1
            ORDER BY name
            """
        ).fetchall()

        products = []

        for row in product_rows:
            product = dict(row)

            product["selling_price"] = float(
                product.get("selling_price") or 0
            )

            product["purchase_price"] = float(
                product.get("purchase_price") or 0
            )

            product["stock"] = int(product.get("stock") or 0)

            products.append(product)

        sales_columns = get_table_columns(connection, "sales")

        if "status" in sales_columns:
            sales_count = connection.execute(
                """
                SELECT COUNT(*) AS total
                FROM sales
                WHERE status = 'completed'
                """
            ).fetchone()["total"]

            sales_total = connection.execute(
                """
                SELECT COALESCE(SUM(total_amount), 0) AS total
                FROM sales
                WHERE status = 'completed'
                """
            ).fetchone()["total"]

        else:
            sales_count = connection.execute(
                "SELECT COUNT(*) AS total FROM sales"
            ).fetchone()["total"]

            sales_total = connection.execute(
                """
                SELECT COALESCE(SUM(total_amount), 0) AS total
                FROM sales
                """
            ).fetchone()["total"]

        return render_template(
            "index.html",
            products=products,
            sales_count=sales_count,
            sales_total=float(sales_total or 0),
        )

    finally:
        connection.close()


# =========================================================
# PRODUCT MANAGEMENT
# =========================================================

@app.route("/products", methods=["GET"])
def manage_products():
    connection = get_connection()

    try:
        products = connection.execute(
            """
            SELECT *
            FROM products
            WHERE is_active = 1
            ORDER BY name
            """
        ).fetchall()

        categories = connection.execute(
            """
            SELECT id, name
            FROM categories
            ORDER BY name
            """
        ).fetchall()

        return render_template(
            "products.html",
            products=products,
            categories=categories,
        )

    finally:
        connection.close()


# =========================================================
# ADD PRODUCT
# =========================================================

@app.route("/products/add", methods=["POST"])
def add_product():
    connection = get_connection()

    try:
        name = request.form.get("name", "").strip()
        barcode = request.form.get("barcode", "").strip() or None
        unit = request.form.get("unit", "pcs").strip() or "pcs"
        expiry_date = request.form.get("expiry_date", "").strip() or None

        if not name:
            raise ValueError("Product name is required.")

        purchase_price = parse_money(
            request.form.get("purchase_price"),
            "Purchase price",
        )

        selling_price = parse_money(
            request.form.get("selling_price"),
            "Selling price",
        )

        stock = parse_integer(
            request.form.get("stock", "0"),
            "Stock",
            minimum=0,
        )

        reorder_level = parse_integer(
            request.form.get("reorder_level", "5"),
            "Reorder level",
            minimum=0,
        )

        tax_rate = parse_money(
            request.form.get("tax_rate", "0"),
            "Tax rate",
        )

        category_value = request.form.get("category_id", "").strip()
        category_id = None

        if category_value:
            category_id = parse_integer(
                category_value,
                "Category",
                minimum=1,
            )

            category_exists = connection.execute(
                "SELECT id FROM categories WHERE id = ?",
                (category_id,),
            ).fetchone()

            if not category_exists:
                raise ValueError("Please select a valid category.")

        if barcode:
            duplicate = connection.execute(
                """
                SELECT id
                FROM products
                WHERE barcode = ? AND is_active = 1
                """,
                (barcode,),
            ).fetchone()

            if duplicate:
                raise ValueError("This barcode already exists.")

        connection.execute(
            """
            INSERT INTO products (
                name,
                barcode,
                category_id,
                unit,
                purchase_price,
                selling_price,
                stock,
                reorder_level,
                tax_rate,
                expiry_date,
                is_active
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            """,
            (
                name,
                barcode,
                category_id,
                unit,
                str(purchase_price),
                str(selling_price),
                stock,
                reorder_level,
                str(tax_rate),
                expiry_date,
            ),
        )

        connection.commit()
        flash(f"{name} added successfully.", "success")

    except (ValueError, sqlite3.Error) as exc:
        connection.rollback()
        flash(f"Could not add product: {exc}", "error")

    finally:
        connection.close()

    return redirect(url_for("manage_products"))


# =========================================================
# EDIT PRODUCT
# =========================================================

@app.route("/products/edit/<int:product_id>", methods=["POST"])
def edit_product(product_id):
    connection = get_connection()

    try:
        product = connection.execute(
            """
            SELECT id
            FROM products
            WHERE id = ? AND is_active = 1
            """,
            (product_id,),
        ).fetchone()

        if not product:
            raise ValueError("Product not found.")

        name = request.form.get("name", "").strip()
        barcode = request.form.get("barcode", "").strip() or None
        unit = request.form.get("unit", "pcs").strip() or "pcs"
        expiry_date = request.form.get("expiry_date", "").strip() or None

        if not name:
            raise ValueError("Product name is required.")

        purchase_price = parse_money(
            request.form.get("purchase_price"),
            "Purchase price",
        )

        selling_price = parse_money(
            request.form.get("selling_price"),
            "Selling price",
        )

        stock = parse_integer(
            request.form.get("stock", "0"),
            "Stock",
            minimum=0,
        )

        reorder_level = parse_integer(
            request.form.get("reorder_level", "5"),
            "Reorder level",
            minimum=0,
        )

        tax_rate = parse_money(
            request.form.get("tax_rate", "0"),
            "Tax rate",
        )

        category_value = request.form.get("category_id", "").strip()
        category_id = None

        if category_value:
            category_id = parse_integer(
                category_value,
                "Category",
                minimum=1,
            )

            category_exists = connection.execute(
                "SELECT id FROM categories WHERE id = ?",
                (category_id,),
            ).fetchone()

            if not category_exists:
                raise ValueError("Please select a valid category.")

        if barcode:
            duplicate = connection.execute(
                """
                SELECT id
                FROM products
                WHERE barcode = ?
                  AND id != ?
                  AND is_active = 1
                """,
                (barcode, product_id),
            ).fetchone()

            if duplicate:
                raise ValueError("This barcode is already used by another product.")

        connection.execute(
            """
            UPDATE products
            SET name = ?,
                barcode = ?,
                category_id = ?,
                unit = ?,
                purchase_price = ?,
                selling_price = ?,
                stock = ?,
                reorder_level = ?,
                tax_rate = ?,
                expiry_date = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND is_active = 1
            """,
            (
                name,
                barcode,
                category_id,
                unit,
                str(purchase_price),
                str(selling_price),
                stock,
                reorder_level,
                str(tax_rate),
                expiry_date,
                product_id,
            ),
        )

        connection.commit()
        flash("Product updated successfully.", "success")

    except (ValueError, sqlite3.Error) as exc:
        connection.rollback()
        flash(f"Could not update product: {exc}", "error")

    finally:
        connection.close()

    return redirect(url_for("manage_products"))


# =========================================================
# SOFT DELETE PRODUCT
# =========================================================

@app.route("/products/delete/<int:product_id>", methods=["POST"])
def delete_product(product_id):
    connection = get_connection()

    try:
        cursor = connection.execute(
            """
            UPDATE products
            SET is_active = 0,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND is_active = 1
            """,
            (product_id,),
        )

        if cursor.rowcount == 0:
            flash("Product not found or already deleted.", "error")
        else:
            flash(
                "Product deactivated. Existing sales history is preserved.",
                "success",
            )

        connection.commit()

    except sqlite3.Error as exc:
        connection.rollback()
        flash(f"Could not delete product: {exc}", "error")

    finally:
        connection.close()

    return redirect(url_for("manage_products"))


# =========================================================
# STOCK IN
# =========================================================

@app.route("/products/stock-in/<int:product_id>", methods=["POST"])
def stock_in(product_id):
    connection = get_connection()

    try:
        quantity = parse_integer(
            request.form.get("quantity"),
            "Quantity",
            minimum=1,
        )

        product = connection.execute(
            """
            SELECT id, name
            FROM products
            WHERE id = ? AND is_active = 1
            """,
            (product_id,),
        ).fetchone()

        if not product:
            raise ValueError("Product not found.")

        connection.execute(
            """
            UPDATE products
            SET stock = stock + ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND is_active = 1
            """,
            (quantity, product_id),
        )

        connection.commit()
        flash(
            f"Added {quantity} units to {product['name']}.",
            "success",
        )

    except (ValueError, sqlite3.Error) as exc:
        connection.rollback()
        flash(f"Could not update stock: {exc}", "error")

    finally:
        connection.close()

    return redirect(url_for("manage_products"))


# =========================================================
# PRODUCT API
# =========================================================

@app.route("/api/products", methods=["GET"])
def get_products_api():
    connection = get_connection()

    try:
        rows = connection.execute(
            """
            SELECT id, name, barcode, category_id, unit,
                   purchase_price, selling_price, stock,
                   reorder_level, tax_rate, expiry_date
            FROM products
            WHERE is_active = 1
            ORDER BY name
            """
        ).fetchall()

        products = []

        for row in rows:
            product = dict(row)
            product["purchase_price"] = float(
                product["purchase_price"] or 0
            )
            product["selling_price"] = float(
                product["selling_price"] or 0
            )
            product["stock"] = int(product["stock"] or 0)
            product["tax_rate"] = float(product["tax_rate"] or 0)
            products.append(product)

        return jsonify(products)

    finally:
        connection.close()


# =========================================================
# CHECKOUT / BILL GENERATION
# =========================================================

@app.route("/api/checkout", methods=["POST"])
def checkout():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return json_error("Invalid checkout request.")

    items = data.get("items")

    if not isinstance(items, list) or not items:
        return json_error("Your cart is empty.")

    customer_name = str(data.get("customer_name") or "").strip()
    customer_phone = str(data.get("customer_phone") or "").strip()

    if not validate_phone(customer_phone):
        return json_error("Enter a valid customer phone number.")

    try:
        discount_percent = parse_money(
            data.get("discount", 0),
            "Discount",
        )

        if discount_percent > 100:
            return json_error("Discount cannot exceed 100%.")

    except ValueError as exc:
        return json_error(str(exc))

    # Combine repeated product IDs.
    combined_items = {}

    for item in items:
        if not isinstance(item, dict):
            return json_error("Invalid product in cart.")

        try:
            product_id = parse_integer(
                item.get("id"),
                "Product ID",
                minimum=1,
            )

            quantity = parse_integer(
                item.get("quantity"),
                "Quantity",
                minimum=1,
            )

        except ValueError as exc:
            return json_error(str(exc))

        combined_items[product_id] = (
            combined_items.get(product_id, 0) + quantity
        )

    connection = get_connection()

    try:
        connection.execute("BEGIN IMMEDIATE")

        products = []

        for product_id, quantity in combined_items.items():
            product = connection.execute(
                """
                SELECT id, name, unit, selling_price, stock, tax_rate
                FROM products
                WHERE id = ? AND is_active = 1
                """,
                (product_id,),
            ).fetchone()

            if not product:
                raise ValueError(f"Product ID {product_id} was not found.")

            if int(product["stock"] or 0) < quantity:
                raise ValueError(
                    f"Not enough stock for {product['name']}. "
                    f"Available: {product['stock']}."
                )

            products.append((product, quantity))

        subtotal = Decimal("0.00")
        total_tax = Decimal("0.00")
        prepared_items = []

        for product, quantity in products:
            unit_price = money(product["selling_price"])
            tax_rate = money(product["tax_rate"])

            line_subtotal = money(unit_price * quantity)
            subtotal += line_subtotal

            prepared_items.append({
                "product": product,
                "quantity": quantity,
                "unit_price": unit_price,
                "line_subtotal": line_subtotal,
                "tax_rate": tax_rate,
            })

        subtotal = money(subtotal)
        discount_amount = money(
            subtotal * discount_percent / Decimal("100")
        )

        taxable_value = money(subtotal - discount_amount)

        for item in prepared_items:
            proportion = (
                item["line_subtotal"] / subtotal
                if subtotal > 0
                else Decimal("0")
            )

            item["discount_amount"] = money(
                discount_amount * proportion
            )

            item["taxable_value"] = money(
                item["line_subtotal"] - item["discount_amount"]
            )

            item["tax_amount"] = money(
                item["taxable_value"]
                * item["tax_rate"]
                / Decimal("100")
            )

            item["line_total"] = money(
                item["taxable_value"] + item["tax_amount"]
            )

            total_tax += item["tax_amount"]

        total_tax = money(total_tax)
        total_amount = money(taxable_value + total_tax)

        # Resolve optional customer information without assuming
        # a particular customer table schema.
        customer_id = None

        if customer_name and table_exists(connection, "customers"):
            customer_columns = get_table_columns(
                connection,
                "customers",
            )

            name_column = get_existing_column(
                connection,
                "customers",
                ["name", "customer_name", "full_name"],
            )

            phone_column = get_existing_column(
                connection,
                "customers",
                ["phone", "phone_number", "mobile"],
            )

            id_column = get_existing_column(
                connection,
                "customers",
                ["id", "customer_id"],
            )

            if name_column and id_column:
                if customer_phone and phone_column:
                    customer = connection.execute(
                        f"""
                        SELECT "{id_column}"
                        FROM customers
                        WHERE "{phone_column}" = ?
                        LIMIT 1
                        """,
                        (customer_phone,),
                    ).fetchone()
                else:
                    customer = None

                if customer:
                    customer_id = customer[id_column]
                else:
                    columns = [name_column]
                    values = [customer_name]

                    if phone_column:
                        columns.append(phone_column)
                        values.append(customer_phone or None)

                    placeholders = ", ".join("?" for _ in columns)
                    quoted_columns = ", ".join(
                        f'"{column}"' for column in columns
                    )

                    cursor = connection.execute(
                        f"""
                        INSERT INTO customers ({quoted_columns})
                        VALUES ({placeholders})
                        """,
                        values,
                    )

                    customer_id = cursor.lastrowid

        invoice_number = (
            "SC-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        )

        cgst_amount = money(total_tax / Decimal("2"))
        sgst_amount = money(total_tax - cgst_amount)
        igst_amount = Decimal("0.00")

        sales_columns = get_table_columns(connection, "sales")

        sale_data = {
            "invoice_number": invoice_number,
            "customer_id": customer_id,
            "subtotal": str(subtotal),
            "discount_amount": str(discount_amount),
            "taxable_value": str(taxable_value),
            "cgst_amount": str(cgst_amount),
            "sgst_amount": str(sgst_amount),
            "igst_amount": str(igst_amount),
            "tax_amount": str(total_tax),
            "total_amount": str(total_amount),
            "amount_paid": str(total_amount),
            "balance_due": "0.00",
            "status": "completed",
        }

        # Only use fields that actually exist in this database.
        sale_data = {
            key: value
            for key, value in sale_data.items()
            if key in sales_columns
        }

        sale_columns_sql = ", ".join(
            f'"{column}"' for column in sale_data
        )
        sale_placeholders = ", ".join("?" for _ in sale_data)

        cursor = connection.execute(
            f"""
            INSERT INTO sales ({sale_columns_sql})
            VALUES ({sale_placeholders})
            """,
            list(sale_data.values()),
        )

        sale_id = cursor.lastrowid

        for item in prepared_items:
            product = item["product"]

            connection.execute(
                """
                INSERT INTO sale_items (
                    sale_id,
                    product_id,
                    product_name,
                    quantity,
                    unit,
                    unit_price,
                    discount_amount,
                    taxable_value,
                    tax_rate,
                    tax_amount,
                    line_total
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    sale_id,
                    product["id"],
                    product["name"],
                    item["quantity"],
                    product["unit"],
                    str(item["unit_price"]),
                    str(item["discount_amount"]),
                    str(item["taxable_value"]),
                    str(item["tax_rate"]),
                    str(item["tax_amount"]),
                    str(item["line_total"]),
                ),
            )

            connection.execute(
                """
                UPDATE products
                SET stock = stock - ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (item["quantity"], product["id"]),
            )

        connection.commit()

        return jsonify({
            "success": True,
            "message": "Bill generated successfully.",
            "sale_id": sale_id,
            "invoice_number": invoice_number,
            "subtotal": float(subtotal),
            "discount_amount": float(discount_amount),
            "taxable_value": float(taxable_value),
            "cgst_amount": float(cgst_amount),
            "sgst_amount": float(sgst_amount),
            "igst_amount": float(igst_amount),
            "tax_amount": float(total_tax),
            "total_amount": float(total_amount),
            "amount_paid": float(total_amount),
            "balance_due": 0.0,
        })

    except ValueError as exc:
        connection.rollback()
        return json_error(str(exc))

    except sqlite3.Error:
        connection.rollback()
        app.logger.exception("Database error during checkout")
        return json_error(
            "Checkout failed because of a database error. "
            "Check the Flask terminal for details.",
            500,
        )

    finally:
        connection.close()


# =========================================================
# SUPPLIER MANAGEMENT
# =========================================================

@app.route("/shop-management", methods=["GET"])
def shop_management():
    connection = get_connection()

    try:
        suppliers = connection.execute(
            """
            SELECT *
            FROM suppliers
            ORDER BY name
            """
        ).fetchall()

        products = connection.execute(
            """
            SELECT id, name, barcode, stock, purchase_price, unit
            FROM products
            WHERE is_active = 1
            ORDER BY name
            """
        ).fetchall()
        products = [dict(product) for product in products]
        purchases = connection.execute(
            """
            SELECT
                p.*,
                s.name AS supplier_name
            FROM purchases p
            LEFT JOIN suppliers s ON s.id = p.supplier_id
            ORDER BY p.id DESC
            LIMIT 100
            """
        ).fetchall()

        purchase_columns = get_table_columns(
            connection,
            "purchases",
        )

        total_purchases = 0
        outstanding_balance = 0

        if "total_amount" in purchase_columns:
            total_purchases = connection.execute(
                """
                SELECT COALESCE(SUM(total_amount), 0) AS total
                FROM purchases
                """
            ).fetchone()["total"]

        if "balance_due" in purchase_columns:
            outstanding_balance = connection.execute(
                """
                SELECT COALESCE(SUM(balance_due), 0) AS total
                FROM purchases
                """
            ).fetchone()["total"]

        return render_template(
            "shop_management.html",
            suppliers=suppliers,
            products=products,
            purchases=purchases,
            total_purchases=float(total_purchases or 0),
            outstanding_balance=float(outstanding_balance or 0),
        )

    finally:
        connection.close()


# =========================================================
# ADD SUPPLIER
# =========================================================

@app.route("/suppliers/add", methods=["POST"])
def add_supplier():
    connection = get_connection()

    try:
        name = request.form.get("name", "").strip()
        phone = request.form.get("phone", "").strip()
        email = request.form.get("email", "").strip()
        address = request.form.get("address", "").strip()

        if not name:
            raise ValueError("Supplier name is required.")

        if not validate_phone(phone):
            raise ValueError("Enter a valid supplier phone number.")

        connection.execute(
            """
            INSERT INTO suppliers (name, phone, email, address)
            VALUES (?, ?, ?, ?)
            """,
            (
                name,
                phone or None,
                email or None,
                address or None,
            ),
        )

        connection.commit()
        flash("Supplier added successfully.", "success")

    except (ValueError, sqlite3.Error) as exc:
        connection.rollback()
        flash(f"Could not add supplier: {exc}", "error")

    finally:
        connection.close()

    return redirect(url_for("shop_management"))


# =========================================================
# RECORD PURCHASE / RESTOCK PRODUCTS
# =========================================================

@app.route("/purchases/create", methods=["POST"])
def create_purchase():
    connection = get_connection()

    try:
        supplier_id = parse_integer(
            request.form.get("supplier_id"),
            "Supplier",
            minimum=1,
        )

        amount_paid = parse_money(
            request.form.get("amount_paid", "0"),
            "Amount paid",
        )

        notes = request.form.get("notes", "").strip()

        product_ids = request.form.getlist("product_id[]")
        quantities = request.form.getlist("quantity[]")
        unit_costs = request.form.getlist("unit_cost[]")

        if not (
            len(product_ids)
            == len(quantities)
            == len(unit_costs)
        ):
            raise ValueError("Purchase item details are incomplete.")

        supplier = connection.execute(
            "SELECT id FROM suppliers WHERE id = ?",
            (supplier_id,),
        ).fetchone()

        if not supplier:
            raise ValueError("Please select a valid supplier.")

        purchase_items = []
        seen_products = set()

        for product_id_text, quantity_text, cost_text in zip(
            product_ids,
            quantities,
            unit_costs,
        ):
            if not str(product_id_text).strip():
                continue

            product_id = parse_integer(
                product_id_text,
                "Product ID",
                minimum=1,
            )

            quantity = parse_integer(
                quantity_text,
                "Purchase quantity",
                minimum=1,
            )

            unit_cost = parse_money(
                cost_text,
                "Unit cost",
            )

            if product_id in seen_products:
                raise ValueError(
                    "Each product should appear only once per purchase."
                )

            seen_products.add(product_id)

            product = connection.execute(
                """
                SELECT id, name
                FROM products
                WHERE id = ? AND is_active = 1
                """,
                (product_id,),
            ).fetchone()

            if not product:
                raise ValueError(
                    f"Product ID {product_id} was not found."
                )

            purchase_items.append({
                "product_id": product_id,
                "name": product["name"],
                "quantity": quantity,
                "unit_cost": unit_cost,
                "line_total": money(unit_cost * quantity),
            })

        if not purchase_items:
            raise ValueError("Add at least one product to the purchase.")

        total_amount = money(
            sum(
                (item["line_total"] for item in purchase_items),
                Decimal("0.00"),
            )
        )

        if amount_paid > total_amount:
            raise ValueError(
                "Amount paid cannot exceed the purchase total."
            )

        balance_due = money(total_amount - amount_paid)

        connection.execute("BEGIN IMMEDIATE")

        purchase_columns = get_table_columns(
            connection,
            "purchases",
        )

        purchase_data = {
            "supplier_id": supplier_id,
            "total_amount": str(total_amount),
            "amount_paid": str(amount_paid),
            "balance_due": str(balance_due),
            "notes": notes or None,
        }

        purchase_data = {
            key: value
            for key, value in purchase_data.items()
            if key in purchase_columns
        }

        if "supplier_id" not in purchase_data:
            raise ValueError(
                "The purchases table is missing its supplier_id column."
            )

        if "total_amount" not in purchase_data:
            raise ValueError(
                "The purchases table is missing its total_amount column."
            )

        columns_sql = ", ".join(
            f'"{column}"' for column in purchase_data
        )
        placeholders = ", ".join("?" for _ in purchase_data)

        cursor = connection.execute(
            f"""
            INSERT INTO purchases ({columns_sql})
            VALUES ({placeholders})
            """,
            list(purchase_data.values()),
        )

        purchase_id = cursor.lastrowid

        purchase_item_columns = get_table_columns(
            connection,
            "purchase_items",
        )

        for item in purchase_items:
            item_data = {
                "purchase_id": purchase_id,
                "product_id": item["product_id"],
                "quantity": item["quantity"],
                "unit_cost": str(item["unit_cost"]),
                "line_total": str(item["line_total"]),
            }

            item_data = {
                key: value
                for key, value in item_data.items()
                if key in purchase_item_columns
            }

            required = {
                "purchase_id",
                "product_id",
                "quantity",
            }

            if not required.issubset(item_data):
                raise ValueError(
                    "The purchase_items table is missing required columns."
                )

            item_columns_sql = ", ".join(
                f'"{column}"' for column in item_data
            )
            item_placeholders = ", ".join(
                "?" for _ in item_data
            )

            connection.execute(
                f"""
                INSERT INTO purchase_items ({item_columns_sql})
                VALUES ({item_placeholders})
                """,
                list(item_data.values()),
            )

            connection.execute(
                """
                UPDATE products
                SET stock = stock + ?,
                    purchase_price = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    item["quantity"],
                    str(item["unit_cost"]),
                    item["product_id"],
                ),
            )

        connection.commit()

        flash(
            f"Purchase #{purchase_id} recorded. Stock updated successfully.",
            "success",
        )

    except (ValueError, sqlite3.Error) as exc:
        connection.rollback()
        flash(f"Could not record purchase: {exc}", "error")

    finally:
        connection.close()

    return redirect(url_for("shop_management"))


# =========================================================
# HEALTH CHECK
# =========================================================

@app.route("/api/health", methods=["GET"])
def health_check():
    return jsonify({
        "status": "ok",
        "application": "SmartCart AI",
    })


# =========================================================
# RUN APPLICATION
# =========================================================

if __name__ == "__main__":
    app.run(debug=True)