# CONTEXT.md

このファイルは、AIコーディングエージェント向けの**統一コンテキスト**です。
以後の実装・運用・分析依頼は、まず本ファイルを参照してください。

---

## 1. プロジェクト目的

- **J-Quants API V2（Premium）**から取得可能なデータを**網羅的に回収**し、
  ローカルに**データレイク**（Bronze / Bulk / 将来Silver）として保存する。
- 初回は**バックフィル（過去全期間）**、以後は**日次増分＋週次更新**で運用する。

---

## 2. 保存形式と命名規則

詳細は `DATA_LAKE_GUIDE.md` を参照。

- **Bronze**: APIレスポンスを JSON Lines + gzip で保存
- **Bulk**: Bulk APIのファイルを Key 名そのままで保存
- **チェックポイント**: `metadata/checkpoints.sqlite`

---

## 3. 取得対象（Premiumまで）

取得対象は `src/datasets.py` に定義済み。主要な論理データセットは以下。

- Free: `eq_master`, `eq_bars_daily`, `fin_summary`, `eq_earnings_cal`, `mkt_calendar`
- Light: `eq_investor_types`, `idx_bars_daily_topix`
- Standard: `idx_bars_daily`, `drv_bars_daily_opt_225`, `mkt_margin_interest`, `mkt_short_ratio`,
  `mkt_short_sale_report`, `mkt_margin_alert`
- Premium: `mkt_breakdown`, `eq_bars_daily_am`, `fin_dividend`, `fin_details`,
  `drv_bars_daily_fut`, `drv_bars_daily_opt`

---

## 4. 実行エントリポイント

- `src/main.py`
  - `backfill`: 営業日ベースで全期間取得
  - `incremental`: 単日取得
  - `bulk-sync`: Bulk API同期

実行例:
```
run/run_all.sh 2006-02-02 2026-02-01 2026-02-01
```

定期運用の実行周期は `PLAN.md` の「2.1 推奨スケジュール（JST）」を参照。

---

## 5. 再実行セーフ / 障害耐性

- **既存ファイルがあれば自動スキップ**（checkpointがなくてもOK）
- `pagination_key` をチェックポイントに保持
- ネット切断や中断後でも再実行で再開可能

---

## 6. 重要な注意点

- APIごとに**取得可能な最古日が異なる**ため、範囲外は自動スキップ
- `eq_bars_daily_am` は**当日限定**（12:00〜翌朝6:00）
- Bulk APIのファイルは Key 名そのまま保存（拡張子注意）

---

## 7. 参照ドキュメント

### 7.1 主要ドキュメント
- `DATA_LAKE_GUIDE.md` : 保存形式と命名規則（分析時の最重要参照）
- `PLAN.md` : 取得計画と運用フロー

### 7.2 docs/*.md の役割（必要に応じて参照）

**基本方針**: まず `DATA_LAKE_GUIDE.md` と `PLAN.md` を見て、
詳細仕様や背景が必要になった場合に `docs/` を参照する。

- `docs/00_project_overview.md`
  - プロジェクトの目的・前提・成果物の全体像
- `docs/01_environment_setup.md`
  - venv や .env 設定などのセットアップ手順
- `docs/02_jquants_v2_and_client_mapping.md`
  - API V2 と `jquants-api-client` の対応表（メソッド一覧）
- `docs/03_request_enumeration_strategy.md`
  - “全通り取得”の定義と、効率的な取得戦略
- `docs/04_rate_limit_retry_checkpoint.md`
  - レート制限・リトライ・チェックポイント設計の詳細
- `docs/05_data_lake_layout.md`
  - データレイク（Bronze/Silver）のディレクトリ設計案
- `docs/06_codex_instructions.md`
  - Codex向けの実装指示（当初設計の原文）
- `docs/07_appendix_known_specs_examples.md`
  - API仕様の具体例・補足

---

## 8. 今後の拡張候補

- Silver（Parquet）生成
- 欠損検知・品質チェック
- API別の取得可能期間メタデータ管理
