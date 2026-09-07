-- 建立表
CREATE TABLE IF NOT EXISTS public.finance_live (
    symbol text PRIMARY KEY,
    name text NOT NULL,
    "index" numeric(12, 2) NOT NULL CHECK ("index" > 0),
    turnover numeric(20, 8) NOT NULL CHECK (turnover >= 0),
    date timestamptz NOT NULL,
    "fetchedAt" timestamptz NOT NULL
);

-- 可重跑以更新已建立的表；既有資料等下次成功擷取後補值。
ALTER TABLE public.finance_live ADD COLUMN IF NOT EXISTS change numeric(12, 2);
COMMENT ON COLUMN public.finance_live.change IS '相較前一交易日收盤的漲跌點數；正數上漲、負數下跌';

COMMENT ON COLUMN public.finance_live.turnover IS '當日累計成交金額，單位：新台幣億元';
COMMENT ON COLUMN public.finance_live.date IS '證交所行情時間；休市保留最近交易日';
GRANT SELECT, INSERT, UPDATE ON public.finance_live TO ingest_user;
-- 另外將 SELECT 授予公開 API 實際使用的資料庫角色。
