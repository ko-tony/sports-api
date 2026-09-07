"""Cloud Run function entry point: finance_live (one fetch per invocation)."""

import logging
from datetime import datetime, time, timedelta
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

import functions_framework
import requests

from config import HTTP_TIMEOUT_SECONDS
from db import upsert_rows

logger = logging.getLogger(__name__)
URL = "https://mis.twse.com.tw/stock/api/getChartOhlcStatis.jsp"
TAIPEI = ZoneInfo("Asia/Taipei")
COLUMNS = ("symbol", "name", "index", "turnover", "date", "fetchedAt", "change")


def _number(raw) -> Decimal:
    value = Decimal(str(raw))
    if not value.is_finite() or value < 0:
        raise ValueError("Invalid market value")
    return value


def _validate_quote_time(observed_at: datetime, now: datetime) -> None:
    if observed_at > now + timedelta(seconds=30):
        raise ValueError("TWSE quote time is in the future")
    # An older trading date can be legitimate on holidays. Keep its source date;
    # never relabel it with today's date or the fetch time.
    if observed_at.date() != now.date():
        return
    if time(9) <= now.time() < time(13, 30):
        if now - observed_at > timedelta(minutes=3):
            raise ValueError("Intraday TWSE quote is more than 3 minutes old")
    elif now.time() >= time(13, 30) and observed_at.time() < time(13, 30):
        raise ValueError("TWSE closing quote is not available yet")


def _to_row(payload: dict, now: datetime | None = None) -> tuple:
    now = now or datetime.now(TAIPEI)
    if not isinstance(payload, dict):
        raise ValueError("Invalid TWSE payload")
    if payload.get("rtcode") != "0000" or payload.get("ex") != "tse":
        raise ValueError("TWSE returned an unsuccessful response")
    quote = next(
        (item for item in payload["infoArray"]
         if isinstance(item, dict) and item.get("c") == "t00" and item.get("ex") == "tse"),
        None,
    )
    if quote is None:
        raise ValueError("TAIEX quote is missing")
    statistics = payload["staticObj"]
    if statistics["key"] != "tse_" + quote["d"]:
        raise ValueError("Index and turnover dates do not match")
    observed_at = datetime.strptime(
        quote["d"] + " " + quote["t"], "%Y%m%d %H:%M:%S"
    ).replace(tzinfo=TAIPEI)
    _validate_quote_time(observed_at, now)
    # staticObj.tz is cumulative TWD; do not use tv (lots) or r (trades).
    turnover = _number(statistics["tz"]) / Decimal("100000000")
    index = _number(quote["z"])
    if index == 0:
        raise ValueError("TAIEX index is unavailable")
    previous_close = _number(quote["y"])
    if previous_close == 0:
        raise ValueError("TAIEX previous close is unavailable")
    return (
        "TAIEX", quote["n"], index, turnover, observed_at,
        now, index - previous_close,
    )


@functions_framework.http
def finance_live(request):
    try:
        response = requests.get(
            URL, params={"ex": "tse", "ch": "t00.tw", "fqy": "1",
                         "_": str(int(datetime.now(TAIPEI).timestamp() * 1000))},
            headers={"Cache-Control": "no-cache"},
            timeout=HTTP_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        row = _to_row(response.json())
    except (requests.RequestException, ValueError, InvalidOperation, KeyError, TypeError):
        logger.exception("讀取證交所大盤 API 失敗")
        return "Failed to get data from API", 502

    try:
        count = upsert_rows(
            "finance_live", COLUMNS, "symbol", [row],
            freshness_column="date",
        )
    except Exception:
        logger.exception("寫入 finance_live 失敗")
        return "Failed to write data", 500
    return f"OK, {count} rows", 200
