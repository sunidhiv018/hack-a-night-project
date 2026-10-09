import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
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
    allow_origins=["*"],
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

# Include API Router under /api/v1
app.include_router(api_router, prefix=settings.API_V1_STR)

# Root status endpoint for API health check
@app.get("/health")
@app.get("/api/v1/health")
def health_check():
    return {
        "status": "online",
        "app_name": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "docs_url": "/docs"
    }

# Frontend Static Files & Clean HTML Routing
FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")

if os.path.exists(FRONTEND_DIR):
    # Mount assets, css, js static directories if present
    for sub in ["assets", "css", "js"]:
        sub_path = os.path.join(FRONTEND_DIR, sub)
        if os.path.exists(sub_path):
            app.mount(f"/{sub}", StaticFiles(directory=sub_path), name=sub)

    @app.get("/")
    def serve_root(request: Request):
        # Default to JSON health status for API compatibility unless explicitly requesting HTML text
        accept = request.headers.get("accept", "")
        if "text/html" in accept and "application/json" not in accept:
            return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))
        return {
            "status": "online",
            "app_name": settings.PROJECT_NAME,
            "version": settings.VERSION,
            "docs_url": "/docs"
        }

    @app.get("/index.html")
    @app.get("/app")
    @app.get("/app/")
    def serve_index():
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))


    @app.get("/login")
    @app.get("/login/")
    @app.get("/signup")
    @app.get("/signup/")
    def serve_login():
        return FileResponse(os.path.join(FRONTEND_DIR, "login.html"))

    @app.get("/dashboard")
    @app.get("/dashboard/")
    def serve_dashboard():
        return FileResponse(os.path.join(FRONTEND_DIR, "dashboard.html"))

    @app.get("/transactions")
    @app.get("/transactions/")
    def serve_transactions():
        return FileResponse(os.path.join(FRONTEND_DIR, "transactions.html"))

    @app.get("/forecasts")
    @app.get("/forecasts/")
    def serve_forecasts():
        return FileResponse(os.path.join(FRONTEND_DIR, "forecasts.html"))

    @app.get("/savings")
    @app.get("/savings/")
    def serve_savings():
        return FileResponse(os.path.join(FRONTEND_DIR, "savings.html"))

    @app.get("/time-machine")
    @app.get("/time-machine/")
    def serve_time_machine():
        return FileResponse(os.path.join(FRONTEND_DIR, "time-machine.html"))

    @app.get("/reports")
    @app.get("/reports/")
    def serve_reports():
        return FileResponse(os.path.join(FRONTEND_DIR, "reports.html"))

    @app.get("/import")
    @app.get("/import/")
    def serve_import():
        return FileResponse(os.path.join(FRONTEND_DIR, "import.html"))

    @app.get("/chat")
    @app.get("/chat/")
    @app.get("/milo")
    @app.get("/milo/")
    def serve_chat():
        return FileResponse(os.path.join(FRONTEND_DIR, "chat.html"))

    @app.get("/{filename}.html")
    def serve_html_file(filename: str):
        file_path = os.path.join(FRONTEND_DIR, f"{filename}.html")
        if os.path.exists(file_path):
            return FileResponse(file_path)
        return JSONResponse(status_code=404, content={"message": "File not found"})
else:
    @app.get("/")
    def root():
        return {
            "status": "online",
            "app_name": settings.PROJECT_NAME,
            "version": settings.VERSION,
            "docs_url": "/docs"
        }


