from sqlalchemy.orm import Session

from app.models import FinanceLive


def get_finance(db: Session) -> FinanceLive | None:
    return db.get(FinanceLive, "TAIEX")
