# レートリミット / リトライ / 再開（checkpoint）設計

## レートリミット（Premium）
- 500 requests / minute :contentReference[oaicite:32]{index=32}
- 超過時：HTTP 429 Too Many Requests :contentReference[oaicite:33]{index=33}
- 大幅超過を継続：5分程度の完全遮断が起こり得る :contentReference[oaicite:34]{index=34}

## クライアント側制御（必須）
- トークンバケット（1分窓）またはリーキーバケットで 480 req/min 程度に抑制
- 429時は即リトライ禁止。指数バックオフ + ジッタ：
  - sleep = min(max_sleep, base * 2^n + random(0,1))
- 429が続く場合は “遮断状態” を疑い、5分程度のクールダウンを許容する。 :contentReference[oaicite:35]{index=35}

## Checkpoint（再開）必須要件
- データセット単位・パラメータ単位で「どこまで取得したか」を永続化
- 例（株価日足 date-only）：
  - dataset = eq_bars_daily
  - date = 2023-03-24
  - pagination_key = "value1.value2."
  - status = in_progress / done / failed
- 保存先：SQLite（例: `run/checkpoints.sqlite`）
- ジョブ再実行時：
  - doneはスキップ
  - in_progress/failedは pagination_key から再開

## 監査ログ（推奨）
- 1リクエストごとに
  - endpoint（またはclient method）
  - params（正規化JSON）
  - HTTP status
  - response bytes
  - retry_count
  - elapsed_ms
  - run_id
- を記録する（後日の欠損・API変更の調査に必須）。