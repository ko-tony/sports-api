import logging

from fastapi import HTTPException, status
from sqlalchemy import Row
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.repositories import environment as repository

logger = logging.getLogger(__name__)


def get_environment(db: Session) -> list[Row]:
    try:
        result = repository.list_environment(db)
    except SQLAlchemyError as error:
        logger.exception("Database query failed for environment")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Data source is temporarily unavailable",
        ) from error

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="environment data was not found",
        )
    return result
