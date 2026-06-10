"""
Ogak Shared Types
Pydantic models and enums used across all services.
"""

from __future__ import annotations

import enum
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


# ===================================================================
# Enums
# ===================================================================

class TransactionType(str, enum.Enum):
    """Type of crypto-fiat transaction."""
    BUY = "BUY"    # Fiat → Crypto
    SELL = "SELL"   # Crypto → Fiat


class TransactionStatus(str, enum.Enum):
    """Lifecycle status of a transaction."""
    PENDING = "PENDING"           # Created, awaiting quote
    QUOTED = "QUOTED"             # Quote generated, awaiting user confirmation
    CONFIRMED = "CONFIRMED"       # User confirmed, awaiting execution
    EXECUTING = "EXECUTING"       # ILP Prepare sent, processing
    FIAT_SETTLED = "FIAT_SETTLED" # Fiat leg completed
    CRYPTO_SETTLED = "CRYPTO_SETTLED"  # Crypto leg completed
    COMPLETED = "COMPLETED"       # Both legs settled successfully
    FAILED = "FAILED"             # One or both legs failed
    ROLLED_BACK = "ROLLED_BACK"   # Failed and reversed
    EXPIRED = "EXPIRED"           # Quote expired before confirmation
    CANCELLED = "CANCELLED"       # User cancelled


class CryptoAsset(str, enum.Enum):
    """Supported cryptocurrency assets."""
    BTC = "BTC"
    USDT = "USDT"
    USDC = "USDC"
    ETH = "ETH"
    BNB = "BNB"


class KYCTier(int, enum.Enum):
    """KYC verification tier determining transaction limits."""
    TIER_0 = 0  # Unverified — phone only
    TIER_1 = 1  # Phone + PIN verified
    TIER_2 = 2  # BVN validated
    TIER_3 = 3  # Full KYC (ID + address)


class Exchange(str, enum.Enum):
    """Supported crypto exchanges / VASPs."""
    QUIDAX = "quidax"
    BUSHA = "busha"
    BINANCE = "binance"


class BankCode(str, enum.Enum):
    """Common Nigerian bank codes (NIBSS codes)."""
    ACCESS = "044"
    GTB = "058"
    ZENITH = "057"
    UBA = "033"
    FIRST_BANK = "011"
    FCMB = "214"
    FIDELITY = "070"
    STANBIC = "221"
    STERLING = "232"
    UNION = "032"
    WEMA = "035"
    POLARIS = "076"
    ECOBANK = "050"
    KEYSTONE = "082"
    KUDA = "090267"
    OPAY = "100004"
    PALMPAY = "100033"
    MONIEPOINT = "100567"


class Language(str, enum.Enum):
    """Supported USSD languages."""
    EN = "en"      # English
    PCM = "pcm"    # Nigerian Pidgin
    YO = "yo"      # Yoruba
    HA = "ha"       # Hausa
    IG = "ig"      # Igbo


class ILPPacketType(int, enum.Enum):
    """ILP packet types (ILPv4)."""
    PREPARE = 12
    FULFILL = 13
    REJECT = 14


class ILPErrorCode(str, enum.Enum):
    """ILP error codes with prefix conventions."""
    # Final errors (don't retry)
    F00_BAD_REQUEST = "F00"
    F01_INVALID_PACKET = "F01"
    F02_UNREACHABLE = "F02"
    F03_INVALID_AMOUNT = "F03"
    F04_INSUFFICIENT_DST_AMOUNT = "F04"
    F05_WRONG_CONDITION = "F05"
    F06_UNEXPECTED_PAYMENT = "F06"
    F07_CANNOT_RECEIVE = "F07"
    F08_AMOUNT_TOO_LARGE = "F08"
    F09_INVALID_PEER_RESPONSE = "F09"
    F99_APPLICATION_ERROR = "F99"
    # Temporary errors (retry may succeed)
    T00_INTERNAL_ERROR = "T00"
    T01_PEER_UNREACHABLE = "T01"
    T02_PEER_BUSY = "T02"
    T03_CONNECTOR_BUSY = "T03"
    T04_INSUFFICIENT_LIQUIDITY = "T04"
    T05_RATE_LIMITED = "T05"
    # Relative errors (adjust and retry)
    R00_TRANSFER_TIMED_OUT = "R00"
    R01_INSUFFICIENT_SOURCE_AMOUNT = "R01"
    R02_INSUFFICIENT_TIMEOUT = "R02"


