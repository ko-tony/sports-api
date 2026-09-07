# 台股 Finance 擷取與部署

API 新增 `change`（漲跌點數），由同一筆行情的 `z - y` 計算：正數上漲、
負數下跌、0 表示平盤；`y` 為前一交易日收盤指數，不是前一次排程的指數。
例如 `47326.27 - 46551.13 = 775.14` 點。

已建表的環境請先重新執行 `cloudrun/finance-live.sql`，其中
`ADD COLUMN IF NOT EXISTS` 會補上 `change numeric(12, 2)`，再部署擷取端與 API。
舊資料在下一次成功擷取前回傳 `change: null`；缺少或無效昨收時不覆寫資料。

`get-twse-finance-live.py` 是 HTTP function，每次呼叫只抓一次資料並 upsert
`finance_live`。不自行啟動計時器；由你部署到 GCP 後設定每 3 分鐘呼叫。

## 資料來源與欄位

證交所行情網站的 JSON API（不是 HTML 爬蟲，也不是正式 OpenAPI 規格）：

https://mis.twse.com.tw/stock/api/getChartOhlcStatis.jsp?ex=tse&ch=t00.tw&fqy=1

- `infoArray` 中 `ex=tse, c=t00` 的 `z`：上市加權指數。
- `staticObj.tz`：當日累計成交金額（新台幣元），除以 100,000,000 寫入 `turnover`（億元），保留 8 位小數。
- `infoArray.d` + `t`：行情時間，使用 Asia/Taipei；`fetchedAt` 是擷取時間。
- 檢查 `staticObj.key` 與行情日期相符，避免混入不同交易日金額。
- 休市時保留來源的最近交易日；空資料、缺欄位、無效數字或上游失敗回 502，不覆寫原資料。資料庫失敗回 500。
- 舊行情不覆寫較新的行情；HTTP 200 的 `OK, 0 rows` 表示舊資料被略過。

### 盤中與盤後

讀取的是最新行情 `infoArray.z`，不是必須等盤後才產生的日報表，也不從
`ohlcArray` 取某個固定時間的指數。10:00 觸發擷取，會向來源取得當時的最新值。
請求附時間戳與 no-cache header，避免重用相同 URL 的 HTTP 快取；上游仍可能延遲。
當日行情於 09:00–13:30 超過 3 分鐘未更新則回 502；13:30 後若當日行情時間
仍早於 13:30，也回 502，等待後續排程取得收盤值。來源有時將最終值時間標成
13:33，保留原始時間，不強改為 13:30。

每 3 分鐘排程代表公開 API 最多另有約 3 分鐘排程延遲，並非逐筆即時。
擷取失敗時公開 API 仍保留上一筆資料，使用端應檢查 `date`，不能只看 `fetchedAt`。
目前沒有交易日曆，較舊交易日期可能是休市或來源異常，不能視為今天即時行情。
實際連線已驗證盤後資料；10:00 盤中行為有單元測試，仍需交易時段實測確認來源延遲。

## 來源限制

- 這是證交所 MIS 基本市況報導網站使用的 JSON endpoint，不在證交所正式
  OpenAPI 規格內；欄位、URL、回應格式可能未預告變更，也沒有公開 SLA。
- 證交所沒有為此 endpoint 公布每分鐘請求上限。3 分鐘一次約每小時 20 次，
  不代表證交所保證或授權此頻率；遇到 403、429、5xx 或 timeout 時，本程式
  回 502 並保留資料庫原值，不會改用錯誤資料。
- MIS 可能使用 session cookie，也可能對流量或來源 IP 做限制。Cloud Run
  重新建立 instance 時不保證沿用 session；目前實測此 endpoint 可直接 GET，
  但不能視為長期介面契約。
- MIS 顯示的是行情快照。每 3 分鐘排程後，使用端看到的資料延遲由「證交所
  上游延遲 + 最多約 3 分鐘排程等待 + Cloud Scheduler/Cloud Run 執行時間」組成。
- 公開 API 會再對外傳輸證交所即時指數。證交所官方交易資訊規範指出，傳輸或
  播送即時股價指數資訊須簽訂使用契約並可能收費；正式對外上線前，應由資料
  使用方式與法務/證交所確認授權。僅供內部顯示也不應直接假設豁免。

2026-09-07 實際取得同一份回應：`z=47326.27`、`tz=939926033350`，
轉換後為 `9399.2603335` 億元。這是來源快照，不是固定回傳值。

## GCP 設定

1. 先以管理角色執行 `finance-live.sql`，再授予公開 API 的 DB 使用者該表的 SELECT 權限。
2. 建立 Python 3.12 Cloud Run function，entry point 設 `finance_live`。
   部署時以 `get-twse-finance-live.py` 作為 `main.py`，並一併部署現有的
   `config.py`、`db.py`、`requirements.txt`（全部位於 `cloudrun/`）。
3. 掛載 Cloud SQL instance，runtime service account 需有 Cloud SQL Client。
   設定 `DB_HOST=/cloudsql/PROJECT:REGION:INSTANCE`、`DB_USER=ingest_user`，
   `DB_PASSWORD` 從 Secret Manager 注入；`DB_NAME` 預設 postgres，
   `HTTP_TIMEOUT_SECONDS` 預設 15。證交所不需 API key。
4. 服務要求驗證。Cloud Scheduler 使用具備該服務 `roles/run.invoker` 的 SA，
   HTTP POST、OIDC audience 填服務 URL；頻率 `*/3 * * * *`，時區 `Asia/Taipei`。
   不需要 request body。建議 function timeout 60 秒、排程 attempt deadline 60 秒。
5. 先手動執行一次排程，確認 HTTP 200 和資料表內容，再部署公開 API。

公開 API `GET /api/v1/finance` 回傳一個物件，包含 `symbol`、`name`、`index`、
`turnover`、`turnoverUnit="億元"`、`date`、`fetchedAt`。尚未寫入資料回 404，
資料庫不可用回 503。回應不額外快取，避免 CDN 再延遲數分鐘。

上述只提供程式與設定步驟，不會自行部署、建表或建立排程。

若啟動記錄出現 `cannot import name 'upsert_rows' from 'db'`，代表部署進
`/workspace/db.py` 的檔案不是目前的 `cloudrun/db.py`。重新部署現有 `db.py`；
正確版本在第 18 行明確定義 `def upsert_rows(...)`。
