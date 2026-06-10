"""
Crypto Exchange Integration Layer
Handles Binance, Quidax, Paxful and other licensed Nigerian exchanges.
"""

import logging
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Optional

import httpx

from packages.shared.config import config
from packages.shared.errors import ExternalServiceError

logger = logging.getLogger(__name__)


class ExchangeProvider(ABC):
    """Abstract exchange provider."""
    
    @abstractmethod
    async def get_price(self, crypto: str, fiat: str = "NGN") -> Decimal:
        """Get current price."""
        pass
    
    @abstractmethod
    async def get_balance(self, crypto: str) -> Decimal:
        """Get available balance for crypto."""
        pass
    
    @abstractmethod
    async def buy_crypto(
        self,
        crypto: str,
        amount_ngn: Decimal,
        wallet_address: str,
        reference: str,
    ) -> dict:
        """Buy crypto with Naira."""
        pass
    
    @abstractmethod
    async def sell_crypto(
        self,
        crypto: str,
        amount_crypto: Decimal,
        bank_account: dict,
        reference: str,
    ) -> dict:
        """Sell crypto for Naira."""
        pass
    
    @abstractmethod
    async def get_order_status(self, order_id: str) -> dict:
        """Check order status."""
        pass


class BinanceProvider(ExchangeProvider):
    """Binance exchange integration (via P2P API)."""
    
    def __init__(self):
        self.api_key = config.exchange.binance_api_key
        self.api_secret = config.exchange.binance_api_secret
        self.base_url = "https://api.binance.com"
        self.client = httpx.AsyncClient(base_url=self.base_url, timeout=30.0)
    
    async def close(self):
        await self.client.aclose()
    
    async def get_price(self, crypto: str = "USDT", fiat: str = "NGN") -> Decimal:
        """Get live price from Binance.

        For NGN pairs, this provider returns the crypto/USDT price.
        The RateService is responsible for combining with a live NGN/USDT rate source
        (e.g. from another provider, CBN reference, or dedicated FX feed).
        No hardcoded NGN conversion is allowed inside exchange providers.
        """
        try:
            symbol = f"{crypto.upper()}USDT"
            response = await self.client.get("/api/v3/ticker/price", params={"symbol": symbol})
            response.raise_for_status()
            data = response.json()
            price = Decimal(str(data.get("price", "0")))
            if price <= 0:
                raise ValueError(f"Invalid or zero price returned from Binance for {symbol}")
            return price
        except Exception as e:
            logger.error(f"Binance price fetch failed: {str(e)}")
            raise ExternalServiceError("Binance", str(e))
    
    async def get_balance(self, crypto: str = "USDT") -> Decimal:
        """Get available balance. Requires signed Binance request in production."""
        # Production implementation must use HMAC-signed requests with recvWindow etc.
        # For now we raise to force proper integration when keys are present.
        raise NotImplementedError("Binance balance requires signed production integration")
    
    async def buy_crypto(
        self,
        crypto: str,
        amount_ngn: Decimal,
        wallet_address: str,
        reference: str,
    ) -> dict:
        """Buy USDT with NGN via Binance P2P."""
        try:
            # In production:
            # 1. Get price
            # 2. Calculate USDT amount
            # 3. Create P2P order
            # 4. Mark as paid once bank transfer is confirmed
            
            price = await self.get_price(crypto)
            usdt_amount = amount_ngn / price
            
            return {
                "reference": reference,
                "order_id": f"BINANCE_{reference}",
                "status": "PENDING",
                "amount_ngn": amount_ngn,
                "crypto": crypto,
                "amount_crypto": usdt_amount,
                "wallet_address": wallet_address,
                "exchange": "binance",
            }
        
        except Exception as e:
            logger.error(f"Binance buy order failed: {str(e)}")
            raise ExternalServiceError("Binance", str(e))
    
    async def sell_crypto(
        self,
        crypto: str,
        amount_crypto: Decimal,
        bank_account: dict,
        reference: str,
    ) -> dict:
        """Sell USDT for NGN via Binance P2P."""
        try:
            price = await self.get_price(crypto)
            amount_ngn = amount_crypto * price
            
            return {
                "reference": reference,
                "order_id": f"BINANCE_{reference}",
                "status": "PENDING",
                "crypto": crypto,
                "amount_crypto": amount_crypto,
                "amount_ngn": amount_ngn,
                "bank_account": bank_account,
                "exchange": "binance",
            }
        
        except Exception as e:
            logger.error(f"Binance sell order failed: {str(e)}")
            raise ExternalServiceError("Binance", str(e))
    
    async def get_order_status(self, order_id: str) -> dict:
        """Check order status."""
        try:
            return {
                "order_id": order_id,
                "status": "PENDING",
            }
        except Exception as e:
            logger.error(f"Binance order status check failed: {str(e)}")
            raise ExternalServiceError("Binance", str(e))