class USSDMenuState(str, enum.Enum):
    """All possible USSD menu states."""
    MAIN_MENU = "MAIN_MENU"
    # Buy flow
    BUY_SELECT_ASSET = "BUY_SELECT_ASSET"
    BUY_ENTER_AMOUNT = "BUY_ENTER_AMOUNT"
    BUY_SELECT_BANK = "BUY_SELECT_BANK"
    BUY_CONFIRM_QUOTE = "BUY_CONFIRM_QUOTE"
    BUY_ENTER_PIN = "BUY_ENTER_PIN"
    BUY_PROCESSING = "BUY_PROCESSING"
    BUY_RESULT = "BUY_RESULT"
    # Sell flow
    SELL_SELECT_ASSET = "SELL_SELECT_ASSET"
    SELL_ENTER_AMOUNT = "SELL_ENTER_AMOUNT"
    SELL_SELECT_EXCHANGE = "SELL_SELECT_EXCHANGE"
    SELL_SELECT_BANK = "SELL_SELECT_BANK"
    SELL_CONFIRM_QUOTE = "SELL_CONFIRM_QUOTE"
    SELL_ENTER_PIN = "SELL_ENTER_PIN"
    SELL_PROCESSING = "SELL_PROCESSING"
    SELL_RESULT = "SELL_RESULT"
    # Rates
    RATES_SELECT_ASSET = "RATES_SELECT_ASSET"
    RATES_VIEW = "RATES_VIEW"
    # Link account
    LINK_SELECT_TYPE = "LINK_SELECT_TYPE"
    LINK_BANK_CODE = "LINK_BANK_CODE"
    LINK_ACCOUNT_NUMBER = "LINK_ACCOUNT_NUMBER"
    LINK_CONFIRM = "LINK_CONFIRM"
    LINK_BVN = "LINK_BVN"
    LINK_BVN_CONFIRM = "LINK_BVN_CONFIRM"
    LINK_EXCHANGE_SELECT = "LINK_EXCHANGE_SELECT"
    LINK_EXCHANGE_API_KEY = "LINK_EXCHANGE_API_KEY"
    # History
    HISTORY_VIEW = "HISTORY_VIEW"
    HISTORY_DETAIL = "HISTORY_DETAIL"
    # Help
    HELP_VIEW = "HELP_VIEW"
    # Settings
    LANGUAGE_SELECT = "LANGUAGE_SELECT"
    # Registration
    REGISTER_PIN = "REGISTER_PIN"
    REGISTER_CONFIRM_PIN = "REGISTER_CONFIRM_PIN"


# ===================================================================
# Pydantic Models — Domain Objects
# ===================================================================

class UserBase(BaseModel):
    """Base user model."""
    phone_number: str = Field(..., description="Nigerian phone number in E.164 format")
    language: Language = Field(default=Language.EN, description="Preferred language")
    kyc_tier: KYCTier = Field(default=KYCTier.TIER_0, description="KYC verification level")


class UserCreate(UserBase):
    """Model for creating a new user."""
    pin: str = Field(..., min_length=4, max_length=6, description="USSD PIN (4-6 digits)")

    @field_validator("pin")
    @classmethod
    def validate_pin(cls, v: str) -> str:
        if not v.isdigit():
            raise ValueError("PIN must contain only digits")
        return v

    @field_validator("phone_number")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        # Accept Nigerian phone numbers
        if not v.startswith("+234") and not v.startswith("234"):
            if v.startswith("0"):
                v = "+234" + v[1:]
            else:
                raise ValueError("Phone number must be a valid Nigerian number")
        if not v.startswith("+"):
            v = "+" + v
        return v


class UserResponse(UserBase):
    """User response model (no sensitive data)."""
    id: str
    created_at: datetime
    is_active: bool = True

    class Config:
        from_attributes = True


