"""
Ogak Custom Errors
Structured error classes for consistent error handling across all services.
"""

from __future__ import annotations

from typing import Any, Optional


class OgakError(Exception):
    """Base error class for all Ogak exceptions."""

    def __init__(
        self,
        message: str,
        code: str = "OGAK_ERROR",
        details: Optional[dict[str, Any]] = None,
        status_code: int = 500,
    ) -> None:
        self.message = message
        self.code = code
        self.details = details or {}
        self.status_code = status_code
        super().__init__(self.message)

    def to_dict(self) -> dict[str, Any]:
        return {
            "error": True,
            "code": self.code,
            "message": self.message,
            "details": self.details,
        }


# ===================================================================
# USSD Errors
# ===================================================================

class USSDError(OgakError):
    """Base USSD error."""

    def __init__(self, message: str, **kwargs: Any) -> None:
        super().__init__(message, code="USSD_ERROR", status_code=400, **kwargs)


class USSDSessionExpiredError(USSDError):
    """USSD session has expired."""

    def __init__(self) -> None:
        super().__init__(
            message="Your session has expired. Please dial again.",
            details={"code": "SESSION_EXPIRED"},
        )


class USSDInvalidInputError(USSDError):
    """Invalid USSD input from user."""

    def __init__(self, expected: str = "") -> None:
        msg = "Invalid input."
        if expected:
            msg += f" Expected: {expected}"
        super().__init__(message=msg, details={"expected": expected})


class USSDPinLockedError(USSDError):
    """Account locked due to too many failed PIN attempts."""

    def __init__(self, lockout_minutes: int = 30) -> None:
        super().__init__(
            message=f"Account locked. Try again after {lockout_minutes} minutes.",
            details={"lockout_minutes": lockout_minutes},
        )


# ===================================================================
# Authentication Errors
# ===================================================================

class AuthError(OgakError):
    """Authentication error."""

    def __init__(self, message: str = "Authentication failed", **kwargs: Any) -> None:
        super().__init__(message, code="AUTH_ERROR", status_code=401, **kwargs)


class InvalidPinError(AuthError):
    """Invalid PIN provided."""

    def __init__(self, attempts_remaining: int = 0) -> None:
        super().__init__(
            message=f"Invalid PIN. {attempts_remaining} attempt(s) remaining.",
            details={"attempts_remaining": attempts_remaining},
        )


# ===================================================================
# Transaction Errors
# ===================================================================

class TransactionError(OgakError):
    """Transaction-related error."""

    def __init__(self, message: str, **kwargs: Any) -> None:
        super().__init__(message, code="TRANSACTION_ERROR", status_code=400, **kwargs)


class QuoteExpiredError(TransactionError):
    """Quote has expired."""

    def __init__(self, quote_id: str = "") -> None:
        super().__init__(
            message="Quote has expired. Please request a new quote.",
            details={"quote_id": quote_id},
        )


class InsufficientFundsError(TransactionError):
    """Insufficient funds for transaction."""

    def __init__(self, required: float = 0, available: float = 0) -> None:
        super().__init__(
            message="Insufficient funds for this transaction.",
            details={"required": required, "available": available},
        )


class TransactionLimitError(TransactionError):
    """Transaction exceeds KYC tier limits."""

    def __init__(self, limit: float, tier: int) -> None:
        super().__init__(
            message=f"Transaction exceeds your Tier {tier} limit of ₦{limit:,.2f}.",
            details={"limit": limit, "tier": tier},
        )


class DailyLimitError(TransactionError):
    """Daily transaction limit exceeded."""

    def __init__(self, limit: float, used: float) -> None:
        super().__init__(
            message=f"Daily limit exceeded. Limit: ₦{limit:,.2f}, Used: ₦{used:,.2f}.",
            details={"limit": limit, "used": used},
        )


# ===================================================================
# ILP Errors
# ===================================================================

class ILPError(OgakError):
    """ILP protocol error."""

    def __init__(self, message: str, ilp_code: str = "T00", **kwargs: Any) -> None:
        super().__init__(
            message, code="ILP_ERROR", status_code=502, details={"ilp_code": ilp_code}, **kwargs
        )


class ILPRejectError(ILPError):
    """ILP packet was rejected."""

    def __init__(self, ilp_code: str, triggered_by: str, message: str = "") -> None:
        super().__init__(
            message=message or f"ILP packet rejected: {ilp_code}",
            ilp_code=ilp_code,
            details={"ilp_code": ilp_code, "triggered_by": triggered_by},
        )


class ILPTimeoutError(ILPError):
    """ILP packet expired."""

    def __init__(self) -> None:
        super().__init__(
            message="ILP packet expired before fulfillment.",
            ilp_code="R00",
        )


class ILPInsufficientLiquidityError(ILPError):
    """Insufficient liquidity in ILP connector."""

    def __init__(self, required: int = 0, available: int = 0) -> None:
        super().__init__(
            message="Insufficient liquidity for this transfer.",
            ilp_code="T04",
            details={"required": required, "available": available},
        )


# ===================================================================
# Integration Errors
# ===================================================================

class BankAPIError(OgakError):
    """Bank/payment provider API error."""

    def __init__(self, provider: str, message: str, **kwargs: Any) -> None:
        super().__init__(
            message=f"{provider} error: {message}",
            code="BANK_API_ERROR",
            status_code=502,
            details={"provider": provider},
            **kwargs,
        )


class ExchangeAPIError(OgakError):
    """Crypto exchange API error."""

    def __init__(self, exchange: str, message: str, **kwargs: Any) -> None:
        super().__init__(
            message=f"{exchange} error: {message}",
            code="EXCHANGE_API_ERROR",
            status_code=502,
            details={"exchange": exchange},
            **kwargs,
        )


# ===================================================================
# KYC Errors
# ===================================================================

class KYCError(OgakError):
    """KYC/AML related error."""

    def __init__(self, message: str, **kwargs: Any) -> None:
        super().__init__(message, code="KYC_ERROR", status_code=403, **kwargs)


class BVNValidationError(KYCError):
    """BVN validation failed."""

    def __init__(self, reason: str = "BVN could not be verified") -> None:
        super().__init__(message=reason, details={"type": "bvn_validation"})


class SanctionScreenError(KYCError):
    """User flagged during sanction screening."""

    def __init__(self) -> None:
        super().__init__(
            message="Transaction blocked pending compliance review.",
            details={"type": "sanction_screen"},
        )
