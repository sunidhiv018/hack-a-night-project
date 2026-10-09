from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from app.core.config import settings
from app.core.responses import ErrorResponse
from app.db.session import engine, Base
from app.api.routes import router as api_router

# Create Database tables automatically on startup
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="AI-powered Personal Finance & Cash-Flow Intelligence Engine",
    openapi_url="/api/v1/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS Configuration for Frontend Integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Exception Handlers
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content=ErrorResponse(
            success=False,
            message="Request validation error",
            errors=exc.errors(),
            code="VALIDATION_ERROR"
        ).model_dump()
    )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            success=False,
            message=str(exc),
            code="INTERNAL_SERVER_ERROR"
        ).model_dump()
    )

# Root endpoint
@app.get("/")
def root():
    return {
        "status": "online",
        "app_name": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "docs_url": "/docs"
    }

# Include API Router under /api/v1
app.include_router(api_router, prefix=settings.API_V1_STR)