class BankAccountBase(BaseModel):
    """Bank account model."""
    bank_code: str = Field(..., description="Nigerian bank code (NIBSS)")
    bank_name: str = Field(..., description="Bank name")
    account_number: str = Field(..., min_length=10, max_length=10, description="NUBAN account number")
    account_name: str = Field(..., description="Account holder name")


class BankAccountCreate(BankAccountBase):
    """Create bank account link."""
    pass


class BankAccountResponse(BankAccountBase):
    """Bank account response."""
    id: str
    user_id: str
    is_verified: bool = False
    created_at: datetime

    class Config:
        from_attributes = True


class ExchangeAccountBase(BaseModel):
    """Exchange/VASP account model."""
    exchange: Exchange
    account_id: Optional[str] = None


class ExchangeAccountCreate(ExchangeAccountBase):
    """Create exchange account link."""
    api_key: str = Field(..., description="Exchange API key")
    api_secret: str = Field(..., description="Exchange API secret")


class ExchangeAccountResponse(ExchangeAccountBase):
    """Exchange account response (no API keys)."""
    id: str
    user_id: str
    is_verified: bool = False
    created_at: datetime

    class Config:
        from_attributes = True


class QuoteRequest(BaseModel):
    """Request a conversion quote."""
    transaction_type: TransactionType
    crypto_asset: CryptoAsset
    fiat_amount: Optional[Decimal] = Field(None, gt=0, description="Amount in Naira")
    crypto_amount: Optional[Decimal] = Field(None, gt=0, description="Amount in crypto")
    exchange: Exchange = Field(default=Exchange.QUIDAX)


class QuoteResponse(BaseModel):
    """Conversion quote response."""
    id: str
    transaction_type: TransactionType
    crypto_asset: CryptoAsset
    fiat_amount: Decimal = Field(..., description="Amount in Naira")
    crypto_amount: Decimal = Field(..., description="Amount in crypto")
    exchange_rate: Decimal = Field(..., description="Rate used")
    spread_bps: int = Field(..., description="Spread in basis points")
    fee_ngn: Decimal = Field(..., description="Fee in Naira")
    total_ngn: Decimal = Field(..., description="Total Naira (amount + fee)")
    expires_at: datetime
    ilp_condition: Optional[str] = None

    class Config:
        from_attributes = True


class TransactionCreate(BaseModel):
    """Create a transaction from a confirmed quote."""
    quote_id: str
    bank_account_id: str
    pin: str = Field(..., min_length=4, max_length=6)


class TransactionResponse(BaseModel):
    """Transaction response."""
    id: str
    user_id: str
    transaction_type: TransactionType
    status: TransactionStatus
    crypto_asset: CryptoAsset
    fiat_amount: Decimal
    crypto_amount: Decimal
    exchange_rate: Decimal
    fee_ngn: Decimal
    exchange: Exchange
    bank_reference: Optional[str] = None
    exchange_reference: Optional[str] = None
    ilp_packet_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None
    failure_reason: Optional[str] = None

    class Config:
        from_attributes = True


class AuditLogEntry(BaseModel):
    """Audit log entry."""
    id: str
    user_id: Optional[str] = None
    action: str
    resource_type: str
    resource_id: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    ip_address: Optional[str] = None
    timestamp: datetime


# ===================================================================
# ILP Models
# ===================================================================

class ILPPreparePacket(BaseModel):
    """ILP Prepare packet."""
    amount: int = Field(..., ge=0, description="Amount in smallest unit")
    expires_at: datetime
    execution_condition: bytes = Field(..., description="SHA-256 condition (32 bytes)")
    destination: str = Field(..., description="ILP address")
    data: bytes = Field(default=b"", description="End-to-end STREAM data")


class ILPFulfillPacket(BaseModel):
    """ILP Fulfill packet."""
    fulfillment: bytes = Field(..., description="32-byte preimage")
    data: bytes = Field(default=b"", description="Additional data")


class ILPRejectPacket(BaseModel):
    """ILP Reject packet."""
    code: ILPErrorCode
    triggered_by: str = Field(..., description="ILP address of rejecting node")
    message: str = Field(default="", description="Human-readable error")
    data: bytes = Field(default=b"", description="Additional error data")


