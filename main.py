"""
Firewatch - Recreation.gov campsite availability monitor.

FastAPI app with:
- Watch CRUD API
- Template expansion API
- Admin/health endpoints
- Background scheduler for availability checks
- API key authentication
- Rate limiting (10 POST/min)
"""

from fastapi import FastAPI, Request, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import os
import logging

from database import engine, Base
from scheduler import start_scheduler, shutdown_scheduler
from routers import watches, templates, admin

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Create database tables
Base.metadata.create_all(bind=engine)

# Initialize FastAPI app
app = FastAPI(
    title="Firewatch API",
    description="Campsite availability monitor for Recreation.gov",
    version="1.0.0"
)

# CORS middleware (allow frontend to call API)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to your domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting setup (10 POST/min, eng review decision)
limiter = Limiter(key_func=get_remote_address, default_limits=["10/minute"])
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# API Key authentication middleware (eng review decision)
API_KEY = os.getenv("API_KEY")

@app.middleware("http")
async def api_key_middleware(request: Request, call_next):
    """
    Require X-API-Key header for all POST/PUT/DELETE requests.

    GET requests are exempt (allows public health checks, etc).

    Eng review decision: API key enforcement to prevent abuse.
    """
    # Skip auth for GET requests and health check
    if request.method == "GET" or request.url.path in ["/api/health", "/health"]:
        return await call_next(request)

    # Skip auth if API_KEY not configured (dev mode)
    if not API_KEY:
        logger.warning("API_KEY not set - API key auth disabled")
        return await call_next(request)

    # Check API key
    api_key = request.headers.get("X-API-Key")

    if not api_key or api_key != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key. Include X-API-Key header."
        )

    return await call_next(request)


# Mount routers
app.include_router(watches.router)
app.include_router(templates.router)
app.include_router(admin.router)


# Scheduler lifecycle management
@app.on_event("startup")
def startup_event():
    """
    Start background scheduler on app startup.

    Poll interval from POLL_INTERVAL_MINUTES env var (default 5).
    """
    poll_interval = int(os.getenv("POLL_INTERVAL_MINUTES", "5"))
    logger.info(f"Starting Firewatch with {poll_interval}-minute poll interval")

    try:
        start_scheduler(poll_interval_minutes=poll_interval)
        logger.info("Scheduler started successfully")
    except Exception as e:
        logger.error(f"Failed to start scheduler: {e}")
        # Continue running without scheduler (allows manual checks via API)


@app.on_event("shutdown")
def shutdown_event():
    """Gracefully shutdown scheduler on app shutdown."""
    logger.info("Shutting down Firewatch")

    try:
        shutdown_scheduler()
        logger.info("Scheduler stopped")
    except Exception as e:
        logger.error(f"Error during scheduler shutdown: {e}")


# Static files and index route (Phase 5 - UI)
# Serve index.html at root and static assets
try:
    app.mount("/static", StaticFiles(directory="static"), name="static")

    @app.get("/")
    def index():
        """Serve the Firewatch UI."""
        return FileResponse("static/index.html")

except Exception as e:
    logger.warning(f"Static files not mounted (static/ directory missing?): {e}")


# Root API info
@app.get("/api")
def api_info():
    """API information and available endpoints."""
    return {
        "name": "Firewatch API",
        "version": "1.0.0",
        "docs": "/docs",
        "endpoints": {
            "watches": "/api/watches",
            "templates": "/api/templates",
            "health": "/api/health",
            "logs": "/api/logs"
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
