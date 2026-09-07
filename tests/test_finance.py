import importlib.util
import sys
import unittest
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from app.core.database import get_db
from main import app

CLOUDRUN = Path(__file__).resolve().parents[1] / "cloudrun"
sys.path.insert(0, str(CLOUDRUN))
spec = importlib.util.spec_from_file_location("finance_ingest", CLOUDRUN / "get-twse-finance-live.py")
ingest = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ingest)
sys.path.pop(0)

PAYLOAD = {
    "rtcode": "0000", "ex": "tse",
    "staticObj": {"key": "tse_20260907", "tz": "939926033350"},
    "infoArray": [{"c": "t00", "ex": "tse", "n": "發行量加權股價指數",
                   "z": "47326.27", "y": "46551.13", "d": "20260907", "t": "13:33:00"}],
}


class FinanceIngestTest(unittest.TestCase):
    def setUp(self):
        clock = patch.object(ingest, "datetime", wraps=datetime)
        mocked = clock.start()
        self.addCleanup(clock.stop)
        mocked.now.return_value = datetime.fromisoformat("2026-09-07T15:00:00+08:00")

    def test_intraday_quote_and_close(self):
        for source_time, call_time in (("10:00:00", "10:00:10"),
                                       ("13:30:00", "14:00:00"),
                                       ("13:33:00", "15:00:00")):
            with self.subTest(source_time=source_time):
                payload = deepcopy(PAYLOAD)
                payload["infoArray"][0]["t"] = source_time
                now = datetime.fromisoformat("2026-09-07T" + call_time + "+08:00")
                row = ingest._to_row(payload, now)
                self.assertEqual(row[4].strftime("%H:%M:%S"), source_time)

    def test_stale_intraday_and_unpublished_close_are_rejected(self):
        for source_time, call_time in (("09:50:00", "10:00:00"),
                                       ("13:29:00", "13:30:05"),
                                       ("13:33:00", "10:00:00")):
            with self.subTest(source_time=source_time):
                payload = deepcopy(PAYLOAD)
                payload["infoArray"][0]["t"] = source_time
                now = datetime.fromisoformat("2026-09-07T" + call_time + "+08:00")
                with self.assertRaises(ValueError):
                    ingest._to_row(payload, now)

    def test_units_and_source_time(self):
        row = ingest._to_row(PAYLOAD)
        self.assertEqual(row[2], Decimal("47326.27"))
        self.assertEqual(row[3], Decimal("9399.2603335"))
        self.assertEqual(row[4].isoformat(), "2026-09-07T13:33:00+08:00")

    def test_signed_change_from_previous_close(self):
        for previous_close, expected in (("46551.13", "775.14"),
                                         ("47426.28", "-100.01"),
                                         ("47326.27", "0")):
            with self.subTest(previous_close=previous_close):
                payload = deepcopy(PAYLOAD)
                payload["infoArray"][0]["y"] = previous_close
                row = dict(zip(ingest.COLUMNS, ingest._to_row(payload)))
                self.assertEqual(row["change"], Decimal(expected))

    def test_invalid_source_preserves_database(self):
        invalid = [None, [], {}]
        for previous_close in (None, "-", "NaN", "Infinity", "0", "-1"):
            data = deepcopy(PAYLOAD)
            data["infoArray"][0]["y"] = previous_close
            invalid.append(data)
        data = deepcopy(PAYLOAD)
        del data["infoArray"][0]["y"]
        invalid.append(data)
        for amount in ("-", "NaN", "Infinity", "-1", None):
            data = deepcopy(PAYLOAD)
            data["staticObj"]["tz"] = amount
            invalid.append(data)
        for field, value in (("rtcode", "9999"), ("infoArray", [])):
            data = deepcopy(PAYLOAD)
            data[field] = value
            invalid.append(data)
        data = deepcopy(PAYLOAD)
        data["staticObj"]["key"] = "tse_20260904"
        invalid.append(data)
        for data in invalid:
            with self.subTest(data=data), patch.object(ingest.requests, "get") as get, patch.object(ingest, "upsert_rows") as write:
                get.return_value.json.return_value = data
                with self.assertLogs(ingest.logger, level="ERROR"):
                    self.assertEqual(ingest.finance_live(Mock())[1], 502)
                write.assert_not_called()

    def test_single_fetch_and_upsert(self):
        with patch.object(ingest.requests, "get") as get, patch.object(ingest, "upsert_rows", return_value=1) as write:
            get.return_value.json.return_value = PAYLOAD
            self.assertEqual(ingest.finance_live(Mock()), ("OK, 1 rows", 200))
            get.assert_called_once()
            self.assertEqual(write.call_args.kwargs, {"freshness_column": "date"})

    def test_network_and_database_failures(self):
        with patch.object(ingest.requests, "get", side_effect=ingest.requests.Timeout), patch.object(ingest, "upsert_rows") as write:
            with self.assertLogs(ingest.logger, level="ERROR"):
                self.assertEqual(ingest.finance_live(Mock())[1], 502)
            write.assert_not_called()
        with patch.object(ingest.requests, "get") as get, patch.object(ingest, "upsert_rows", side_effect=RuntimeError):
            get.return_value.json.return_value = PAYLOAD
            with self.assertLogs(ingest.logger, level="ERROR"):
                self.assertEqual(ingest.finance_live(Mock())[1], 500)


class FinanceApiTest(unittest.TestCase):
    def setUp(self):
        app.dependency_overrides[get_db] = lambda: object()
        self.addCleanup(app.dependency_overrides.clear)
        self.client = TestClient(app)

    @patch("app.services.finance.repository.get_finance")
    def test_finance_response(self, get):
        get.return_value = SimpleNamespace(
            symbol="TAIEX", name="發行量加權股價指數", index=Decimal("47326.27"),
            change=Decimal("775.14"),
            turnover=Decimal("9399.26033350"), date=datetime(2026, 9, 7, tzinfo=timezone.utc),
            fetchedAt=datetime(2026, 9, 7, tzinfo=timezone.utc),
        )
        response = self.client.get("/api/v1/finance")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["turnover"], 9399.2603335)
        self.assertEqual(response.json()["turnoverUnit"], "億元")
        self.assertEqual(response.headers["cache-control"], "no-store")
        for change in (Decimal("775.14"), Decimal("-100.01"), Decimal("0"), None):
            with self.subTest(change=change):
                get.return_value.change = change
                response = self.client.get("/api/v1/finance")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["change"], float(change) if change is not None else None)

    @patch("app.services.finance.repository.get_finance")
    def test_empty_and_database_errors(self, get):
        get.return_value = None
        self.assertEqual(self.client.get("/api/v1/finance").status_code, 404)
        get.side_effect = SQLAlchemyError("unavailable")
        with self.assertLogs("app.services.finance", level="ERROR"):
            self.assertEqual(self.client.get("/api/v1/finance").status_code, 503)
