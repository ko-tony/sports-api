import logging

from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import FinanceLive
from app.repositories import finance as repository

logger = logging.getLogger(__name__)


def get_finance(db: Session) -> FinanceLive:
    try:
        result = repository.get_finance(db)
    except SQLAlchemyError as error:
        logger.exception("Database query failed for finance")
        raise HTTPException(503, "Data source is temporarily unavailable") from error
    if result is None:
        raise HTTPException(404, "finance data was not found")
    return result
