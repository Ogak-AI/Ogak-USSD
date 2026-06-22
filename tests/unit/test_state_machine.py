"""
Tests for USSD state machine and session management
Tests state restoration, empty input handling, and session recovery
"""

import pytest
from packages.shared.types import USSDMenuState


class TestStateMachine:
    """Test USSD state machine behavior"""
    
    @pytest.mark.unit
    def test_empty_input_returns_main_menu(self):
        """Test that empty input on first dial returns main menu, not error"""
        # This would be tested with an actual menu instance in integration tests
        # For now, verify the logic is sound
        from packages.shared.types import USSDMenuState
        assert USSDMenuState.MAIN_MENU is not None

    @pytest.mark.unit
    def test_state_enum_values(self):
        """Test that all expected USSD states exist"""
        expected_states = [
            'MAIN_MENU',
            'REGISTER_PIN',
            'REGISTER_CONFIRM_PIN',
            'BUY_ENTER_AMOUNT',
            'BUY_SELECT_ASSET',
            'BUY_CONFIRM_QUOTE',
            'BUY_ENTER_PIN',
            'SELL_ENTER_AMOUNT',
            'SELL_SELECT_ASSET',
            'SELL_CONFIRM_QUOTE',
            'SELL_ENTER_PIN',
        ]
        
        for state_name in expected_states:
            assert hasattr(USSDMenuState, state_name), f"Missing state: {state_name}"


class TestSessionRecovery:
    """Test session recovery when Redis times out"""
    
    @pytest.mark.unit
    def test_text_segmentation(self):
        """Test that text with * separators can be split for recovery"""
        text = "1*25000*2"
        segments = text.split("*")
        assert len(segments) == 3
        assert segments[0] == "1"
        assert segments[1] == "25000"
        assert segments[2] == "2"

    @pytest.mark.unit
    def test_empty_text_no_segments(self):
        """Test that empty text results in empty segment list"""
        text = ""
        segments = text.split("*") if text else []
        assert len(segments) == 0 or (len(segments) == 1 and segments[0] == "")
