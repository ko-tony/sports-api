from fastapi import APIRouter, Response

from app import models
from app.core.config import settings
from app.core.database import DatabaseSession
from app.schemas import (
    AirQualityResponse,
    CwaUvLiveResponse,
    EnvironmentResponse,
)
from app.services import environment as service

v1_router = APIRouter(prefix="/api/v1", tags=["environment"])
legacy_router = APIRouter(tags=["environment-legacy"])


def _set_public_cache(response: Response) -> None:
    response.headers["Cache-Control"] = settings.public_cache_control


@legacy_router.get(
    "/cwa_uv_live", response_model=list[CwaUvLiveResponse], deprecated=True
)
@v1_router.get("/cwa-uv-live", response_model=list[CwaUvLiveResponse])
def get_cwa_uv_live(
    response: Response, db: DatabaseSession
) -> list[models.CwaUvLive]:
    _set_public_cache(response)
    return service.get_cwa_uv_live(db)


@legacy_router.get(
    "/moenv_live", response_model=list[AirQualityResponse], deprecated=True
)
@v1_router.get("/air-quality", response_model=list[AirQualityResponse])
def get_air_quality(response: Response, db: DatabaseSession) -> list[models.MoenvLive]:
    _set_public_cache(response)
    return service.get_air_quality(db)


@legacy_router.get(
    "/env_live_1",
    response_model=list[EnvironmentResponse],
    deprecated=True,
    summary="空氣品質與溫濕度",
)
@v1_router.get("/environment", response_model=list[EnvironmentResponse])
def get_environment(response: Response, db: DatabaseSession) -> list[object]:
    _set_public_cache(response)
    return service.get_environment(db)
