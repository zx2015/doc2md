from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1 import jobs, config, health, ws
from app.core.database import SessionLocal
from app.api.deps import init_app_config
from app.core.config import settings

app = FastAPI(title=settings.PROJECT_NAME)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix=settings.API_V1_STR, tags=["Health"])
app.include_router(jobs.router, prefix=settings.API_V1_STR, tags=["Jobs"])
app.include_router(config.router, prefix=settings.API_V1_STR, tags=["Config"])
app.include_router(ws.router, prefix=settings.API_V1_STR, tags=["WebSockets"])

@app.on_event("startup")
def on_startup():
    db = SessionLocal()
    init_app_config(db)
    db.close()
