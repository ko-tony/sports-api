import logging
from collections.abc import Callable
from typing import TypeVar

from fastapi import HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app import models
from app.repositories import environment as repository

logger = logging.getLogger(__name__)
Result = TypeVar("Result")


def _load(
    db: Session,
    query: Callable[[Session], list[Result]],
    resource_name: str,
) -> list[Result]:
    try:
        result = query(db)
    except SQLAlchemyError as error:
        logger.exception("Database query failed for %s", resource_name)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Data source is temporarily unavailable",
        ) from error

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{resource_name} data was not found",
        )
    return result


def get_cwa_uv_live(db: Session) -> list[models.CwaUvLive]:
    return _load(db, repository.list_cwa_uv_live, "CWA weather")


def get_air_quality(db: Session) -> list[models.MoenvLive]:
    return _load(db, repository.list_air_quality, "air quality")


def get_environment(db: Session) -> list[object]:
    return _load(db, repository.list_environment, "environment")
