"""
Ogak Configuration
Centralized settings management using Pydantic Settings.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ----- Application -----
    app_name: str = "ogak-ussd"
    app_env: str = "development"
    app_debug: bool = True
    app_secret_key: str = "change-this-in-production"
    app_encryption_key: str = "change-this-in-production"

    # ----- Ports -----
    ussd_port: int = 8000
    api_port: int = 8001
    ilp_port: int = 8002
    admin_port: int = 8003

    # ----- PostgreSQL -----
    database_url: str = "postgresql+asyncpg://ogak:ogak_secret@localhost:5432/ogak_db"
    database_sync_url: str = "postgresql://ogak:ogak_secret@localhost:5432/ogak_db"

    # ----- Redis -----
    redis_url: str = "redis://localhost:6379/0"
    redis_session_db: int = 1
    redis_cache_db: int = 2

    # ----- Africa's Talking -----
    at_username: str = ""
    at_api_key: str = ""
    at_ussd_shortcode: str = "*737*OGAK#"
    at_sms_shortcode: str = "OGAK"
    at_environment: str = "production"  # Must be "production" for live shortcode

    # ----- Flutterwave -----
    flw_public_key: str = ""
    flw_secret_key: str = ""
    flw_encryption_key: str = ""
    flw_webhook_secret: str = ""
    flw_base_url: str = "https://api.flutterwave.com/v3"

    # ----- Paystack -----
    paystack_secret_key: str = ""
    paystack_public_key: str = ""
    paystack_webhook_secret: str = ""
    paystack_base_url: str = "https://api.paystack.co"

    # ----- Quidax -----
    quidax_secret_key: str = ""
    quidax_base_url: str = "https://www.quidax.com/api/v1"
    quidax_webhook_secret: str = ""

    # ----- Busha -----
    busha_api_key: str = ""
    busha_secret_key: str = ""
    busha_base_url: str = "https://api.busha.co/v2"
    busha_webhook_secret: str = ""

    # ----- Binance -----
    binance_api_key: str = ""
    binance_secret_key: str = ""
    binance_base_url: str = "https://api.binance.com/api/v3"

    # ----- ILP Connector -----
    ilp_connector_address: str = "g.ogak.ng.connector"
    ilp_connector_secret: str = "change-this-in-production"
    ilp_max_packet_amount: int = 10_000_000_00
    ilp_route_expiry_ms: int = 30_000
    ilp_default_spread_bps: int = 150

    # ----- KYC/AML Limits -----
    kyc_tier1_tx_limit_ngn: int = 50_000
    kyc_tier1_daily_limit_ngn: int = 500_000
    kyc_tier2_tx_limit_ngn: int = 500_000
    kyc_tier2_daily_limit_ngn: int = 5_000_000
    kyc_tier3_tx_limit_ngn: int = 5_000_000
    kyc_tier3_daily_limit_ngn: int = 50_000_000
    bvn_validation_provider: str = "flutterwave"

    # ----- USSD Session -----
    ussd_session_ttl_seconds: int = 180
    ussd_max_pin_attempts: int = 3
    ussd_pin_lockout_seconds: int = 1800

    # ----- Rate Engine -----
    rate_cache_ttl_seconds: int = 30
    rate_quote_expiry_seconds: int = 120
    rate_spread_bps: int = 150

    # ----- Celery -----
    celery_broker_url: str = "redis://localhost:6379/3"
    celery_result_backend: str = "redis://localhost:6379/4"

    # ----- Logging -----
    log_level: str = "INFO"
    log_format: str = "json"
    log_file: Optional[str] = None

    # ----- CORS -----
    cors_origins: str = "http://localhost:3000,http://localhost:8003"

    # ----- Open Payments (public base for wallet addresses, auth & resource servers) -----
    # Used when constructing walletAddress.id, authServer, resourceServer in responses.
    # Set this to your publicly reachable base (e.g. https://api.ogak.ng) in production.
    # Include scheme, no trailing slash. Falls back to http://localhost:8001 for local dev.
    op_public_base_url: str = "http://localhost:8001"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",")]

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() in ("production", "prod")

    @property
    def is_development(self) -> bool:
        return not self.is_production


@lru_cache()
def get_settings() -> Settings:
    """Get cached application settings."""
    return Settings()
