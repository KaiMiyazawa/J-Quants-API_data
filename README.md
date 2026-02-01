# J-Quants Premium Data Lake (V2 / jquants-api-client)

本リポジトリは、J-Quants API Premium で取得可能なデータセットを「バックフィル + 増分更新」し、
データレイク（Bronze/Silver）として保存するための実行基盤です。

公式Pythonクライアント `jquants-api-client` の `ClientV2` を使用します。

## 0. 前提
- `.env` に `JQUANTS_API_KEY` を設定してください。
- Premium のレート制御は上限500 req/minのため、デフォルトは480 req/minです（安全側）。

## 1. セットアップ（venv）
```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt

cp .env.example .env
# .env を編集（JQUANTS_API_KEY など）
```

## 2. 実行例

### 2.1 バックフィル（期間指定）

```bash
python -m src.main backfill --from 2008-05-07 --to 2026-01-24
```

### 2.2 増分（単日）

```bash
python -m src.main incremental --date 2026-01-24
```

### 2.3 Bulk同期（可能なデータはCSVバルクで回収）

```bash
python -m src.main bulk-sync
```

### 2.4 Silver生成（Bronze → Parquet）

```bash
python -m src.main normalize --dataset eq_bars_daily --date 2026-01-24
```

## 3. 保存先（DATA_LAKE_ROOT）

* Bronze（Raw）: jsonl.gz（1取得単位=1ファイル）
* Silver（Normalized）: parquet（dtパーティション）

例:
DATA_LAKE_ROOT/
bronze/dataset=eq_bars_daily/dt=2026-01-24/run_id=.../part-0000.jsonl.gz
silver/dataset=eq_bars_daily/dt=2026-01-24/part-0000.parquet
metadata/checkpoints.sqlite

## 4. 重要な注意

* `jquants-api-client` には `*_range` 系ユーティリティがあり、内部で複数リクエストを発行するため、
  範囲が広い/連続実行ではレートリミット到達の可能性がある旨が README に記載されています。
  本実装では、原則として自前のchunking + レート制御で取得します。
# J-Quants-API_data