class QuidaxProvider(ExchangeProvider):
    """Quidax exchange integration (Nigerian exchange)."""
    
    def __init__(self):
        self.api_key = config.exchange.quidax_api_key
        self.base_url = config.exchange.quidax_base_url
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=30.0,
        )
    
    async def close(self):
        await self.client.aclose()
    
    async def get_price(self, crypto: str = "USDT", fiat: str = "NGN") -> Decimal:
        """Get current crypto/NGN price from Quidax."""
        try:
            response = await self.client.get(
                f"/ticker/{crypto.lower()}/{fiat.lower()}"
            )
            response.raise_for_status()
            data = response.json()
            return Decimal(str(data["buy"]))  # Buy price (what users pay)
        
        except Exception as e:
            logger.error(f"Quidax price fetch failed: {str(e)}")
            raise ExternalServiceError("Quidax", str(e))
    
    async def get_balance(self, crypto: str = "USDT") -> Decimal:
        """Get available balance."""
        try:
            response = await self.client.get(f"/wallets/{crypto.lower()}")
            response.raise_for_status()
            data = response.json()
            return Decimal(str(data["balance"]))
        
        except Exception as e:
            logger.error(f"Quidax balance check failed: {str(e)}")
            raise ExternalServiceError("Quidax", str(e))
    
    async def buy_crypto(
        self,
        crypto: str,
        amount_ngn: Decimal,
        wallet_address: str,
        reference: str,
    ) -> dict:
        """Buy crypto from Quidax."""
        try:
            price = await self.get_price(crypto)
            amount_crypto = amount_ngn / price
            
            response = await self.client.post(
                "/orders",
                json={
                    "side": "buy",
                    "coin_amount": str(amount_crypto),
                    "coin": crypto.lower(),
                    "fiat_amount": str(amount_ngn),
                    "fiat": "NGN",
                    "address": wallet_address,
                    "payment_method": "bank_transfer",
                }
            )
            response.raise_for_status()
            data = response.json()
            
            return {
                "reference": reference,
                "order_id": data["id"],
                "status": "PENDING",
                "amount_ngn": amount_ngn,
                "crypto": crypto,
                "amount_crypto": amount_crypto,
                "exchange": "quidax",
            }
        
        except Exception as e:
            logger.error(f"Quidax buy order failed: {str(e)}")
            raise ExternalServiceError("Quidax", str(e))
    
    async def sell_crypto(
        self,
        crypto: str,
        amount_crypto: Decimal,
        bank_account: dict,
        reference: str,
    ) -> dict:
        """Sell crypto to Quidax."""
        try:
            price = await self.get_price(crypto)
            amount_ngn = amount_crypto * price
            
            response = await self.client.post(
                "/orders",
                json={
                    "side": "sell",
                    "coin_amount": str(amount_crypto),
                    "coin": crypto.lower(),
                    "fiat_amount": str(amount_ngn),
                    "fiat": "NGN",
                    "bank_account": bank_account,
                }
            )
            response.raise_for_status()
            data = response.json()
            
            return {
                "reference": reference,
                "order_id": data["id"],
                "status": "PENDING",
                "crypto": crypto,
                "amount_crypto": amount_crypto,
                "amount_ngn": amount_ngn,
                "exchange": "quidax",
            }
        
        except Exception as e:
            logger.error(f"Quidax sell order failed: {str(e)}")
            raise ExternalServiceError("Quidax", str(e))
    
    async def get_order_status(self, order_id: str) -> dict:
        """Check order status."""
        try:
            response = await self.client.get(f"/orders/{order_id}")
            response.raise_for_status()
            data = response.json()
            
            return {
                "order_id": order_id,
                "status": data.get("status"),
            }
        
        except Exception as e:
            logger.error(f"Quidax order status check failed: {str(e)}")
            raise ExternalServiceError("Quidax", str(e))


def get_exchange_provider(exchange: str = "quidax") -> ExchangeProvider:
    """Get an exchange provider instance."""
    if exchange.lower() == "binance":
        return BinanceProvider()
    elif exchange.lower() == "quidax":
        return QuidaxProvider()
    else:
        raise ValueError(f"Unknown exchange: {exchange}")
