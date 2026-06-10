"""
Ogak USSD Service Entry Point
FastAPI USSD gateway service.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from packages.shared.config import get_settings

settings = get_settings()
from packages.ussd.gateway import router as ussd_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle startup and shutdown."""
    logger.info("Ogak USSD Service Starting")
    yield
    logger.info("Ogak USSD Service Shutting Down")


app = FastAPI(
    title="Ogak USSD Service",
    description="Production Africa's Talking USSD engine for Ogak",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.security.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root() -> dict:
    """Root endpoint."""
    return {
        "name": "Ogak USSD Service",
        "version": config.api_version,
        "status": "operational",
    }


@app.get("/health")
async def health() -> dict:
    """Health check."""
    return {
        "status": "healthy",
        "service": "ogak-ussd",
        "version": config.api_version,
    }


# Register USSD routes
app.include_router(ussd_router, prefix="/api/v1")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=settings.ussd_port,
        log_level="info",
    )
