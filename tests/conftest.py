"""
Shared pytest fixtures for Ogak USSD tests
"""

import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def mock_redis():
    """Mock Redis client for testing"""
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock(return_value=True)
    redis.setex = AsyncMock(return_value=True)
    redis.delete = AsyncMock(return_value=True)
    redis.close = AsyncMock(return_value=None)
    return redis


@pytest.fixture
def mock_db_session():
    """Mock SQLAlchemy database session"""
    db = AsyncMock()
    db.execute = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    return db


@pytest.fixture
def mock_user():
    """Mock User model"""
    user = MagicMock()
    user.id = "test-user-123"
    user.phone_number = "+2348012345678"
    user.hashed_pin = "hashed_pin_value"
    user.pin_salt = "salt_value"
    user.kyc_tier = "TIER_1"
    user.is_active = True
    user.locked_until = None
    user.pin_attempts = 0
    return user


@pytest.fixture
def mock_settings():
    """Mock Settings object"""
    settings = MagicMock()
    settings.app_env = "development"
    settings.debug = True
    settings.log_level = "INFO"
    settings.redis_url = "redis://localhost:6379/0"
    settings.cors_origins_list = ["http://localhost:3000"]
    settings.paystack_secret_key = "test_paystack_key"
    settings.flw_secret_key = "test_flutterwave_key"
    settings.binance_api_key = "test_binance_key"
    settings.binance_secret_key = "test_binance_secret"
    settings.quidax_secret_key = "test_quidax_key"
    return settings
