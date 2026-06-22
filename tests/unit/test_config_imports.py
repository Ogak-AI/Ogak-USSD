"""
Tests for config imports and settings
Ensures all main modules can be imported without NameError
"""

import pytest


class TestConfigImports:
    """Test that config imports work correctly in all main modules"""
    
    @pytest.mark.unit
    def test_ussd_main_imports(self):
        """Test that ussd/main.py imports successfully"""
        try:
            from packages.ussd.main import app, settings
            assert app is not None
            assert settings is not None
            assert hasattr(settings, 'cors_origins_list')
        except NameError as e:
            pytest.fail(f"Import error in ussd/main.py: {e}")

    @pytest.mark.unit
    def test_api_main_imports(self):
        """Test that api/main.py imports successfully"""
        try:
            from packages.api.main import app, settings
            assert app is not None
            assert settings is not None
            assert hasattr(settings, 'app_env')
            assert hasattr(settings, 'log_level')
        except NameError as e:
            pytest.fail(f"Import error in api/main.py: {e}")

    @pytest.mark.unit
    def test_banks_module_imports(self):
        """Test that banks.py imports and initializes correctly"""
        try:
            from packages.api.banks import PaystackProvider, FlutterwaveProvider
            paystack = PaystackProvider()
            assert paystack.secret_key is not None
            flutterwave = FlutterwaveProvider()
            assert flutterwave.secret_key is not None
        except AttributeError as e:
            pytest.fail(f"Config attribute error in banks.py: {e}")

    @pytest.mark.unit
    def test_exchanges_module_imports(self):
        """Test that exchanges.py imports and initializes correctly"""
        try:
            from packages.api.exchanges import BinanceProvider, QuidaxProvider
            binance = BinanceProvider()
            assert binance.api_key is not None
            quidax = QuidaxProvider()
            assert quidax.api_key is not None
        except AttributeError as e:
            pytest.fail(f"Config attribute error in exchanges.py: {e}")

    @pytest.mark.unit
    def test_settings_has_required_attributes(self):
        """Test that Settings object has all required attributes"""
        from packages.shared.config import get_settings
        settings = get_settings()
        
        required_attrs = [
            'cors_origins_list',
            'app_env',
            'log_level',
            'paystack_secret_key',
            'flw_secret_key',
            'binance_api_key',
            'binance_secret_key',
            'quidax_secret_key',
        ]
        
        for attr in required_attrs:
            assert hasattr(settings, attr), f"Settings missing attribute: {attr}"
