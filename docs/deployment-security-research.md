# PPPMP 附屬資料 API：部署與 PostgreSQL 安全研究

更新日期：2026-09-03

## 結論先行

- **部署建議：改用 Cloud Run service**，維持一個可容器化的 FastAPI 應用。這個專案已有多個 HTTP route，未來還會新增股市 API，並非單一事件處理函式；Google 也把 functions 定位為 single-purpose/event-driven code，而 Cloud Run service 是一般 HTTP 應用的穩定端點。[Cloud Run deployment options](https://docs.cloud.google.com/run/docs/deployment-options-for-services)
- **管理建議：Git 作為唯一來源，push 後由 Cloud Build 自動建置、推送 Artifact Registry、部署新 revision**。先採簡單的 Dockerfile + `cloudbuild.yaml`；基礎設施變多後，再用 Terraform 管理 Cloud Run、Cloud SQL、IAM、Secret Manager。[Continuous deployment](https://docs.cloud.google.com/run/docs/continuous-deployment) / [Manual setup with Cloud Build](https://docs.cloud.google.com/run/docs/manually-set-up-continuous-deployment)
- **PostgreSQL 現況不能只從 repo 判定為安全或不安全**。程式只顯示由 `SQLALCHEMY_DATABASE_URL` 建立連線，無法證明 Cloud SQL 的 public/private IP、TLS、IAM、備份、審計與實際權限設定。這些必須對 GCP runtime 與 Cloud SQL instance 做一次唯讀盤點。
- **安全目標：公開 Load Balancer/CDN/Armor＋只接受 Load Balancer ingress 的 Cloud Run＋專用 service account＋Cloud SQL private IP/connector＋Secret Manager＋有限連線池＋備份/PITR＋稽核與監控**。

## 1. Cloud Run functions 與 Cloud Run service

### 已確認的現行拓撲（2026-09-03）

- `get-cwa-uv-live`、`get-moenv-aqi-live-1` 是位於 `asia-east1` 的資料擷取 Functions，負責把 CWA／環境部資料寫入 PostgreSQL；它們不是 FastAPI 對外查詢服務。
- 對外 FastAPI 跑在 Compute Engine VM group。`realtime-template-20251029` 的 startup script 進入 `/home/tony/sports-api`、執行 `git pull`、啟用既有 `env`，再以前景 Gunicorn + Uvicorn worker 綁定 port 8000。
- `sports-api.me-pppmp.com` 回應帶有 `via: 1.1 google`，且使用者已確認 VM group 位於既有 Google frontend／Load Balancer 後方。
- 因此可優先沿用既有網域、憑證、固定 IP 與 Load Balancer；真正需要選擇的是 backend 繼續使用 MIG，或改為 Cloud Run serverless NEG。

### MIG 能否沿用

可以短期沿用，但不建議繼續使用現在的 mutable startup deployment：

- `git pull` 沒有固定 commit，同一個 template 在不同時間建立的 VM 可能跑不同版本。
- startup script 沒有安裝／驗證 requirements，也沒有 build、test、失敗回滾與 release artifact。
- Gunicorn 在 startup script 前景執行；process crash 後缺少 systemd restart policy，startup script 本身也不會成為可靠的 process supervisor。
- template 中使用既有 `/home/tony/sports-api/env`，環境內容不由 template 或 immutable image 完整描述，難以重現。

若保留 MIG，建議改為 Git push 後由 Cloud Build 建 image，建立新版 instance template，先 canary 再 rolling update；VM 上用 systemd 管理 process，Load Balancer 與 autohealing 分別使用健康檢查。MIG 原生支援 autoscaling、autohealing、regional multi-zone 與 rolling/canary update。[Managed instance groups](https://docs.cloud.google.com/compute/docs/instance-groups) / [MIG rolling updates](https://docs.cloud.google.com/compute/docs/instance-groups/rolling-out-updates-to-managed-instance-groups)

對這個小型 stateless FastAPI，較推薦沿用 Load Balancer 但把 backend 換成 Cloud Run serverless NEG：可以保留公開網址與 edge 層，同時移除 VM patching、systemd、template/image 與 MIG rolling update 的維運工作。遷移期間先建立 Cloud Run backend 並 smoke test，再切換 backend；舊 MIG 保留到觀察完成後才決定是否下線。

目前 Google Cloud 的產品模型中，新的 Cloud Run function 最終也會建置成 container 並部署為 Cloud Run service；Cloud Run Admin API 是 Google 推薦的新管理介面。這不代表 function 與一般 service 在程式組織上相同：function 仍偏向單一 entrypoint 或 event handler，而 service 適合完整 HTTP application。[Functions comparison](https://docs.cloud.google.com/run/docs/functions/comparison)

| 項目 | Cloud Run function | Cloud Run service/container |
|---|---|---|
| 適合情境 | 單一用途、事件驅動、簡短 handler | FastAPI、多路由、多依賴、共同 middleware |
| 建置 | source 經 buildpacks / Cloud Build | 可 source deploy，也可自訂 Dockerfile |
| 版本 | 底層仍是 Cloud Run revision | revision、流量切分、標籤、回滾完整可用 |
| 本專案適合度 | 隨 weather、air、stock route 增加會愈來愈勉強 | **推薦**：一個附屬資料 API service |

Cloud Run service 可直接 `gcloud run deploy --source .`，由 buildpacks 與 Cloud Build 自動產生 image，不要求本機先安裝 Docker；若需要鎖定系統套件與 runtime，改用 Dockerfile。[Deploy services from source](https://docs.cloud.google.com/run/docs/deploying-source-code)

每次部署會形成 revision。Cloud Run 支援先讓新 revision 不接流量、以 tag 驗證，再逐步切流量；也可以把流量切回舊 revision。[Rollouts, rollbacks, and traffic migration](https://cloud.google.com/run/docs/rollouts-rollbacks-traffic-migration)

### 建議的部署成熟度

1. **立即可用**：本機執行測試後，`gcloud run deploy --source .`。比現有 function 部署流程更符合 FastAPI，也不需先維護 Dockerfile。
2. **推薦常態流程**：GitHub/GitLab/Bitbucket → Cloud Build trigger → Artifact Registry → Cloud Run。push 到指定 branch 就建置與部署；image 用 commit SHA 或 digest 標識，不使用漂移的 `latest`。Artifact Registry 的 digest 是不可變的，也可啟用 immutable tags。實際 trigger 設定需等 project、region、service name、Load Balancer 與權限盤點完成後再加入。[Artifact Registry image versions](https://docs.cloud.google.com/artifact-registry/docs/docker/names)
3. **環境增加後**：用 Terraform `google_cloud_run_v2_service` 管理 service、service account、Secret Manager IAM、Cloud SQL 與 networking；Google 也列 YAML 與 Terraform 為可重現的 declarative/GitOps 部署方式。[Deployment options](https://docs.cloud.google.com/run/docs/deployment-options-for-services)
4. **需要多環境核准時**：再評估 Cloud Deploy 做 staging → production promotion；Cloud Run service 支援 canary。[Cloud Deploy for Cloud Run](https://docs.cloud.google.com/deploy/docs/run-targets)

對目前規模，不建議一開始就導入 Kubernetes/GKE：Cloud Run 已提供 HTTPS、autoscaling、revision 與 managed runtime，維運成本較低。[What is Cloud Run](https://docs.cloud.google.com/run/docs/overview/what-is-cloud-run)

## 2. PostgreSQL / Cloud SQL 安全現況與基線

### 改造前 repo 基線

- `sql_app/database.py` 從環境變數 `SQLALCHEMY_DATABASE_URL` 取得完整連線字串；至少不是直接寫死在 Python source。
- `.env` 已列入 `.gitignore`；但這只能防止一般誤 commit，**不代表部署環境的密碼有用 Secret Manager 管理，也不代表歷史版本從未洩漏**。
- SQLAlchemy engine 未顯式設定 `pool_size`、`max_overflow`、`pool_timeout`、`pool_recycle` 或連線重試策略；Cloud Run scale-out 時，無法從 repo 證明連線數受控。
- repo 看不到 Cloud SQL instance/network/IAM 設定，所以無法確認 public IP、authorized networks、TLS enforcement、IAM DB auth、備份/PITR、maintenance version 或 audit logging。

### 目前 worktree 已改善

- DB session 已集中到 `app/core/database.py`，並設定 `pool_size`、`max_overflow`、connect/pool timeout、recycle 與 `pool_pre_ping`。
- client 端預設使用 `sslmode=require`，不再允許連線降級成明文；但 `require` 不驗證伺服器 hostname，正式目標仍是 Cloud SQL Connector，或 `verify-full` 搭配可信 CA 與正確 hostname。
- CORS 已調整為公開 origin、只允許 GET，且 `allow_credentials=False`。
- 成功資料 response 已加上可由環境變數調整的 browser/shared cache headers。
- 以上均是尚未部署的 worktree 修改；Cloud SQL public IP、authorized networks、runtime secret、DB role、備份/PITR 與 audit 設定仍未改動。

### 2026-09-03 唯讀實測結果

- 本機 `.env` 的 PostgreSQL URL 指向 public IP，且連線參數沒有明寫 `sslmode`。這表示 client 端沒有宣告「只接受加密且驗證伺服器身分」；仍需到 GCP 確認 authorized networks 與 server-side SSL enforcement。
- 從目前環境實際建立的資料庫 session 使用 **TLS 1.3**；伺服器為 PostgreSQL **15.18**，`password_encryption` 為 **SCRAM-SHA-256**。這證明該次連線有加密，但不等於所有連線都被強制加密。
- 目前應用 DB role 不是 superuser，沒有 replication 與 bypass RLS；但擁有 **CREATEDB** 與 **CREATEROLE**。對只讀取天氣、空品與未來大盤資料的 runtime API 而言，這仍違反最小權限，應建立專用 application role 並撤除這兩項能力。
- 線上 `/openapi.json` 可在未驗證狀態讀取，並確認 production 仍公開列出 `/register`、`/token`、`/excel_to_word`、`/weather`、`/cwa_uv_live`、`/moenv_live`、`/env_live_1` 與 `/items/`。清理完成後，部署 smoke test 必須確認前三個待移除功能及測試 route 已消失。

### 必須在 GCP 做的唯讀盤點

| 檢查面向 | 合格基線 |
|---|---|
| 網路 | 優先 private IP；若保留 public IP，不可授權 `0.0.0.0/0` 或過寬 CIDR |
| 連線 | private IP 可 direct connection + 強制 TLS；public IP 使用 Cloud SQL Auth Proxy 或 Python Connector |
| 身分 | Cloud Run 使用專用 user-managed service account，只授予需要的 Cloud SQL Client、secret access 等角色 |
| DB 登入 | 優先 automatic IAM database authentication；若暫留 password，使用獨立低權限 application role |
| secrets | DB password、第三方天氣/股市 API key 放 Secret Manager，不放 repo、Docker image、一般明文設定 |
| 權限 | runtime DB role 不用 `postgres`/superuser，不給 `CREATEDB`/`CREATEROLE`；依 API 所需只給 schema/table 的 SELECT 或必要寫入權限 |
| 連線池 | 每 instance 設小型 pool，並設定 Cloud Run max instances，確保最壞連線總數低於 DB budget |
| 復原 | automated backups + PITR，設定 retention，並定期做 restore drill |
| 記錄 | Cloud Audit Logs、必要的 Data Access logs；SQL 級稽核採 pgAudit；監控 connection、CPU、storage、error 與慢查詢 |
| 維護 | 盤點 PostgreSQL major version、maintenance version、maintenance window、storage auto-increase 與 HA 需求 |

Google 的安全控制目錄要求限制 Cloud SQL public IP，資料庫通常不應直接暴露網際網路；也要求建立並實際測試 backup/restore。[Google Cloud data management controls](https://docs.cloud.google.com/docs/security/security-best-practices-catalog/data-management)

Cloud SQL Language Connectors 提供 IAM connection authorization、加密與短期憑證；它們**不會自行建立 private IP 的 network path**，private IP 仍要配置 Direct VPC egress 或 VPC connector。[Language Connectors](https://docs.cloud.google.com/sql/docs/postgres/language-connectors) Google 對 private IP 的一般建議是 direct connection 並強制 SSL；public IP 則建議 connector。[Choose how to connect](https://cloud.google.com/sql/docs/postgres/connect-overview) 使用 connector 或 Auth Proxy 時，TLS 與 client/server identity verification 會自動處理。[SSL/TLS](https://docs.cloud.google.com/sql/docs/postgres/authorize-ssl)

Automatic IAM database authentication 讓 connector 自動取得與更新短效 OAuth token，Google 明確建議它優於手動 IAM token；仍需在 PostgreSQL 內授予該 IAM DB user 實際的 schema/table privileges。[IAM database authentication](https://docs.cloud.google.com/sql/docs/postgres/iam-authentication)

Cloud Run 每個 instance 都可能建立自己的 pool，scale-out 會放大總連線數。應使用 SQLAlchemy persistent pool、限制 `pool_size` / `max_overflow`，並用 Cloud Run max instances 約束最壞上限；Google 的 Python 範例與 retry/backoff 指引可作設定依據。[Manage database connections](https://docs.cloud.google.com/sql/docs/postgres/manage-connections) 內建 Cloud SQL connection 每個 Cloud Run instance 對每個 database 有 100 connections 的平台上限，但實務 pool 應遠低於此值。[Cloud SQL quotas and limits](https://docs.cloud.google.com/sql/docs/quotas)

若 Cloud SQL 是用 CLI、Terraform 或 API 建立，不能假設 automated backups/PITR 已開啟；官方文件說明這些路徑可能需要手動啟用。[Configure PITR](https://docs.cloud.google.com/sql/docs/postgres/backup-recovery/configure-pitr) 管理操作與存取行為可由 Cloud Audit Logs 查看；需要 SQL statement 級追蹤時可配置 pgAudit。[Cloud SQL audit logging](https://docs.cloud.google.com/sql/docs/postgres/audit-logging) / [pgAudit](https://docs.cloud.google.com/sql/docs/postgres/pg-audit)

### 建議優先修正順序

1. 先確認 Cloud SQL 是否 public、authorized networks 是否過寬、密碼現在放在哪裡；若發現 public + 廣泛允許或 secret 曾進入 repo，先封鎖範圍並輪替 credential。
2. 建立 Cloud Run 專用 runtime service account，改用 private IP + Direct VPC egress，或先以 Cloud SQL Python Connector 過渡。
3. 把 DB credential 與外部 API keys 移到 Secret Manager。Cloud Run 官方建議敏感資訊存 Secret Manager；secret env var 應 pin 版本，volume 則較適合 rotation。[Configure Cloud Run secrets](https://docs.cloud.google.com/run/docs/configuring/services/secrets)
4. 建立低權限 application DB role，移除 superuser/owner 類權限。
5. 設定小型 SQLAlchemy pool、Cloud Run max instances、timeout/recycle/backoff，再用 load test 驗證。
6. 啟用並驗證 backups、PITR、restore；最後補 audit logs、alerts、Query Insights。Query Insights 可協助定位 ORM 與 query performance 問題。[Cloud SQL observability](https://docs.cloud.google.com/sql/docs/postgres/observability)

## 3. API 對外與 service-to-service 安全

### 已確認的產品邊界（2026-09-03）

- caller 是廣告中的使用者瀏覽器，因此 API 必須允許 unauthenticated public GET，不能依賴 Cloud Run service-to-service IAM。
- 現有 `/cwa_uv_live`、`/moenv_live`、`/env_live_1` 路徑必須保持相容；`/weather` 已確認可移除。重構後以同一 handler 掛載 legacy alias，不做 HTTP redirect，避免額外 round trip 與不同瀏覽器的 CORS/redirect 差異。新功能則只新增在 `/api/v1/...`。
- 預估流量為每秒數十個 request。Cloud Run service 本身已有 request-driven autoscaling 與 concurrency，這個量級不需要為了容量額外加 Load Balancer；但因回應是公開且高度可快取的天氣/環境資料，正式架構建議加 External Application Load Balancer + serverless NEG + Cloud CDN，讓大部分 request 不進 Cloud Run/PostgreSQL。
- Load Balancer 同時是 Cloud Armor rate limiting/WAF 的掛載點。Cloud Run ingress 應設 `internal-and-cloud-load-balancing`，並停用預設 `run.app` URL，否則 client 可繞過 CDN/Armor 直接打 origin。
- 廣告可能分布在許多 publisher domain；若無法維護完整 allowlist，公開唯讀 GET 可使用 `Access-Control-Allow-Origin: *`，但必須關閉 credentials，不能把 cookie、永久 API key 或 DB/provider secret 交給瀏覽器。

建議流量路徑：

```text
Browser ad
  -> External Application Load Balancer
       -> Cloud Armor (rate limit / WAF)
       -> Cloud CDN (cache public GET)
       -> serverless NEG
       -> Cloud Run service
       -> PostgreSQL (only on cache miss)
```

Cloud Run 自動依 CPU 與 request concurrency 擴展；官方建議先用較低 concurrency（例如 8）開始，再依 latency、CPU 與 DB 連線觀測調高。可設 `min-instances=1` 降低冷啟動，`max-instances` 則依 PostgreSQL connection budget 計算，而不是任意放大。[Cloud Run concurrency](https://docs.cloud.google.com/run/docs/about-concurrency) / [Cloud Run autoscaling](https://docs.cloud.google.com/run/docs/about-instance-autoscaling)

Cloud CDN 只會快取符合條件的 response。天氣/空品 endpoint 應依資料更新頻率送出明確的 `Cache-Control: public, max-age=..., s-maxage=..., stale-while-revalidate=...`，並監控 cache hit ratio；股市盤中行情則需採較短 TTL，且先確認資料供應商是否允許重新散布與 edge cache。[Load Balancer performance best practices](https://docs.cloud.google.com/load-balancing/docs/https/http-load-balancing-best-practices)

External Application Load Balancer 可透過 serverless NEG 指向 Cloud Run；將 ingress 限制為 `internal-and-cloud-load-balancing` 可確保公開請求都經過 Load Balancer 的 Cloud CDN/Armor。[Load Balancer with Cloud Run](https://docs.cloud.google.com/load-balancing/docs/https/setting-up-https-serverless) / [Cloud Run ingress](https://docs.cloud.google.com/run/docs/securing/ingress) Cloud Armor 可針對 client 做 throttle 或 temporary ban，建議先用 preview mode 觀察再執行封鎖。[Cloud Armor rate limiting](https://docs.cloud.google.com/armor/docs/rate-limiting-overview)

因 caller 已確認是使用者瀏覽器，不能把任何永久 API secret 放在前端。CORS 不是存取控制；這組公開資料 API 的保護層應是 CDN cache、Cloud Armor rate limit、成本/錯誤告警，以及不讓公開 request 直接接觸 database credential 或上游 provider key。

Cloud Run runtime 應使用專用 user-managed service account，而不是帶有廣泛權限的 default service account。Google 明確建議自管 service account 並授予最小權限。[Cloud Run service identity](https://docs.cloud.google.com/run/docs/securing/service-identity)

## 4. 為天氣與股市 API 保留擴充性

建議維持**模組化單體（modular monolith）**，暫時不要拆微服務：

```text
FastAPI Cloud Run service
├── api/v1/air_quality   HTTP contract / validation
├── api/v1/market
├── services/            use cases、聚合、快取策略
├── providers/           CWA、MOENV、股市資料供應商 adapter
├── repositories/        PostgreSQL access
├── core/                config、logging、errors、security
└── schemas/             request/response models
```

設計原則：

- 外部資料來源藏在 provider interface 後面；將來換股市供應商，不改 HTTP contract。
- 對外 API 從 `/api/v1/...` 開始，response schema 明確包含 `source`、`as_of`、`fetched_at`，避免即時行情與快取資料語意混淆。
- HTTP request path 只讀取已整理資料；抓取外部天氣/股市資料若是週期工作，放到 Cloud Run Job，由 Cloud Scheduler 定時執行，避免 request latency 與供應商失效直接拖垮廣告請求。[Schedule Cloud Run jobs](https://docs.cloud.google.com/run/docs/execute/jobs-on-schedule)
- 外部 API 呼叫必須設 connect/read timeout、有限 retry + exponential backoff、circuit breaker 或 stale-cache fallback；記錄 provider、latency、status，不記錄 API key 或完整敏感 payload。
- 對股市資料定義 freshness、交易日/時區（Asia/Taipei）、盤中與收盤狀態；行情授權與重散布條款應在選供應商時先確認。
- schema migration 不在每個 web instance startup 自動執行；由 CI/CD 的獨立、可觀測步驟或一次性 job 執行，避免多 instance 競爭。
- Cloud Run stdout/stderr 會自動進 Cloud Logging，並關聯 service/revision/location；應輸出結構化 JSON log 與 request ID。[Cloud Run logging](https://docs.cloud.google.com/run/docs/logging)

## 5. 推薦目標架構

```text
Browser ad
  │ public HTTPS
  ▼
External Application Load Balancer
  ├── Cloud CDN
  └── Cloud Armor
        ▼ serverless NEG
Cloud Run service (FastAPI /api/v1 + legacy aliases)
        ├── Secret Manager (provider keys; DB secret only if IAM DB auth not used)
        ├── Cloud SQL PostgreSQL (private IP, low-privilege role, TLS/IAM)
        └── Cloud Logging / Monitoring / Error Reporting

Git push
  └── Cloud Build trigger
        ├── test + image build
        ├── Artifact Registry (commit SHA/digest)
        └── deploy new Cloud Run revision → smoke test → traffic / rollback

Cloud Scheduler
  └── Cloud Run Job (weather/market ingestion or refresh)
```

## 6. 建議落地階段

### Phase A：清理與可部署化

- 移除帳號與 Excel/Word routes、依賴及死碼。
- 拆出 `/api/v1` routers、settings、DB session、統一 errors/logging、health/readiness endpoints。
- 補齊 dependency lock、Dockerfile、`.dockerignore` 與測試。

### Phase B：安全遷移

- 做 Cloud SQL/IAM/network/secrets/backups 唯讀盤點。
- 確認 project、region、service、Artifact Registry 與 Load Balancer 後，加入 Cloud Build trigger／部署設定。
- 建立 runtime/deployer 各自的 service account 與最小權限。
- 秘密移到 Secret Manager；建立 private Cloud Run → Cloud SQL 連線。
- 收斂 Cloud Run invoker 與 CORS；輪替任何曾以明文散布的 credential。

### Phase C：穩定交付

- 建 staging 與 production；image 以 commit SHA/digest 部署。
- 新 revision 先 0% traffic/tag smoke test，再切流量；保留 rollback runbook。
- 設定 max instances、DB pool、alerts、backup restore drill。

### Phase D：加入股市資料

- 新增 `market` provider/interface/schema，不直接把特定供應商欄位暴露成公共 contract。
- 確認資料授權、更新頻率與 freshness SLA。
- 視需求加入 Scheduler + Job 定期抓取、PostgreSQL 儲存與 stale-cache fallback。

## 7. 實作前仍需確認

- 現有部署究竟是 Cloud Functions 1st gen、Cloud Functions 2nd gen，或 Cloud Run function。
- PPPMP-API 與此 API 是否在同一 GCP project/region，以及 caller 是 server 還是瀏覽器。
- PostgreSQL 是否為 Cloud SQL；instance name、region、IP 模式、authorized networks、SSL mode。
- 現行 DB username 的 grants/role attributes，以及 database URL 實際保存位置。
- automated backups、PITR、retention、restore 演練、HA 與 maintenance 設定。
- 目前尖峰 QPS、Cloud Run concurrency/max instances、DB `max_connections` 與外部資料 freshness 需求。
