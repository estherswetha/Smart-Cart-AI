import os
from pathlib import Path


# Find the main project directory.
BASE_DIR = Path(__file__).resolve().parent


# Store application data inside the instance folder.
INSTANCE_DIR = BASE_DIR / "instance"

# Create the instance folder if it does not exist.
INSTANCE_DIR.mkdir(parents=True, exist_ok=True)


# SQLite database location.
DATABASE_PATH = INSTANCE_DIR / "smartcart.db"


# Application settings.
APP_NAME = "SmartCart AI"

SHOP_NAME = os.environ.get(
    "SMARTCART_SHOP_NAME",
    "SmartCart Supermarket"
)

SHOP_ADDRESS = os.environ.get(
    "SMARTCART_SHOP_ADDRESS",
    "Tamil Nadu, India"
)

CURRENCY_SYMBOL = "₹"


# Flask settings.
SECRET_KEY = os.environ.get(
    "SMARTCART_SECRET_KEY",
    "dev-only-change-this-secret-before-deployment"
)

DEBUG = os.environ.get(
    "SMARTCART_DEBUG",
    "true"
).lower() == "true"


# Session settings.
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"

# Enable this when deploying behind correctly configured HTTPS.
SESSION_COOKIE_SECURE = os.environ.get(
    "SMARTCART_HTTPS",
    "false"
).lower() == "true"


# Default invoice settings.
INVOICE_PREFIX = "SC"
RETURN_POLICY = "Please retain your invoice for returns."


# Default application preferences.
DEFAULT_LOW_STOCK_LEVEL = 10

# Set the tax treatment explicitly in application settings
# when we implement billing.
DEFAULT_TAX_MODE = "exclusive"


# Directories used for generated files.
INVOICES_DIR = BASE_DIR / "invoices"
EXPORTS_DIR = BASE_DIR / "exports"
BACKUPS_DIR = BASE_DIR / "backups"

INVOICES_DIR.mkdir(parents=True, exist_ok=True)
EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
BACKUPS_DIR.mkdir(parents=True, exist_ok=True)