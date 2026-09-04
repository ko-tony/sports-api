from fastapi import APIRouter, Response
from sqlalchemy import Row

from app.core.config import settings
from app.core.database import DatabaseSession
from app.schemas import EnvironmentResponse
from app.services import environment as service

v1_router = APIRouter(prefix="/api/v1", tags=["environment"])


@v1_router.get(
    "/environment",
    response_model=list[EnvironmentResponse],
    summary="各縣市空氣品質與天氣即時值",
)
def get_environment(response: Response, db: DatabaseSession) -> list[Row]:
    response.headers["Cache-Control"] = settings.public_cache_control
    return service.get_environment(db)
