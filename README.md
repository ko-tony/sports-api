# PPPMP Data API

PPPMP 廣告使用的公開附屬資料 API。目前提供天氣與空氣品質資料，並保留未來加入股市大盤 provider 的擴充位置。

## API

對外只有一支資料 endpoint：

- `GET /api/v1/environment`

回傳各縣市的空氣品質與天氣即時值（`cityName`、`aqi`、`pm25`、`o3`、`aqiDate`、`airTemperature`、`humidity`、`uvIndex`、`weather`、`weatherDate`），資料由 `moenv_live` 與 `cwa_uv_live` 依縣市 JOIN 而成。兩表縣市名格式不同（`臺北市` / `臺北`），JOIN 時以 `replace(cityName, '市', '')` 對齊。

舊路徑 `/cwa_uv_live`、`/moenv_live`、`/env_live_1` 與 `/api/v1/cwa-uv-live`、`/api/v1/air-quality` 已移除。`/weather`、帳號、OAuth 測試與 Excel 轉 Word 功能亦已移除。

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

直接 TCP 連線使用 `require`、`verify-ca` 或 `verify-full`。Cloud Run 透過 Cloud SQL Unix Socket 連線時，URL 使用 `?host=/cloudsql/PROJECT:REGION:INSTANCE`，並設定 `DB_SSLMODE=disable`；此處的 `disable` 只關閉 container 到本機 socket 的 libpq TLS，Cloud SQL 整合仍負責 socket 後端連線的加密與授權。程式會拒絕一般 TCP URL 使用 `disable`。

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
