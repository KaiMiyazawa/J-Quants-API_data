# J-Quants Data Lake Guide

このドキュメントは、本プロジェクトで取得・保存される **J-Quants API Premium データ**の
「**何が / どの形式で / どの命名規則で**」保存されるかを人とAIの両方が参照できる形で整理したものです。

---

## 1. 全体構成

```
DATA_LAKE_ROOT/
  bronze/
    dataset=<dataset_name>/
      dt=<YYYY-MM-DD>/
        run_id=<uuid>/
          page=000001.jsonl.gz
          page=000002.jsonl.gz
          manifest.json
  bulk_raw/
    <endpoint_slug>/
      <Key from /bulk/list>
  metadata/
    checkpoints.sqlite
  silver/                  # (将来: Bronze -> Silver 正規化用)
```

### 主要ディレクトリ
- **bronze/**: APIレスポンスの **生データ**（JSON Lines + gzip）
- **bulk_raw/**: Bulk API のCSV等を **そのまま保存**（Key 名そのまま）
- **metadata/**: チェックポイント等の運用メタデータ
- **silver/**: 正規化済みデータ（現状は未生成だが将来対応）

---

## 2. Bronze（Raw APIレスポンス）

### 2.1 形式
- **ファイル形式**: `jsonl.gz`
- **1ページ = 1ファイル**
- **1行 = 1レコード**（APIの `data` 要素）

### 2.2 命名規則
```
bronze/dataset=<dataset_name>/dt=<YYYY-MM-DD>/run_id=<uuid>/page=000001.jsonl.gz
```

- `dataset_name` : 論理データセット名（後述）
- `dt` : 取得対象日（または取得範囲の開始日）
- `run_id` : 取得ジョブごとに生成される UUID
- `page` : pagination に対応した連番

### 2.3 manifest.json
同一 run_id 配下に `manifest.json` が生成されます。

例:
```json
{
  "dataset": "eq_bars_daily",
  "endpoint": "/equities/bars/daily",
  "scope": "dt=2019-09-02",
  "dt": "2019-09-02",
  "run_id": "<uuid>",
  "params": {"date": "20190902"},
  "pages": 1,
  "row_count": 4000,
  "created_at": "2026-02-03T23:15:06Z"
}
```

---

## 3. Bulk API（CSVダウンロード）

### 3.1 形式
- **ファイル形式**: Bulk API から取得した内容を **そのまま保存**
- **拡張子**: APIが返す `Key` に依存（例: `.csv.gz`）

### 3.2 命名規則
```
bulk_raw/<endpoint_slug>/<Key>
```

- `endpoint_slug` : エンドポイントを `/` → `__` に変換した文字列
  - 例: `/markets/breakdown` → `markets__breakdown`
- `Key` : `/bulk/list` のレスポンスにある Key をそのまま使用

例:
```
bulk_raw/markets__breakdown/markets/breakdown/live/markets_breakdown_20260115.csv.gz
```

---

## 4. チェックポイント（再実行のための進捗保存）

- **保存先**: `metadata/checkpoints.sqlite`
- **役割**: 取得単位（dataset + scope）ごとの取得済み/再開情報

主な情報:
- `dataset`: データセット名
- `scope`: 取得対象（例: `dt=YYYY-MM-DD` / `from=YYYY-MM-DD_to=YYYY-MM-DD`）
- `status`: `done` / `in_progress`
- `payload_json`: pagination_key などの再開情報

---

## 5. データセット一覧（Premiumまで）

### Free
- `eq_master` → `/equities/master`
- `eq_bars_daily` → `/equities/bars/daily`
- `fin_summary` → `/fins/summary`
- `eq_earnings_cal` → `/equities/earnings-calendar`
- `mkt_calendar` → `/markets/calendar`

### Light
- `eq_investor_types` → `/equities/investor-types`
- `idx_bars_daily_topix` → `/indices/bars/daily/topix`

### Standard
- `idx_bars_daily` → `/indices/bars/daily`
- `drv_bars_daily_opt_225` → `/derivatives/bars/daily/options/225`
- `mkt_margin_interest` → `/markets/margin-interest`
- `mkt_short_ratio` → `/markets/short-ratio`
- `mkt_short_sale_report` → `/markets/short-sale-report`
- `mkt_margin_alert` → `/markets/margin-alert`

### Premium
- `mkt_breakdown` → `/markets/breakdown`
- `eq_bars_daily_am` → `/equities/bars/daily/am`（当日限定）
- `fin_dividend` → `/fins/dividend`
- `fin_details` → `/fins/details`
- `drv_bars_daily_fut` → `/derivatives/bars/daily/futures`
- `drv_bars_daily_opt` → `/derivatives/bars/daily/options`

---

## 6. dt の意味

- `dt` は**原則として取得対象日**を表します。
- 週次取得（`eq_investor_types`）などは `scope=from=..._to=...` が付与されます。
- `eq_bars_daily_am` は「当日限定データ」のため `dt` は取得日（実行日）に一致します。

---

## 7. 代表的な保存例

```
bronze/dataset=eq_bars_daily/dt=2019-09-02/run_id=3a6.../page=000001.jsonl.gz
bronze/dataset=mkt_breakdown/dt=2019-09-02/run_id=aa1.../page=000001.jsonl.gz
bronze/dataset=eq_bars_daily_am/dt=2026-02-01/run_id=bb2.../page=000001.jsonl.gz
bulk_raw/markets__breakdown/markets/breakdown/live/markets_breakdown_20260115.csv.gz
metadata/checkpoints.sqlite
```

---

## 8. AI分析エージェント向け注意点

- **Bronzeは生レスポンス**のため、列名・型はAPI仕様に準拠するが変動の可能性あり
- pagination により **複数ファイルに分割**されることがある
- `eq_bars_daily_am` は当日取得限定で、ヒストリカル用途は `eq_bars_daily` を利用
- Bulk のファイル名は Key に依存するため、データ対象日などは Key から推測する

---

## 9. 今後の拡張予定（Silver）

- Bronze → Silver 変換で以下を想定
  - Parquet形式
  - スキーマ固定
  - `dt` パーティション
  - `run_id` 識別

---

## 10. ファイル探索例

```
# ある日の株価日足を探す
find data_lake/bronze/dataset=eq_bars_daily/dt=2019-09-02 -type f

# Bulkデータ一覧を見る
find data_lake/bulk_raw -type f | head
```

