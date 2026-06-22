"""
Banking Integration Layer
Handles Nigerian bank APIs, NIP/NIBSS, Paystack, Flutterwave integrations.
"""

import logging
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Optional

import httpx

from packages.shared.config import get_settings
from packages.shared.errors import ExternalServiceError
from packages.shared.types import BankAccountModel

logger = logging.getLogger(__name__)


class BankProvider(ABC):
    """Abstract bank provider."""
    
    @abstractmethod
    async def verify_account(
        self,
        account_number: str,
        bank_code: str,
        bvn: Optional[str] = None,
    ) -> dict:
        """Verify bank account details."""
        pass
    
    @abstractmethod
    async def get_account_name(
        self,
        account_number: str,
        bank_code: str,
    ) -> str:
        """Resolve account name."""
        pass
    
    @abstractmethod
    async def initiate_debit(
        self,
        account_number: str,
        bank_code: str,
        amount: Decimal,
        reference: str,
        narration: str,
    ) -> dict:
        """Initiate account debit (for buy crypto)."""
        pass
    
    @abstractmethod
    async def initiate_credit(
        self,
        account_number: str,
        bank_code: str,
        amount: Decimal,
        reference: str,
        narration: str,
    ) -> dict:
        """Initiate account credit (for sell crypto)."""
        pass
    
    @abstractmethod
    async def get_transaction_status(self, reference: str) -> dict:
        """Check transaction status."""
        pass


class PaystackProvider(BankProvider):
    """Paystack bank integration."""
    
    def __init__(self):
        settings = get_settings()
        self.secret_key = settings.paystack_secret_key
        self.base_url = "https://api.paystack.co"
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {self.secret_key}"},
            timeout=30.0,
        )
    
    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()
    
    async def verify_account(
        self,
        account_number: str,
        bank_code: str,
        bvn: Optional[str] = None,
    ) -> dict:
        """Verify account using Paystack."""
        try:
            response = await self.client.get(
                "/bank/resolve",
                params={
                    "account_number": account_number,
                    "bank_code": bank_code,
                }
            )
            response.raise_for_status()
            data = response.json()
            
            if not data.get("status"):
                raise ValueError(f"Account verification failed: {data.get('message')}")
            
            return {
                "account_number": account_number,
                "bank_code": bank_code,
                "account_name": data["data"]["account_name"],
                "verified": True,
            }
        
        except Exception as e:
            logger.error(f"Paystack account verification failed: {str(e)}")
            raise ExternalServiceError("Paystack", str(e))
    
    async def get_account_name(
        self,
        account_number: str,
        bank_code: str,
    ) -> str:
        """Resolve account name."""
        result = await self.verify_account(account_number, bank_code)
        return result["account_name"]
    
    async def initiate_debit(
        self,
        account_number: str,
        bank_code: str,
        amount: Decimal,
        reference: str,
        narration: str,
    ) -> dict:
        """Initiate debit using Paystack."""
        # Create recipient first
        recipient = await self._create_recipient(account_number, bank_code)
        
        # Initiate transfer
        try:
            response = await self.client.post(
                "/transfer",
                json={
                    "source": "balance",
                    "recipient": recipient["id"],
                    "amount": int(amount * 100),  # Paystack expects cents
                    "reference": reference,
                    "reason": narration,
                }
            )
            response.raise_for_status()
            data = response.json()
            
            return {
                "reference": reference,
                "paystack_reference": data["data"]["reference"],
                "status": "initiated",
                "amount": amount,
            }
        
        except Exception as e:
            logger.error(f"Paystack debit initiation failed: {str(e)}")
            raise ExternalServiceError("Paystack", str(e))
    
    async def initiate_credit(
        self,
        account_number: str,
        bank_code: str,
        amount: Decimal,
        reference: str,
        narration: str,
    ) -> dict:
        """Initiate credit (transfer) to account."""
        # Similar to debit but recipient is user's account
        return await self.initiate_debit(
            account_number, bank_code, amount, reference, narration
        )
    
    async def get_transaction_status(self, reference: str) -> dict:
        """Check transfer status."""
        try:
            response = await self.client.get(
                f"/transfer/verify/{reference}"
            )
            response.raise_for_status()
            data = response.json()
            
            return {
                "reference": reference,
                "status": data["data"]["status"],
                "amount": Decimal(str(data["data"]["amount"])) / 100,
            }
        
        except Exception as e:
            logger.error(f"Paystack status check failed: {str(e)}")
            raise ExternalServiceError("Paystack", str(e))
    
    async def _create_recipient(self, account_number: str, bank_code: str) -> dict:
        """Create a recipient in Paystack for transfers."""
        try:
            # First, verify account
            verification = await self.verify_account(account_number, bank_code)
            
            # Create recipient
            response = await self.client.post(
                "/transferrecipient",
                json={
                    "type": "nuban",
                    "name": verification["account_name"],
                    "account_number": account_number,
                    "bank_code": bank_code,
                    "currency": "NGN",
                }
            )
            response.raise_for_status()
            data = response.json()
            
            return {
                "id": data["data"]["recipient_code"],
                "account_number": account_number,
            }
        
        except Exception as e:
            logger.error(f"Paystack recipient creation failed: {str(e)}")
            raise ExternalServiceError("Paystack", str(e))


