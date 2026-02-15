# docs/README

このディレクトリは、設計背景・運用設計・仕様補足などの**詳細資料**を保持します。
普段は `DATA_LAKE_GUIDE.md` と `PLAN.md` を参照し、
さらに詳細が必要になった場合にこの `docs/` を開いてください。

---

## 各ファイルの役割

- `00_project_overview.md`
  - プロジェクト目的、前提、成果物の概要
- `01_environment_setup.md`
  - venv/.env など実行環境の手順
- `02_jquants_v2_and_client_mapping.md`
  - J-Quants V2 と client メソッド対応表
- `03_request_enumeration_strategy.md`
  - 「全通り取得」の定義と効率的な取得戦略
- `04_rate_limit_retry_checkpoint.md`
  - レート制限と再実行耐性（checkpoint）設計
- `05_data_lake_layout.md`
  - データレイクのディレクトリ設計
- `06_codex_instructions.md`
  - 当初のCodex向け実装指示（設計の原文）
- `07_appendix_known_specs_examples.md`
  - API仕様の具体例・補足
