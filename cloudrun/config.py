"""擷取工作共用的環境設定。

DB_PASSWORD 由 Cloud Run 從 Secret Manager 注入，其餘為一般環境變數。
"""

import os


def required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"環境變數 {name} 未設定")
    return value


def db_connection_kwargs() -> dict[str, str]:
    """Cloud SQL 連線參數。

    DB_HOST 走 /cloudsql/<connection-name> Unix socket 時不需要 port。
    """
    return {
        "dbname": os.environ.get("DB_NAME", "postgres"),
        "user": required("DB_USER"),
        "password": required("DB_PASSWORD"),
        "host": required("DB_HOST"),
    }


# 政府 API 回應慢時不要一路卡到 Cloud Run request timeout
HTTP_TIMEOUT_SECONDS = int(os.environ.get("HTTP_TIMEOUT_SECONDS", "15"))
