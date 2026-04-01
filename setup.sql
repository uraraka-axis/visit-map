-- =============================================
-- 訪問管理マップ - Supabase テーブル定義
-- Supabase Dashboard > SQL Editor で実行
-- =============================================

CREATE TABLE IF NOT EXISTS hotels (
    id          BIGSERIAL PRIMARY KEY,
    area        TEXT NOT NULL,                          -- エリア名 (例: atami)
    name        TEXT NOT NULL,                          -- 宿泊施設名
    rooms       TEXT DEFAULT '',                        -- 客室数
    address     TEXT DEFAULT '',                        -- 住所
    phone       TEXT DEFAULT '',                        -- 電話番号
    website     TEXT DEFAULT '',                        -- ウェブサイトURL
    lat         DOUBLE PRECISION,                       -- 緯度
    lng         DOUBLE PRECISION,                       -- 経度
    status      TEXT DEFAULT '未訪問',                   -- 未訪問 / アポ済 / 訪問済 / 対象外
    assignee    TEXT DEFAULT '',                        -- 担当者
    visit_date  DATE,                                   -- 訪問日
    memo        TEXT DEFAULT '',                        -- メモ
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(area, name)
);

-- インデックス
CREATE INDEX IF NOT EXISTS idx_hotels_area ON hotels(area);
CREATE INDEX IF NOT EXISTS idx_hotels_status ON hotels(status);

-- updated_at 自動更新トリガー
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_hotels_updated ON hotels;
CREATE TRIGGER trg_hotels_updated
    BEFORE UPDATE ON hotels
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();
