# PPPMP Data API

PPPMP 廣告使用的公開附屬資料 API。目前提供天氣與空氣品質資料，並保留未來加入股市大盤 provider 的擴充位置。

## API

新功能使用 `/api/v1`：

- `GET /api/v1/cwa-uv-live`
- `GET /api/v1/air-quality`
- `GET /api/v1/environment`

廣告仍在使用的 `/cwa_uv_live`、`/moenv_live`、`/env_live_1` 會維持相同 response，並在 OpenAPI 標記為 deprecated。`/weather`、帳號、OAuth 測試與 Excel 轉 Word 功能已移除。

## 本機執行

環境變數：

```dotenv
SQLALCHEMY_DATABASE_URL=postgresql://user:password@host:5432/database
DB_SSLMODE=require
DB_POOL_SIZE=5
DB_MAX_OVERFLOW=2
DB_CONNECT_TIMEOUT_SECONDS=5
BROWSER_CACHE_SECONDS=30
SHARED_CACHE_SECONDS=300
STALE_WHILE_REVALIDATE_SECONDS=600
```

啟動與測試：

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn main:app --reload
.venv/bin/python -m unittest discover
```

- API 文件：`http://127.0.0.1:8000/docs`
- Liveness：`GET /health`
- Database readiness：`GET /ready`

## 部署方向

現有網域與 External Application Load Balancer 可繼續沿用。短期可部署在既有 Managed Instance Group，但應改用固定版本 artifact、systemd 與 MIG rolling update，不再於 VM 開機時直接 `git pull`。較省維運的目標是把 Load Balancer backend 換成 Cloud Run serverless NEG；Cloud Run ingress 設為 `internal-and-cloud-load-balancing`，避免直接繞過 CDN/Armor。

正式環境的 database credential 與 provider API key 應由 Secret Manager 提供。完整研究與遷移清單見 [`docs/deployment-security-research.md`](docs/deployment-security-research.md)。
