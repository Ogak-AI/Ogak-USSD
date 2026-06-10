"""
Production Africa's Talking USSD Gateway
Real webhook integration only. No simulator paths.

Every request:
1. Receives the standard AT callback (sessionId, phoneNumber, text, serviceCode)
2. Loads/creates user + Redis session state
3. Reconstructs the USSDMenu with a real DB session
4. Delegates to the production menu state machine
5. Returns strict "CON ..." or "END ..." response
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.database import get_db
from packages.shared.config import get_settings
from packages.shared.types import Language
from packages.ussd.menu import USSDMenu
from packages.ussd.session import session_manager  # still used for lightweight Redis state

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ussd", tags=["ussd"])


class ATUSSDRequest(BaseModel):
    """Strict model for Africa's Talking production callback."""
    sessionId: str = Field(..., alias="sessionId")
    serviceCode: str = Field(..., alias="serviceCode")
    phoneNumber: str = Field(..., alias="phoneNumber")
    text: str = Field(default="", alias="text")
    networkCode: Optional[str] = Field(None, alias="networkCode")

    class Config:
        populate_by_name = True
        extra = "allow"


@router.post("/callback")
async def handle_ussd_callback(
    payload: ATUSSDRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Primary production USSD entry point.
    This endpoint must be publicly reachable and registered in your Africa's Talking
    USSD application dashboard for the live short code.
    """
    try:
        logger.info(
            "USSD callback received",
            extra={
                "session_id": payload.sessionId,
                "phone": payload.phoneNumber,
                "text": payload.text,
                "service_code": payload.serviceCode,
            },
        )

        phone = payload.phoneNumber
        session_id = payload.sessionId
        text = payload.text or ""
        current_input = text.split("*")[-1] if text else ""

        # Lightweight Redis session (for speed). Full user + transaction state lives in Postgres.
        session_data = await session_manager.get_session(session_id)
        language = Language(session_data.get("language", "en")) if session_data else Language.EN

        menu = USSDMenu(
            session_id=session_id,
            phone_number=phone,
            language=language,
            db_session=db,
        )

        # First request in session or expired → start fresh
        if not session_data:
            await session_manager.create_session(session_id, phone, language.value)
        else:
            # Restore minimal context if needed (menu is mostly stateless per request)
            menu.context = session_data.get("context", {})

        response_text, next_state = await menu.handle_input(current_input)

        # Persist lightweight state
        await session_manager.update_session(
            session_id,
            {
                "language": language.value,
                "context": menu.context,
                "current_menu": next_state.value if next_state else "MAIN_MENU",
                "user_id": getattr(menu.user, "id", None),
            },
        )

        end_session = next_state is None or next_state.name in ("EXIT",) or "Goodbye" in response_text

        ussd_response = f"{'END' if end_session else 'CON'} {response_text}"

        logger.info(
            "USSD response sent",
            extra={"session_id": session_id, "end": end_session},
        )

        return {"USSD": ussd_response}

    except Exception as exc:
        logger.exception("USSD callback processing failed")
        return {"USSD": "END Sorry, an error occurred. Please dial again in a few minutes."}


@router.get("/health")
async def ussd_health() -> dict:
    return {
        "status": "healthy",
        "service": "ogak-ussd",
        "provider": "africas_talking",
        "shortcode": get_settings().at_ussd_shortcode,
    }
