from fastapi import APIRouter, Response

from app.core.database import DatabaseSession
from app.schemas import FinanceResponse
from app.services import finance as service

v1_router = APIRouter(prefix="/api/v1", tags=["大盤"])


@v1_router.get("/finance", response_model=FinanceResponse,
               summary="台灣加權指數與當日累計成交金額（億元）")
def get_finance(response: Response, db: DatabaseSession):
    # Do not add the environment endpoint's 5-minute CDN cache to a 3-minute feed.
    response.headers["Cache-Control"] = "no-store"
    return service.get_finance(db)