# ===================================================================
# USSD Models
# ===================================================================

class USSDRequest(BaseModel):
    """Africa's Talking USSD callback request."""
    sessionId: str = Field(..., alias="sessionId")
    serviceCode: str = Field(..., alias="serviceCode")
    phoneNumber: str = Field(..., alias="phoneNumber")
    text: str = Field(default="", alias="text")
    networkCode: Optional[str] = Field(None, alias="networkCode")


class USSDSession(BaseModel):
    """Internal USSD session state stored in Redis."""
    session_id: str
    phone_number: str
    state: USSDMenuState = USSDMenuState.MAIN_MENU
    data: dict[str, Any] = Field(default_factory=dict)
    language: Language = Language.EN
    history: list[str] = Field(default_factory=list)  # State history for back nav
    pin_attempts: int = 0
    created_at: float  # Unix timestamp
    last_activity_at: float  # Unix timestamp
    user_id: Optional[str] = None


# ===================================================================
# Open Payments Models
# ===================================================================

class WalletAddress(BaseModel):
    """Open Payments wallet address."""
    id: str
    publicName: str
    assetCode: str = "NGN"
    assetScale: int = 2
    authServer: str
    resourceServer: str


class IncomingPaymentCreate(BaseModel):
    """Create an incoming payment."""
    walletAddressUrl: str
    incomingAmount: Optional[dict[str, Any]] = None
    expiresAt: Optional[datetime] = None
    metadata: Optional[dict[str, Any]] = None


class OutgoingPaymentCreate(BaseModel):
    """Create an outgoing payment."""
    walletAddressUrl: str
    quoteId: str
    metadata: Optional[dict[str, Any]] = None


# ===================================================================
# API Response Wrappers
# ===================================================================

class APIResponse(BaseModel):
    """Standard API response wrapper."""
    success: bool = True
    message: str = ""
    data: Optional[Any] = None
    errors: Optional[list[str]] = None


class PaginatedResponse(BaseModel):
    """Paginated API response."""
    success: bool = True
    data: list[Any] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20
    has_more: bool = False


# ═══════════════════════════════════════════════════════════════════
# Open Payments Core Models (shared)
# ═══════════════════════════════════════════════════════════════════

class OpenPaymentsWalletAddress(BaseModel):
    """Standard Open Payments Wallet Address document (what client.walletAddress.get returns)."""
    id: str
    publicName: Optional[str] = None
    assetCode: str = "NGN"
    assetScale: int = 2
    authServer: str
    resourceServer: str


class OpenPaymentsGrantRequest(BaseModel):
    """GNAP-style grant request body for Open Payments."""
    access_token: dict[str, Any]
    interact: Optional[dict[str, Any]] = None
    client: Optional[str] = None


class OpenPaymentsAccessToken(BaseModel):
    value: str
    manage: Optional[str] = None
    access: list[dict[str, Any]] = Field(default_factory=list)
    expires_in: Optional[int] = None  # seconds


class OpenPaymentsGrantResponse(BaseModel):
    """Response for a finalized (non-interactive) grant or pending grant."""
    access_token: Optional[OpenPaymentsAccessToken] = None
    continue_: Optional[dict[str, Any]] = Field(None, alias="continue")
    interact: Optional[dict[str, Any]] = None

    class Config:
        populate_by_name = True


class OpenPaymentsIncomingPayment(BaseModel):
    """Incoming payment resource (as returned by resource server)."""
    id: str
    walletAddress: str
    incomingAmount: Optional[dict[str, Any]] = None
    receivedAmount: dict[str, Any] = Field(default_factory=lambda: {"value": "0", "assetCode": "NGN", "assetScale": 2})
    completed: bool = False
    metadata: Optional[dict[str, Any]] = None
    createdAt: datetime
    expiresAt: Optional[datetime] = None
    updatedAt: Optional[datetime] = None


class OpenPaymentsIncomingPaymentCreateRequest(BaseModel):
    """Body for creating an incoming payment (sent to resource server)."""
    walletAddress: str
    incomingAmount: Optional[dict[str, Any]] = None
    expiresAt: Optional[datetime] = None
    metadata: Optional[dict[str, Any]] = None
