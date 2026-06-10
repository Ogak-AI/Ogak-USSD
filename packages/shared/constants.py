"""
Ogak Constants
Application-wide constants, configuration defaults, and lookup tables.
"""

from __future__ import annotations

# ===================================================================
# USSD Constants
# ===================================================================

USSD_SERVICE_CODE = "*384*OGAK#"
USSD_SESSION_TTL = 180  # seconds
USSD_MAX_PIN_ATTEMPTS = 3
USSD_PIN_LOCKOUT_SECONDS = 1800  # 30 minutes

# Back navigation input
USSD_BACK_INPUT = "0"
USSD_CANCEL_INPUT = "00"

# ===================================================================
# ILP Constants
# ===================================================================

ILP_CONNECTOR_ADDRESS = "g.ogak.ng.connector"
ILP_FIAT_PREFIX = "g.ogak.ng.fiat"
ILP_CRYPTO_PREFIX = "g.ogak.ng.crypto"

# ILP packet constraints
ILP_MAX_PACKET_AMOUNT = 10_000_000_00  # ₦10M in kobo
ILP_CONDITION_SIZE = 32  # bytes (SHA-256)
ILP_FULFILLMENT_SIZE = 32  # bytes
ILP_DEFAULT_EXPIRY_MS = 30_000  # 30 seconds
ILP_MIN_EXPIRY_MS = 5_000  # 5 seconds

# ===================================================================
# Rate Engine Constants
# ===================================================================

RATE_CACHE_TTL = 30  # seconds
RATE_QUOTE_EXPIRY = 120  # seconds
DEFAULT_SPREAD_BPS = 150  # 1.5% spread

# ===================================================================
# KYC / Transaction Limits (in Naira)
# ===================================================================

KYC_LIMITS = {
    0: {"per_tx": 0, "daily": 0, "description": "Unverified — no transactions allowed"},
    1: {"per_tx": 50_000, "daily": 500_000, "description": "Phone + PIN verified"},
    2: {"per_tx": 500_000, "daily": 5_000_000, "description": "BVN validated"},
    3: {"per_tx": 5_000_000, "daily": 50_000_000, "description": "Full KYC"},
}

# ===================================================================
# Nigerian Banks
# ===================================================================

NIGERIAN_BANKS = {
    "044": {"name": "Access Bank", "short": "Access"},
    "058": {"name": "Guaranty Trust Bank", "short": "GTB"},
    "057": {"name": "Zenith Bank", "short": "Zenith"},
    "033": {"name": "United Bank for Africa", "short": "UBA"},
    "011": {"name": "First Bank of Nigeria", "short": "FirstBank"},
    "214": {"name": "First City Monument Bank", "short": "FCMB"},
    "070": {"name": "Fidelity Bank", "short": "Fidelity"},
    "221": {"name": "Stanbic IBTC Bank", "short": "Stanbic"},
    "232": {"name": "Sterling Bank", "short": "Sterling"},
    "032": {"name": "Union Bank", "short": "Union"},
    "035": {"name": "Wema Bank", "short": "Wema"},
    "076": {"name": "Polaris Bank", "short": "Polaris"},
    "050": {"name": "Ecobank Nigeria", "short": "Ecobank"},
    "082": {"name": "Keystone Bank", "short": "Keystone"},
    "090267": {"name": "Kuda Microfinance Bank", "short": "Kuda"},
    "100004": {"name": "OPay", "short": "OPay"},
    "100033": {"name": "PalmPay", "short": "PalmPay"},
    "100567": {"name": "Moniepoint", "short": "Moniepoint"},
}

# Popular banks displayed first in USSD menus
POPULAR_BANKS = ["044", "058", "057", "033", "011", "090267", "100004", "100033"]

# ===================================================================
# Crypto Asset Display
# ===================================================================

CRYPTO_ASSETS = {
    "BTC": {"name": "Bitcoin", "symbol": "₿", "decimals": 8, "min_amount": 0.00001},
    "USDT": {"name": "Tether USD", "symbol": "$", "decimals": 2, "min_amount": 1.0},
    "USDC": {"name": "USD Coin", "symbol": "$", "decimals": 2, "min_amount": 1.0},
    "ETH": {"name": "Ethereum", "symbol": "Ξ", "decimals": 8, "min_amount": 0.001},
    "BNB": {"name": "Binance Coin", "symbol": "BNB", "decimals": 8, "min_amount": 0.001},
}

# ===================================================================
# Exchange Configuration
# ===================================================================

EXCHANGES = {
    "quidax": {
        "name": "Quidax",
        "display": "Quidax (SEC Licensed)",
        "base_url": "https://www.quidax.com/api/v1",
        "supported_assets": ["BTC", "USDT", "USDC", "ETH", "BNB"],
    },
    "busha": {
        "name": "Busha",
        "display": "Busha (SEC Licensed)",
        "base_url": "https://api.busha.co/v2",
        "supported_assets": ["BTC", "USDT", "USDC", "ETH"],
    },
    "binance": {
        "name": "Binance",
        "display": "Binance",
        "base_url": "https://api.binance.com/api/v3",
        "supported_assets": ["BTC", "USDT", "USDC", "ETH", "BNB"],
    },
}

# ===================================================================
# Naira Formatting
# ===================================================================

NAIRA_SYMBOL = "₦"
KOBO_MULTIPLIER = 100  # 1 Naira = 100 Kobo (for Paystack)


def format_naira(amount: float | int) -> str:
    """Format amount as Naira with commas. E.g., 50000 → '₦50,000.00'"""
    return f"{NAIRA_SYMBOL}{amount:,.2f}"


def format_crypto(amount: float, asset: str) -> str:
    """Format crypto amount with appropriate decimals."""
    decimals = CRYPTO_ASSETS.get(asset, {}).get("decimals", 8)
    return f"{amount:.{decimals}f} {asset}"


# ===================================================================
# SMS Templates
# ===================================================================

SMS_TEMPLATES = {
    "buy_success": (
        "Ogak: You bought {crypto_amount} {crypto_asset} for {fiat_amount}. "
        "Ref: {reference}. Rate: {rate}. Thank you!"
    ),
    "sell_success": (
        "Ogak: You sold {crypto_amount} {crypto_asset} for {fiat_amount}. "
        "Credited to your {bank_name} account. Ref: {reference}."
    ),
    "transaction_failed": (
        "Ogak: Your {tx_type} transaction for {amount} has failed. "
        "Reason: {reason}. No funds were debited. Ref: {reference}."
    ),
    "otp_code": "Ogak: Your OTP code is {otp}. Valid for 5 minutes. Do not share.",
    "pin_locked": (
        "Ogak: Your account has been temporarily locked due to multiple "
        "failed PIN attempts. Try again after 30 minutes."
    ),
    "welcome": (
        "Welcome to Ogak! Your account has been created. "
        "Dial {service_code} to buy/sell crypto safely."
    ),
}
