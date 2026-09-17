from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import attendance, auth, dashboard, employees, issues, master, plans, progress, reports, sites, users

app = FastAPI(title="GSB Site API", version="0.1.1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(auth.router, prefix="/api/v1")
app.include_router(sites.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(employees.router, prefix="/api/v1")
app.include_router(attendance.router, prefix="/api/v1")
app.include_router(plans.router, prefix="/api/v1")
app.include_router(progress.router, prefix="/api/v1")
app.include_router(issues.router, prefix="/api/v1")
app.include_router(dashboard.router, prefix="/api/v1")
app.include_router(master.router, prefix="/api/v1")
app.include_router(reports.router, prefix="/api/v1")


@app.get("/health")
def health() -> dict:
    return {"ok": True}