class FlutterwaveProvider(BankProvider):
    """Flutterwave bank integration."""
    
    def __init__(self):
        settings = get_settings()
        self.secret_key = settings.flw_secret_key
        self.base_url = "https://api.flutterwave.com/v3"
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {self.secret_key}"},
            timeout=30.0,
        )
    
    async def close(self):
        await self.client.aclose()
    
    async def verify_account(
        self,
        account_number: str,
        bank_code: str,
        bvn: Optional[str] = None,
    ) -> dict:
        """Verify account using Flutterwave."""
        try:
            response = await self.client.post(
                "/accounts/resolve",
                json={
                    "account_number": account_number,
                    "bank_code": bank_code,
                }
            )
            response.raise_for_status()
            data = response.json()
            
            if not data.get("status") == "success":
                raise ValueError(f"Account verification failed: {data.get('message')}")
            
            return {
                "account_number": account_number,
                "bank_code": bank_code,
                "account_name": data["data"]["account_name"],
                "verified": True,
            }
        
        except Exception as e:
            logger.error(f"Flutterwave account verification failed: {str(e)}")
            raise ExternalServiceError("Flutterwave", str(e))
    
    async def get_account_name(
        self,
        account_number: str,
        bank_code: str,
    ) -> str:
        """Resolve account name."""
        result = await self.verify_account(account_number, bank_code)
        return result["account_name"]
    
    async def initiate_debit(
        self,
        account_number: str,
        bank_code: str,
        amount: Decimal,
        reference: str,
        narration: str,
    ) -> dict:
        """Initiate debit (charge) via Flutterwave."""
        try:
            response = await self.client.post(
                "/charges?type=account",
                json={
                    "account_bank": bank_code,
                    "account_number": account_number,
                    "amount": str(amount),
                    "currency": "NGN",
                    "tx_ref": reference,
                    "narration": narration,
                }
            )
            response.raise_for_status()
            data = response.json()
            
            return {
                "reference": reference,
                "flutterwave_reference": data["data"]["flw_ref"],
                "status": "initiated",
                "amount": amount,
            }
        
        except Exception as e:
            logger.error(f"Flutterwave debit initiation failed: {str(e)}")
            raise ExternalServiceError("Flutterwave", str(e))
    
    async def initiate_credit(
        self,
        account_number: str,
        bank_code: str,
        amount: Decimal,
        reference: str,
        narration: str,
    ) -> dict:
        """Initiate credit (transfer) to account."""
        try:
            response = await self.client.post(
                "/transfers",
                json={
                    "account_bank": bank_code,
                    "account_number": account_number,
                    "amount": str(amount),
                    "currency": "NGN",
                    "reference": reference,
                    "narration": narration,
                }
            )
            response.raise_for_status()
            data = response.json()
            
            return {
                "reference": reference,
                "flutterwave_reference": data["data"]["reference"],
                "status": "initiated",
                "amount": amount,
            }
        
        except Exception as e:
            logger.error(f"Flutterwave credit initiation failed: {str(e)}")
            raise ExternalServiceError("Flutterwave", str(e))
    
    async def get_transaction_status(self, reference: str) -> dict:
        """Check transfer status."""
        try:
            response = await self.client.get(
                f"/transfers?reference={reference}"
            )
            response.raise_for_status()
            data = response.json()
            
            if not data.get("data"):
                raise ValueError(f"Transfer not found: {reference}")
            
            transfer = data["data"][0]
            return {
                "reference": reference,
                "status": transfer["status"],
                "amount": Decimal(str(transfer["amount"])),
            }
        
        except Exception as e:
            logger.error(f"Flutterwave status check failed: {str(e)}")
            raise ExternalServiceError("Flutterwave", str(e))


def get_bank_provider(provider: str = "paystack") -> BankProvider:
    """Get a bank provider instance."""
    if provider.lower() == "paystack":
        return PaystackProvider()
    elif provider.lower() == "flutterwave":
        return FlutterwaveProvider()
    else:
        raise ValueError(f"Unknown bank provider: {provider}")
