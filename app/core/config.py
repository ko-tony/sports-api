import os
from dataclasses import dataclass

from dotenv import load_dotenv
from sqlalchemy.engine import make_url

load_dotenv()


def _int_setting(name: str, default: int, minimum: int) -> int:
    value = int(os.getenv(name, str(default)))
    if value < minimum:
        raise ValueError(f"{name} must be {minimum} or greater")
    return value


def _validate_db_sslmode(database_url: str, db_sslmode: str) -> None:
    encrypted_sslmodes = {
        "require",
        "verify-ca",
        "verify-full",
    }
    if db_sslmode in encrypted_sslmodes:
        return

    if db_sslmode == "disable":
        database = make_url(database_url)
        socket_host = database.query.get("host")
        connection_name = (
            socket_host.removeprefix("/cloudsql/")
            if isinstance(socket_host, str)
            else ""
        )
        is_cloud_sql_socket = (
            database.drivername.startswith("postgresql")
            and database.host is None
            and set(database.query) == {"host"}
            and isinstance(socket_host, str)
            and socket_host.startswith("/cloudsql/")
            and connection_name.count(":") == 2
            and "/" not in connection_name
            and "," not in connection_name
        )
        if is_cloud_sql_socket:
            return
        raise ValueError(
            "DB_SSLMODE=disable is only allowed with a Cloud SQL Unix Socket"
        )

    allowed_sslmodes = sorted(encrypted_sslmodes | {"disable"})
    raise ValueError(f"DB_SSLMODE must be one of {allowed_sslmodes}")


@dataclass(frozen=True)
class Settings:
    database_url: str
    db_sslmode: str
    db_pool_size: int
    db_max_overflow: int
    db_connect_timeout_seconds: int
    db_pool_timeout_seconds: int
    db_pool_recycle_seconds: int
    browser_cache_seconds: int
    shared_cache_seconds: int
    stale_while_revalidate_seconds: int

    @property
    def public_cache_control(self) -> str:
        return (
            "public, "
            f"max-age={self.browser_cache_seconds}, "
            f"s-maxage={self.shared_cache_seconds}, "
            f"stale-while-revalidate={self.stale_while_revalidate_seconds}"
        )


def load_settings() -> Settings:
    database_url = os.getenv("SQLALCHEMY_DATABASE_URL")
    if not database_url:
        raise RuntimeError("SQLALCHEMY_DATABASE_URL is required")

    db_sslmode = os.getenv("DB_SSLMODE", "require")
    _validate_db_sslmode(database_url, db_sslmode)

    return Settings(
        database_url=database_url,
        db_sslmode=db_sslmode,
        db_pool_size=_int_setting("DB_POOL_SIZE", 5, 1),
        db_max_overflow=_int_setting("DB_MAX_OVERFLOW", 2, 0),
        db_connect_timeout_seconds=_int_setting("DB_CONNECT_TIMEOUT_SECONDS", 5, 1),
        db_pool_timeout_seconds=_int_setting("DB_POOL_TIMEOUT_SECONDS", 10, 1),
        db_pool_recycle_seconds=_int_setting("DB_POOL_RECYCLE_SECONDS", 1800, 1),
        browser_cache_seconds=_int_setting("BROWSER_CACHE_SECONDS", 30, 0),
        shared_cache_seconds=_int_setting("SHARED_CACHE_SECONDS", 300, 0),
        stale_while_revalidate_seconds=_int_setting(
            "STALE_WHILE_REVALIDATE_SECONDS", 600, 0
        ),
    )


settings = load_settings()
