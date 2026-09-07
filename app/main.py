from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.environment import v1_router
from app.api.finance import v1_router as finance_router
from app.core.database import DatabaseSession

app = FastAPI(
    title="Realtime API for PPPMP ads",
    description="Public supplementary data API for PPPMP ads.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["Accept", "Content-Type"],
)

app.include_router(v1_router)
app.include_router(finance_router)


@app.get("/", include_in_schema=False)
def read_root() -> dict[str, str]:
    return {"Hello": "World"}


@app.get("/health", include_in_schema=False)
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready", include_in_schema=False)
def readiness(db: DatabaseSession) -> dict[str, str]:
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is unavailable",
        ) from error
    return {"status": "ready"}
