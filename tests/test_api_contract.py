import unittest
from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from app.core.database import get_db
from main import app


class ApiContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        app.dependency_overrides[get_db] = lambda: object()
        cls.client = TestClient(app)
        cls.paths = cls.client.get("/openapi.json").json()["paths"]

    @classmethod
    def tearDownClass(cls) -> None:
        app.dependency_overrides.clear()

    def test_legacy_data_paths_remain_available(self) -> None:
        for path in ("/cwa_uv_live", "/moenv_live", "/env_live_1"):
            with self.subTest(path=path):
                self.assertIn(path, self.paths)

    def test_versioned_data_paths_are_available(self) -> None:
        for path in (
            "/api/v1/cwa-uv-live",
            "/api/v1/air-quality",
            "/api/v1/environment",
        ):
            with self.subTest(path=path):
                self.assertIn(path, self.paths)

    def test_removed_features_are_not_exposed(self) -> None:
        for path in (
            "/register",
            "/token",
            "/excel_to_word",
            "/items/",
            "/weather",
            "/api/v1/weather",
        ):
            with self.subTest(path=path):
                self.assertNotIn(path, self.paths)

    def test_health_endpoint(self) -> None:
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    @patch("app.services.environment.repository.list_cwa_uv_live")
    def test_legacy_and_versioned_cwa_contracts_match(self, list_cwa) -> None:
        list_cwa.return_value = [
            SimpleNamespace(
                cityName="臺北",
                airTemperature=28.5,
                uvIndex=6,
                date=datetime(2026, 9, 3, 12, 0),
                weather="晴",
                humidity=70,
            )
        ]

        legacy = self.client.get("/cwa_uv_live")
        versioned = self.client.get("/api/v1/cwa-uv-live")

        self.assertEqual(legacy.json(), versioned.json())
        self.assertEqual(legacy.json()[0]["airTemperature"], 28.5)
        self.assertEqual(legacy.json()[0]["date"], "2026-09-03T12:00:00")
        self.assertIn("s-maxage=300", legacy.headers["cache-control"])

    @patch("app.services.environment.repository.list_air_quality")
    def test_legacy_and_versioned_air_quality_contracts_match(
        self, list_air_quality
    ) -> None:
        list_air_quality.return_value = [
            SimpleNamespace(
                cityName="臺北市",
                aqi=42,
                pm25=Decimal("12.5"),
                o3=Decimal("30"),
                date=date(2026, 9, 3),
            )
        ]

        legacy = self.client.get("/moenv_live")
        versioned = self.client.get("/api/v1/air-quality")

        self.assertEqual(legacy.json(), versioned.json())
        self.assertEqual(legacy.json()[0]["pm25"], 12.5)

    @patch("app.services.environment.repository.list_environment")
    def test_legacy_and_versioned_environment_contracts_match(
        self, list_environment
    ) -> None:
        list_environment.return_value = [
            SimpleNamespace(
                cityName="臺北市",
                aqi=42,
                pm25=Decimal("12.5"),
                date=date(2026, 9, 3),
                humidity=70,
                airTemperature=28.5,
            )
        ]

        legacy = self.client.get("/env_live_1")
        versioned = self.client.get("/api/v1/environment")

        self.assertEqual(legacy.json(), versioned.json())
        self.assertEqual(legacy.json()[0]["date"], "2026-09-03")

    @patch("app.services.environment.repository.list_cwa_uv_live")
    def test_database_errors_return_service_unavailable(self, list_cwa) -> None:
        list_cwa.side_effect = SQLAlchemyError("unavailable")

        with self.assertLogs("app.services.environment", level="ERROR"):
            response = self.client.get("/cwa_uv_live")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json(), {"detail": "Data source is temporarily unavailable"}
        )

    def test_public_cors_does_not_allow_credentials(self) -> None:
        response = self.client.get(
            "/health", headers={"Origin": "https://publisher.example"}
        )

        self.assertEqual(response.headers["access-control-allow-origin"], "*")
        self.assertNotIn("access-control-allow-credentials", response.headers)


if __name__ == "__main__":
    unittest.main()
