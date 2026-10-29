from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import settings
from app.core.logging_config import SafeLogger
from app.db.database import db
from app.ingestion.catalogue_loader import catalogue_loader
from app.ingestion.policy_loader import policy_loader
from app.retrieval.semantic_search import local_vector_index

from app.api.health import router as health_router
from app.api.auth import router as auth_router
from app.api.catalogue import router as catalogue_router
from app.api.products import router as products_router
from app.api.feedback import router as feedback_router
from app.api.policy import router as policy_router
from app.api.audit import router as audit_router
from app.api.chat import router as chat_router
from app.api.evaluation import router as evaluation_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    SafeLogger.info(f"Starting {settings.PROJECT_NAME} v{settings.VERSION} for {settings.TEAM_NAME}")
    # 1. Initialize persistent SQLite database and seeds
    try:
        db.init_db()
    except Exception as e:
        SafeLogger.error(f"Failed to initialize database: {str(e)}")

    # 2. Load active catalogue from database or disk fallback
    catalogue_loader.load_default_catalogue()
    
    # 3. Load active policy from database or disk fallback
    policy_loader.load_default_policy()

    # 4. Build/load local vector index
    if catalogue_loader.is_ready:
        local_vector_index.build_index()

    yield
    SafeLogger.info("Shutting down TruthCart AI application.")

app = FastAPI(
    title=settings.PROJECT_NAME,
    description=f"{settings.TAGLINE} | Team {settings.TEAM_NAME} - Hackathon 2026",
    version=settings.VERSION,
    lifespan=lifespan
)

# CORS middleware for configured frontend origins and Vercel domains
cors_origins = [o.strip() for o in settings.CORS_ORIGINS if o.strip()]
default_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "https://truth-cart-ai.vercel.app",
    "https://truthcart-ai.vercel.app",
]
for d in default_origins:
    if d not in cors_origins and "*" not in cors_origins:
        cors_origins.append(d)

has_wildcard = "*" in cors_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if has_wildcard else cors_origins,
    allow_origin_regex=None if has_wildcard else r"^(https://.*\.vercel\.app|https://.*\.devtunnels\.ms|http://(localhost|127\.0\.0\.1|192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+|172\.(1[6-9]|2\d|3[0-1])\.\d+\.\d+)(:\d+)?)$",
    allow_credentials=not has_wildcard,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Exception handlers
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()}
    )

# Global safe error handler for unhandled runtime exceptions
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    if isinstance(exc, (HTTPException, StarletteHTTPException)):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail}
        )
    SafeLogger.error(f"Unhandled exception on {request.url.path}: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal server error occurred. Request could not be processed safely."}
    )

# Register API routers under /api
app.include_router(health_router, prefix="/api")
app.include_router(auth_router, prefix="/api")
app.include_router(catalogue_router, prefix="/api")
app.include_router(products_router, prefix="/api")
app.include_router(feedback_router, prefix="/api")
app.include_router(policy_router, prefix="/api")
app.include_router(audit_router, prefix="/api")
app.include_router(chat_router, prefix="/api")
app.include_router(evaluation_router, prefix="/api")

@app.get("/")
def root():
    return {
        "project": settings.PROJECT_NAME,
        "team": settings.TEAM_NAME,
        "tagline": settings.TAGLINE,
        "track": settings.TRACK,
        "status": "operational",
        "documentation": "/docs"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=True)
