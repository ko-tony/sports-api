import logging
from datetime import datetime
from zoneinfo import ZoneInfo

import functions_framework
import requests

from config import HTTP_TIMEOUT_SECONDS, required
from db import upsert_rows

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

URL = "https://data.moenv.gov.tw/api/v2/aqx_p_432"

# 測站代號 -> 代表的縣市（county 欄位由 API 提供，這裡只做篩選）
SITE_IDS = {
    "12": "中山",
    "6": "板橋",
    "17": "桃園市",
    "32": "西屯",
    "46": "臺南市",
    "50": "鳳山",
}

COLUMNS = ("cityName", "aqi", "pm25", "o3", "date")

# 環境部的 publishtime 沒有時區資訊，實際是台北當地時間
TAIPEI = ZoneInfo("Asia/Taipei")
PUBLISHTIME_FORMATS = ("%Y/%m/%d %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M")


def _fetch() -> list[dict]:
    params = {"api_key": required("MOENV_API_KEY")}
    response = requests.get(URL, params=params, timeout=HTTP_TIMEOUT_SECONDS)
    response.raise_for_status()
    payload = response.json()

    records = payload["records"] if isinstance(payload, dict) else payload
    return [record for record in records if record.get("siteid") in SITE_IDS]


def _value(station: dict, key: str) -> str | None:
    """測站維修時欄位會是空字串，要寫成 NULL 而不是 0。"""
    value = station.get(key)
    return value if value not in ("", None) else None


def _parse_publishtime(raw: str) -> datetime:
    for fmt in PUBLISHTIME_FORMATS:
        try:
            return datetime.strptime(raw.strip(), fmt).replace(tzinfo=TAIPEI)
        except ValueError:
            continue
    raise ValueError(f"無法解析 publishtime: {raw!r}")


def _to_row(station: dict) -> tuple:
    return (
        station["county"],
        _value(station, "aqi"),
        _value(station, "pm2.5"),
        _value(station, "o3"),
        _parse_publishtime(station["publishtime"]),
    )


@functions_framework.http
def moenv_live(request):
    try:
        stations = _fetch()
    except (requests.RequestException, ValueError, KeyError):
        logger.exception("讀取環境部 API 失敗")
        return "Failed to get data from API", 502

    try:
        count = upsert_rows("moenv_live", COLUMNS, "cityName", [
            _to_row(station) for station in stations
        ])
    except Exception:
        logger.exception("寫入 moenv_live 失敗")
        return "Failed to write data", 500

    return f"OK, {count} rows", 200
