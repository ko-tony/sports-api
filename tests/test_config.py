import os
import unittest
from unittest.mock import patch

from app.core.config import load_settings


class DatabaseSslModeTest(unittest.TestCase):
    def test_disable_is_allowed_for_cloud_sql_unix_socket(self) -> None:
        environment = {
            "SQLALCHEMY_DATABASE_URL": (
                "postgresql+psycopg2://api_user:password@/postgres"
                "?host=/cloudsql/project:asia-east1:instance"
            ),
            "DB_SSLMODE": "disable",
        }

        with patch.dict(os.environ, environment, clear=True):
            settings = load_settings()

        self.assertEqual(settings.db_sslmode, "disable")

    def test_disable_is_rejected_for_tcp_connection(self) -> None:
        environment = {
            "SQLALCHEMY_DATABASE_URL": (
                "postgresql+psycopg2://api_user:password@db.example/postgres"
            ),
            "DB_SSLMODE": "disable",
        }

        with patch.dict(os.environ, environment, clear=True):
            with self.assertRaisesRegex(ValueError, "Cloud SQL Unix Socket"):
                load_settings()

    def test_disable_rejects_cloud_sql_socket_with_tcp_fallback(self) -> None:
        environment = {
            "SQLALCHEMY_DATABASE_URL": (
                "postgresql+psycopg2://api_user:password@/postgres"
                "?host=/cloudsql/project:asia-east1:instance,db.example"
            ),
            "DB_SSLMODE": "disable",
        }

        with patch.dict(os.environ, environment, clear=True):
            with self.assertRaisesRegex(ValueError, "Cloud SQL Unix Socket"):
                load_settings()

    def test_disable_rejects_cloud_sql_socket_with_hostaddr_fallback(self) -> None:
        environment = {
            "SQLALCHEMY_DATABASE_URL": (
                "postgresql+psycopg2://api_user:password@/postgres"
                "?host=/cloudsql/project:asia-east1:instance"
                "&hostaddr=203.0.113.10"
            ),
            "DB_SSLMODE": "disable",
        }

        with patch.dict(os.environ, environment, clear=True):
            with self.assertRaisesRegex(ValueError, "Cloud SQL Unix Socket"):
                load_settings()

    def test_encrypted_sslmode_remains_available_for_tcp_connection(self) -> None:
        environment = {
            "SQLALCHEMY_DATABASE_URL": (
                "postgresql+psycopg2://api_user:password@db.example/postgres"
            ),
            "DB_SSLMODE": "verify-full",
        }

        with patch.dict(os.environ, environment, clear=True):
            settings = load_settings()

        self.assertEqual(settings.db_sslmode, "verify-full")


if __name__ == "__main__":
    unittest.main()
