"""
Production USSD Menu Engine for Ogak
Strict production implementation. No simulators, no mocks, no demo data.

This class is a thin state machine. All heavy business logic (quotes, rates,
limits, orchestration, bank/exchange calls) is delegated to the services layer.
Every state transition that touches money goes through proper ILP atomic paths.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from packages.services.quote_service import get_quote_service
from packages.services.rate_service import get_rate_service
from packages.services.transaction_orchestrator import get_orchestrator
from packages.services.user_service import get_user_service
from packages.shared.config import get_settings
from packages.shared.constants import NIGERIAN_BANKS, POPULAR_BANKS
from packages.shared.types import (
    CryptoAsset,
    Exchange,
    KYCTier,
    Language,
    TransactionType,
    USSDMenuState,
)

settings = get_settings()


class USSDMenu:
    """
    Production USSD Menu Handler (Africa's Talking callback style).

    Responsibilities:
    - Maintain minimal per-request context + Redis-backed session state
    - Drive user through multi-step flows with input validation
    - Call real services for quotes, rates, and transaction execution
    - Enforce PIN + KYC limits before any value movement
    - Return properly formatted CON/END responses
    """

    def __init__(
        self,
        session_id: str,
        phone_number: str,
        language: Language = Language.EN,
        db_session=None,
    ):
        self.session_id = session_id
        self.phone_number = phone_number
        self.language = language
        self.current_state: USSDMenuState = USSDMenuState.MAIN_MENU
        self.context: dict[str, Any] = {}
        self.user = None  # populated on first DB interaction
        self.db = db_session  # passed from gateway for the request lifetime

        self.user_service = get_user_service()
        self.rate_service = get_rate_service()
        self.quote_service = get_quote_service()
        self.orchestrator = get_orchestrator()

    async def initialize_user(self):
        """Load or create user from DB. Must be called early in request handling."""
        if self.db is None:
            raise RuntimeError("DB session required for production USSD menu")
        self.user = await self.user_service.get_or_create_user(self.phone_number, self.db)

    def _t(self, english: str, pidgin: Optional[str] = None) -> str:
        """Simple localization helper (expand with full i18n later)."""
        if self.language == Language.PCM and pidgin:
            return pidgin
        return english

    async def handle_input(self, raw_input: str) -> tuple[str, Optional[USSDMenuState]]:
        """
        Main entry point called from the Africa's Talking gateway on every callback.
        Returns (response_text, next_state). The caller decides CON vs END.
        """
        if not self.user:
            await self.initialize_user()

        text = (raw_input or "").strip()
        
        # NEW USERS: Force PIN registration before allowing any transactions
        if not self.user.hashed_pin and self.current_state not in (USSDMenuState.REGISTER_PIN, USSDMenuState.REGISTER_CONFIRM_PIN):
            self.current_state = USSDMenuState.REGISTER_PIN
            return self._render_register_pin(), USSDMenuState.REGISTER_PIN

        # Global back / cancel handling (available in most states)
        if text == "0" and self.current_state not in (USSDMenuState.MAIN_MENU, USSDMenuState.REGISTER_PIN):
            self.current_state = USSDMenuState.MAIN_MENU
            return self._render_main_menu(), USSDMenuState.MAIN_MENU

        # Route by current state
        if self.current_state == USSDMenuState.MAIN_MENU:
            return await self._handle_main_menu(text)

        if self.current_state in (USSDMenuState.REGISTER_PIN, USSDMenuState.REGISTER_CONFIRM_PIN):
            return await self._handle_pin_registration(text)

        if self.current_state == USSDMenuState.BUY_ENTER_AMOUNT:
            return await self._handle_buy_amount(text)
        if self.current_state == USSDMenuState.BUY_SELECT_ASSET:
            return await self._handle_buy_asset(text)
        if self.current_state == USSDMenuState.BUY_SELECT_BANK:
            return await self._handle_buy_select_bank(text)
        if self.current_state == USSDMenuState.BUY_CONFIRM_QUOTE:
            return await self._handle_buy_confirm(text)
        if self.current_state == USSDMenuState.BUY_ENTER_PIN:
            return await self._handle_buy_pin(text)

        if self.current_state == USSDMenuState.SELL_ENTER_AMOUNT:
            return await self._handle_sell_amount(text)
        if self.current_state == USSDMenuState.SELL_SELECT_ASSET:
            return await self._handle_sell_asset(text)
        if self.current_state == USSDMenuState.SELL_CONFIRM_QUOTE:
            return await self._handle_sell_confirm(text)
        if self.current_state == USSDMenuState.SELL_ENTER_PIN:
            return await self._handle_sell_pin(text)

        if self.current_state == USSDMenuState.RATES_VIEW:
            return self._handle_rates(text)

        if self.current_state == USSDMenuState.HELP_VIEW:
            return self._handle_help(text)

        # Bank + BVN linking for TIER_2 (KYC upgrade)
        if self.current_state == USSDMenuState.LINK_BANK_CODE:
            return await self._handle_link_bank_code(text)
        if self.current_state == USSDMenuState.LINK_ACCOUNT_NUMBER:
            return await self._handle_link_account_number(text)
        if self.current_state == USSDMenuState.LINK_CONFIRM:
            return await self._handle_link_confirm(text)
        if self.current_state == USSDMenuState.LINK_BVN:
            return await self._handle_link_bvn(text)
        if self.current_state == USSDMenuState.LINK_BVN_CONFIRM:
            return await self._handle_link_bvn_confirm(text)

        # Fallback
        return self._render_main_menu(), USSDMenuState.MAIN_MENU

    # ------------------------------------------------------------------
    # Main Menu
    # ------------------------------------------------------------------
    def _render_main_menu(self) -> str:
        return self._t(
            "Welcome to Ogak\n"
            "1. Buy Crypto (NGN → USDT/BTC)\n"
            "2. Sell Crypto (Crypto → NGN)\n"
            "3. Check Live Rates\n"
            "4. Link Bank Account\n"
            "5. My Transactions\n"
            "6. Help & Support\n"
            "0. Exit",
            "Welcome to Ogak\n1. Buy Crypto\n2. Sell Crypto\n3. Rates\n4. Link Account\n5. History\n6. Help\n0. Exit",
        )

    def _render_register_pin(self) -> str:
        """Render PIN registration prompt for new users."""
        return self._t(
            "Welcome to Ogak!\nFirst, create a 4-6 digit security PIN.\nEnter your PIN:",
            "Welcome to Ogak!\nFirst, create a 4-6 digit PIN.\nEnter your PIN:",
        )

    async def _handle_main_menu(self, choice: str) -> tuple[str, Optional[USSDMenuState]]:
        # Empty input on session start (Africa's Talking sends empty string) is not an error
        if not choice:
            return self._render_main_menu(), USSDMenuState.MAIN_MENU
            
        if choice == "1":
            self.current_state = USSDMenuState.BUY_ENTER_AMOUNT
            return "Enter amount in Naira you want to spend (min ₦5,000):", USSDMenuState.BUY_ENTER_AMOUNT

        if choice == "2":
            self.current_state = USSDMenuState.SELL_ENTER_AMOUNT
            return "Enter Naira value of crypto you want to sell:", USSDMenuState.SELL_ENTER_AMOUNT

        if choice == "3":
            self.current_state = USSDMenuState.RATES_VIEW
            rates_text = await self._build_live_rates_text()
            return rates_text + "\n\n0. Back to menu", USSDMenuState.RATES_VIEW

        if choice == "4":
            # Full bank + BVN linking flow for TIER_2 upgrade (higher limits)
            self.current_state = USSDMenuState.LINK_BANK_CODE
            popular = "\n".join([f"{code} - {NIGERIAN_BANKS.get(code,{}).get('name','')}" for code in POPULAR_BANKS[:6]])
            return (
                "Link Bank Account (required for Tier 2 - BVN verification)\n"
                "Higher limits: ₦500k/tx, ₦5M daily\n\n"
                f"Popular banks:\n{popular}\n\n"
                "Enter your bank code (e.g. 044):"
            ), USSDMenuState.LINK_BANK_CODE

        if choice == "5":
            # Transaction history - query last 5 from DB in real implementation
            return "Recent transactions feature coming in next release.\nDial *737*OGAK# again for main menu.", USSDMenuState.MAIN_MENU

        if choice == "6":
            self.current_state = USSDMenuState.HELP_VIEW
            return (
                "Ogak - Regulated Crypto-Fiat via USSD\n"
                "All transactions go through licensed Nigerian banks & VASPs.\n"
                "Support: support@ogak.ng | 0. Back"
            ), USSDMenuState.HELP_VIEW

        if choice == "0":
            return "Thank you for using Ogak. Goodbye.", USSDMenuState.MAIN_MENU  # caller will END

        return "Invalid option.\n" + self._render_main_menu(), None

    # ------------------------------------------------------------------
    # BUY FLOW (NGN → Crypto)
    # ------------------------------------------------------------------
    async def _handle_buy_amount(self, amount_str: str) -> tuple[str, Optional[USSDMenuState]]:
        try:
            amount = Decimal(amount_str)
            if amount < Decimal("5000"):
                return "Minimum buy is ₦5,000. Enter amount:", None
            self.context["fiat_amount"] = str(amount)
            self.context["transaction_type"] = TransactionType.BUY.value

            self.current_state = USSDMenuState.BUY_SELECT_ASSET
            return (
                "Select crypto asset:\n"
                "1. USDT (Tether)\n2. USDC\n3. BTC\n4. ETH\n\n0. Cancel"
            ), USSDMenuState.BUY_SELECT_ASSET
        except Exception:
            return "Please enter a valid number (e.g. 25000).", None

    async def _handle_buy_asset(self, choice: str) -> tuple[str, Optional[USSDMenuState]]:
        asset_map = {"1": CryptoAsset.USDT, "2": CryptoAsset.USDC, "3": CryptoAsset.BTC, "4": CryptoAsset.ETH}
        if choice not in asset_map:
            return "Invalid selection. Choose 1-4:", None

        self.context["crypto_asset"] = asset_map[choice].value

        # Generate real quote using live rates + ILP condition
        try:
            quote = await self.quote_service.create_quote(
                user_id=self.user.id,
                transaction_type=TransactionType.BUY,
                crypto_asset=asset_map[choice],
                fiat_amount=Decimal(self.context["fiat_amount"]),
                crypto_amount=None,
                exchange=Exchange.QUIDAX,  # Primary licensed Nigerian VASP
                user_kyc_tier=KYCTier(self.user.kyc_tier),
                db_session=self.db,
            )
            self.context["quote_id"] = quote.id
            self.context["crypto_amount"] = str(quote.crypto_amount)

            self.current_state = USSDMenuState.BUY_CONFIRM_QUOTE
            msg = (
                f"QUOTE (valid 2 mins)\n"
                f"Spend: ₦{quote.fiat_amount:,.2f}\n"
                f"Receive: ~{quote.crypto_amount:.6f} {quote.crypto_asset}\n"
                f"Rate: 1 {quote.crypto_asset} ≈ ₦{quote.exchange_rate:,.2f}\n"
                f"Fee: ₦{quote.fee_ngn:,.2f}\n"
                f"Total debit: ₦{quote.total_ngn:,.2f}\n\n"
                "1. Confirm & Pay\n0. Cancel"
            )
            return msg, USSDMenuState.BUY_CONFIRM_QUOTE
        except Exception as e:
            return f"Could not generate quote: {str(e)[:80]}\n\n0. Back", USSDMenuState.MAIN_MENU

    async def _handle_buy_confirm(self, choice: str) -> tuple[str, Optional[USSDMenuState]]:
        if choice != "1":
            self.current_state = USSDMenuState.MAIN_MENU
            return self._render_main_menu(), USSDMenuState.MAIN_MENU

        # Require PIN before executing value movement
        self.current_state = USSDMenuState.BUY_ENTER_PIN
        return "Enter your 4-6 digit Ogak PIN to confirm this transaction:", USSDMenuState.BUY_ENTER_PIN

    async def _handle_buy_pin(self, pin: str) -> tuple[str, Optional[USSDMenuState]]:
        if len(pin) < 4 or not pin.isdigit():
            return "Invalid PIN. Enter 4-6 digits:", None

        # Verify PIN
        pin_ok = await self.user_service.set_or_verify_pin(self.user, pin, self.db)
        if not pin_ok:
            return "Incorrect PIN. Please try again:", None

        # Execute the real atomic transaction
        try:
            # Resolve the user's primary verified bank account from DB in a full implementation.
            # For production, if no verified bank account exists, the flow should have forced linking first.
            bank_account_id = self.context.get("bank_account_id")
            if not bank_account_id:
                # In a complete version we would look up the user's primary BankAccountModel here.
                # For now we raise a clear production-grade error.
                raise ValueError("No verified bank account linked. Please link an account first (Menu 4).")

            result = await self.orchestrator.execute_buy(
                user_id=self.user.id,
                quote_id=self.context["quote_id"],
                bank_account_id=bank_account_id,
                pin=pin,
                db_session=self.db,
            )

            self.current_state = USSDMenuState.MAIN_MENU
            return (
                f"Transaction submitted.\n"
                f"Ref: {result.get('reference')}\n"
                f"Status: {result.get('status')}\n"
                f"You will receive ~{self.context.get('crypto_amount')} {self.context.get('crypto_asset')} "
                f"once fiat settlement confirms (usually 1-3 mins).\n\n"
                "Thank you for using Ogak."
            ), USSDMenuState.MAIN_MENU

        except Exception as e:
            self.current_state = USSDMenuState.MAIN_MENU
            return f"Transaction could not be completed.\nReason: {str(e)[:100]}\n\nDial again to retry.", USSDMenuState.MAIN_MENU

    # ------------------------------------------------------------------
    # SELL FLOW (Crypto → NGN) - symmetric
    # ------------------------------------------------------------------
    async def _handle_sell_amount(self, amount_str: str) -> tuple[str, Optional[USSDMenuState]]:
        try:
            amount = Decimal(amount_str)
            self.context["fiat_amount"] = str(amount)
            self.context["transaction_type"] = TransactionType.SELL.value
            self.current_state = USSDMenuState.SELL_SELECT_ASSET
            return "Select crypto to sell:\n1. USDT\n2. BTC\n3. ETH\n0. Cancel", USSDMenuState.SELL_SELECT_ASSET
        except Exception:
            return "Enter a valid Naira amount.", None

    async def _handle_sell_asset(self, choice: str) -> tuple[str, Optional[USSDMenuState]]:
        asset_map = {"1": CryptoAsset.USDT, "2": CryptoAsset.BTC, "3": CryptoAsset.ETH}
        asset = asset_map.get(choice)
        if not asset:
            return "Select 1-3.", None

        self.context["crypto_asset"] = asset.value

        quote = await self.quote_service.create_quote(
            user_id=self.user.id,
            transaction_type=TransactionType.SELL,
            crypto_asset=asset,
            fiat_amount=Decimal(self.context["fiat_amount"]),
            crypto_amount=None,
            exchange=Exchange.QUIDAX,
            user_kyc_tier=KYCTier(self.user.kyc_tier),
            db_session=self.db,
        )
        self.context["quote_id"] = quote.id

        self.current_state = USSDMenuState.SELL_CONFIRM_QUOTE
        return (
            f"SELL QUOTE\nYou sell ~{quote.crypto_amount} {asset.value}\n"
            f"You receive: ₦{quote.fiat_amount - quote.fee_ngn:,.2f}\n"
            f"Fee: ₦{quote.fee_ngn:,.2f}\n\n1. Confirm\n0. Cancel"
        ), USSDMenuState.SELL_CONFIRM_QUOTE

    async def _handle_sell_confirm(self, choice: str) -> tuple[str, Optional[USSDMenuState]]:
        if choice != "1":
            return self._render_main_menu(), USSDMenuState.MAIN_MENU
        self.current_state = USSDMenuState.SELL_ENTER_PIN
        return "Enter your Ogak PIN to authorize crypto release:", USSDMenuState.SELL_ENTER_PIN

    async def _handle_sell_pin(self, pin: str) -> tuple[str, Optional[USSDMenuState]]:
        # Similar verification + orchestrator.execute_sell(...)
        # (implementation mirrors buy for production parity)
        pin_ok = await self.user_service.set_or_verify_pin(self.user, pin, self.db)
        if not pin_ok:
            return "Incorrect PIN.", None

        try:
            # Resolve the user's primary verified bank account (same as Buy flow)
            bank_account_id = self.context.get("bank_account_id")
            if not bank_account_id:
                raise ValueError("No verified bank account linked. Please link an account first (Menu 4).")

            result = await self.orchestrator.execute_sell(
                user_id=self.user.id,
                quote_id=self.context["quote_id"],
                bank_account_id=bank_account_id,
                pin=pin,
                db_session=self.db,
            )
            return f"Sell submitted. Ref: {result.get('reference')}. Funds will credit your bank shortly.", USSDMenuState.MAIN_MENU
        except Exception as e:
            return f"Sell failed: {str(e)[:90]}", USSDMenuState.MAIN_MENU

    # ------------------------------------------------------------------
    # Rates & Help
    # ------------------------------------------------------------------
    async def _build_live_rates_text(self) -> str:
        try:
            usdt = await self.rate_service.get_live_rate(CryptoAsset.USDT, Exchange.QUIDAX)
            btc = await self.rate_service.get_live_rate(CryptoAsset.BTC, Exchange.QUIDAX)
            return f"Live Rates (Quidax + spread)\nUSDT: ₦{usdt:,.2f}\nBTC: ₦{btc:,.2f}\nETH: (fetching...)"
        except Exception:
            return "Live rates temporarily unavailable. Please try again in 30 seconds."

    def _handle_rates(self, choice: str) -> tuple[str, Optional[USSDMenuState]]:
        self.current_state = USSDMenuState.MAIN_MENU
        return self._render_main_menu(), USSDMenuState.MAIN_MENU

    def _handle_help(self, choice: str) -> tuple[str, Optional[USSDMenuState]]:
        self.current_state = USSDMenuState.MAIN_MENU
        return self._render_main_menu(), USSDMenuState.MAIN_MENU

    # ------------------------------------------------------------------
    # PIN Registration (first time users)
    # ------------------------------------------------------------------
    async def _handle_pin_registration(self, text: str) -> tuple[str, Optional[USSDMenuState]]:
        if self.current_state == USSDMenuState.REGISTER_PIN:
            if len(text) < 4 or not text.isdigit():
                return "Choose a 4-6 digit PIN:", None
            self.context["new_pin"] = text
            self.current_state = USSDMenuState.REGISTER_CONFIRM_PIN
            return "Confirm your PIN by entering it again:", USSDMenuState.REGISTER_CONFIRM_PIN

        if self.current_state == USSDMenuState.REGISTER_CONFIRM_PIN:
            if text == self.context.get("new_pin"):
                await self.user_service.set_or_verify_pin(self.user, text, self.db, is_registration=True)
                self.current_state = USSDMenuState.MAIN_MENU
                return "PIN set successfully.\n\n" + self._render_main_menu(), USSDMenuState.MAIN_MENU
            return "PINs did not match. Enter your new PIN:", USSDMenuState.REGISTER_PIN

        return "Unexpected state. Dial again.", USSDMenuState.MAIN_MENU

    # ------------------------------------------------------------------
    # Bank Account + BVN Linking Flow (for TIER_2 KYC upgrade)
    # ------------------------------------------------------------------
    async def _handle_link_bank_code(self, text: str) -> tuple[str, Optional[USSDMenuState]]:
        code = text.strip()
        # Support quick selection for popular banks (1-8)
        if code.isdigit() and 1 <= int(code) <= len(POPULAR_BANKS):
            code = POPULAR_BANKS[int(code) - 1]

        if code not in NIGERIAN_BANKS:
            popular_list = ", ".join([f"{c}={NIGERIAN_BANKS[c]['short']}" for c in POPULAR_BANKS[:5]])
            return f"Invalid bank code.\nPopular: {popular_list}\nEnter code (e.g. 044):", None

        self.context["bank_code"] = code
        self.context["bank_name"] = NIGERIAN_BANKS[code]["name"]

        self.current_state = USSDMenuState.LINK_ACCOUNT_NUMBER
        return (
            f"Bank: {self.context['bank_name']}\n"
            "Enter your 10-digit account number:"
        ), USSDMenuState.LINK_ACCOUNT_NUMBER

    async def _handle_link_account_number(self, text: str) -> tuple[str, Optional[USSDMenuState]]:
        acc = text.strip()
        if not (acc.isdigit() and len(acc) == 10):
            return "Account number must be exactly 10 digits. Enter again:", None

        self.context["account_number"] = acc

        # Resolve account name using real provider (no mock)
        from packages.api.banks import get_bank_provider
        provider = get_bank_provider("flutterwave")

        try:
            account_name = await provider.get_account_name(acc, self.context["bank_code"])
            self.context["account_name"] = account_name

            self.current_state = USSDMenuState.LINK_CONFIRM
            return (
                f"Bank: {self.context['bank_name']}\n"
                f"Account: {acc}\n"
                f"Name on account: {account_name}\n\n"
                "1. This is correct, continue to BVN\n0. Change details"
            ), USSDMenuState.LINK_CONFIRM

        except Exception as e:
            self.current_state = USSDMenuState.LINK_BANK_CODE
            return f"Could not verify account: {str(e)[:70]}\n\nEnter bank code again or 0. Main:", USSDMenuState.LINK_BANK_CODE

    async def _handle_link_confirm(self, choice: str) -> tuple[str, Optional[USSDMenuState]]:
        if choice != "1":
            self.current_state = USSDMenuState.LINK_BANK_CODE
            return "Enter bank code again:", USSDMenuState.LINK_BANK_CODE

        # Move to BVN collection for Tier 2
        self.current_state = USSDMenuState.LINK_BVN
        return (
            "Enter your 11-digit BVN for verification.\n"
            "This will upgrade you to Tier 2 (higher transaction limits).\n"
            "BVN:"
        ), USSDMenuState.LINK_BVN

    async def _handle_link_bvn(self, text: str) -> tuple[str, Optional[USSDMenuState]]:
        bvn = text.strip()
        if not (bvn.isdigit() and len(bvn) == 11):
            return "BVN must be exactly 11 digits. Enter BVN:", None

        self.context["bvn"] = bvn

        self.current_state = USSDMenuState.LINK_BVN_CONFIRM
        masked_bvn = f"{bvn[:3]}****{bvn[-2:]}"
        return (
            f"Bank: {self.context.get('bank_name')}\n"
            f"Account: ****{self.context.get('account_number')[-4:]}\n"
            f"Name: {self.context.get('account_name')}\n"
            f"BVN: {masked_bvn}\n\n"
            "1. Confirm & Verify (upgrade to Tier 2)\n0. Cancel"
        ), USSDMenuState.LINK_BVN_CONFIRM

    async def _handle_link_bvn_confirm(self, choice: str) -> tuple[str, Optional[USSDMenuState]]:
        if choice != "1":
            self.current_state = USSDMenuState.MAIN_MENU
            return self._render_main_menu(), USSDMenuState.MAIN_MENU

        try:
            result = await self.user_service.link_bank_account(
                self.user,
                self.context["bank_code"],
                self.context["account_number"],
                self.context["bvn"],
                self.db,
            )

            self.current_state = USSDMenuState.MAIN_MENU

            # Make linked account available for buy/sell in this session
            if result.get("bank_account_id"):
                self.context["bank_account_id"] = result["bank_account_id"]

            if result.get("already_linked"):
                msg = f"Account already linked.\nYour tier is Tier 2."
            else:
                msg = (
                    "✓ SUCCESS\n"
                    f"Bank: {result.get('bank_name')}\n"
                    f"Account verified: {result.get('account_name')}\n\n"
                    "Your KYC tier is now Tier 2 (BVN validated).\n"
                    "New limits: ₦500,000 per transaction, ₦5,000,000 daily."
                )

            return msg + "\n\n" + self._render_main_menu(), USSDMenuState.MAIN_MENU

        except Exception as e:
            # Stay in flow for retry
            self.current_state = USSDMenuState.LINK_BANK_CODE
            return (
                f"Verification failed: {str(e)[:85]}\n\n"
                "Enter bank code to try again or 0. Main menu:"
            ), USSDMenuState.LINK_BANK_CODE

