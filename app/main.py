"""FastAPI application entry point."""

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.router import router
from app.db import db

app = FastAPI(title="Logistics Automation API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1", tags=["documents"])


@app.on_event("startup")
async def startup_event():
    """Check database on startup."""
    if db.check_connection():
        print("Database connected")
    else:
        print("Database connection failed")


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "Logistics Automation API", "docs": "/docs"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8080)))
