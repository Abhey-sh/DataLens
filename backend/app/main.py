"""
Main FastAPI application.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
import os
import sys

from app.api.routes import assets, members
from app.schemas.validation import HealthResponse

# Configure logging
logger.remove()
logger.add(
    sys.stdout,
    format="<level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="INFO",
)

# Create FastAPI app
app = FastAPI(
    title="DataLens - Enterprise Data Validation Platform",
    description="A production-ready data validation engine for CSV imports",
    version="1.0.0",
)

# Configure CORS
allowed_origins = os.getenv(
    "DATALENS_CORS_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173",
).split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in allowed_origins],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(members.router)
app.include_router(assets.router)


@app.get("/health", response_model=HealthResponse, include_in_schema=False)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(status="healthy")


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "DataLens Validation Engine",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
