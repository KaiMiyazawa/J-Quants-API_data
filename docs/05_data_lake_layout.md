# データレイク設計（Bronze / Silver）

## 基本思想
- Bronze（Raw）: APIレスポンスを「可能な限り生」で保存（JSON Lines / gzip推奨）
- Silver（Normalized）: DataFrame化してスキーマ正規化、パーティション最適化（Parquet推奨）

## 推奨ディレクトリ（例）
DATA_LAKE_ROOT/
  bronze/
    dataset=<dataset_name>/
      dt=<YYYY-MM-DD>/                # 取得対象日（or 取得窓の開始日）
        run_id=<uuid>/
          page=000001.jsonl.gz
          page=000002.jsonl.gz
          manifest.json
  silver/
    dataset=<dataset_name>/
      dt=<YYYY-MM-DD>/
        run_id=<uuid>_part-0000.parquet
        _schema.json
  silver_legacy/                     # 旧形式の退避先（任意）
    dataset=<dataset_name>/
      dt=<YYYY-MM-DD>/
        part-0000.parquet
  metadata/
    runs/
      run_id=<uuid>.json
    checkpoints.sqlite

## manifest.json（例）
- dataset
- client_method
- request_params_hash
- started_at / finished_at
- pages
- row_count_estimate
- pagination_chain
- warnings（例：429発生回数）

## “改定が起こりうるデータ”の扱い
- 投資部門別のように、修正履歴があり得る（改定前後が提供され得る）旨が仕様で注意されている。 :contentReference[oaicite:36]{index=36}
- 上書きせず append-only で保持し、（StartDate, EndDate, Section, PublishedDate等）でバージョニングできるようにする。

## Silver の命名ルール（補足）
- 複数 run_id が同一 dt に存在しうるため、Silver の Parquet 名に run_id を含める。
- 旧形式（run_id なしの `part-0000.parquet`）が残っている場合は、混在に注意する。
