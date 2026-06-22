"""
Ogak USSD Platform - Main FastAPI Application
Entry point for all services: USSD gateway, Open Payments API, Admin Dashboard
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from packages.shared.config import get_settings
from packages.shared.errors import OgakException
from packages.ussd.gateway import router as ussd_router
from packages.api.open_payments import router as open_payments_router
from packages.api.webhooks import router as webhooks_router
from packages.ilp_connector.connector import get_connector, close_connectors

settings = get_settings()

# Configure logging
logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════
# Lifespan Events
# ═══════════════════════════════════════════════════════════════════

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle startup and shutdown events."""
    # Startup
    logger.info("Ogak USSD Platform Starting")
    logger.info(f"Environment: {settings.app_env}")
    logger.info(f"Debug: {settings.app_debug}")
    
    # Initialize ILP connector
    try:
        connector = await get_connector("default")
        logger.info("ILP Connector initialized")
    except Exception as e:
        logger.error(f"Failed to initialize ILP Connector: {str(e)}")
    
    yield
    
    # Shutdown
    logger.info("Ogak USSD Platform Shutting Down")
    await close_connectors()
    logger.info("ILP Connectors closed")


# ═══════════════════════════════════════════════════════════════════
# Create FastAPI App
# ═══════════════════════════════════════════════════════════════════

app = FastAPI(
    title="Ogak USSD Platform",
    description="Non-P2P Crypto-Fiat Integration USSD for Nigeria — Production",
    version="1.0.0",
    lifespan=lifespan,
)


# ═══════════════════════════════════════════════════════════════════
# CORS Middleware
# ═══════════════════════════════════════════════════════════════════

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ═══════════════════════════════════════════════════════════════════
# Exception Handlers
# ═══════════════════════════════════════════════════════════════════

@app.exception_handler(OgakException)
async def ogak_exception_handler(request, exc: OgakException):
    """Handle Ogak-specific exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_dict(),
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc: Exception):
    """Handle general exceptions."""
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "message": "Internal server error",
            "error_code": "INTERNAL_ERROR",
        },
    )


# ═══════════════════════════════════════════════════════════════════
# Root & Health Endpoints
# ═══════════════════════════════════════════════════════════════════

@app.get("/")
async def root() -> dict:
    """Root endpoint."""
    return {
        "name": "Ogak USSD Platform",
        "version": settings.app_name,
        "environment": settings.app_env,
        "status": "operational",
    }


@app.get("/health")
async def health() -> dict:
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "ogak-ussd-platform",
        "version": settings.app_name,
    }


# ═══════════════════════════════════════════════════════════════════
# Register Routers
# ═══════════════════════════════════════════════════════════════════

# USSD routes (Africa's Talking production webhook)
app.include_router(ussd_router, prefix="/api/v1", tags=["ussd"])

# Core API + Open Payments
app.include_router(open_payments_router, prefix="/api/v1", tags=["open-payments"])

# Real provider webhooks (Paystack, Flutterwave, Quidax, etc.)
app.include_router(webhooks_router, prefix="/api/v1", tags=["webhooks"])

# Admin routes (CLI + future web dashboard)
# app.include_router(admin_router, prefix="/admin", tags=["admin"])


# ═══════════════════════════════════════════════════════════════════
# Info Endpoint
# ═══════════════════════════════════════════════════════════════════

@app.get("/api/v1/info")
async def api_info() -> dict:
    """Get API information."""
    return {
        "name": "Ogak USSD Platform",
        "version": config.api_version,
        "environment": config.environment,
        "description": "Non-P2P Crypto-Fiat Integration USSD for Nigeria",
        "endpoints": {
            "ussd": "/api/v1/ussd",
            "open_payments": "/api/v1/open-payments",
            "health": "/health",
        },
        "features": [
            "USSD menu system with multi-language support",
            "Interledger Protocol (ILP) for atomic settlement",
            "Open Payments API for account discovery",
            "Integration with Nigerian banks (Paystack, Flutterwave)",
            "Crypto exchange integration (Binance, Quidax)",
            "KYC/AML compliance",
            "Real-time rates and quotes",
        ],
    }


# ═══════════════════════════════════════════════════════════════════
# Main Entry Point
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        app,
        host=config.admin.host,
        port=config.admin.port,
        log_level=config.log.level.lower(),
        reload=config.debug,
    )
