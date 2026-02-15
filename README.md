# J-Quants Data Lake (Premium, V2)

J-Quants API V2（Premium）で取得可能なデータを、バックフィル + 増分で収集して
ローカルデータレイクとして保存するプロジェクトです。

- Bronze: APIレスポンス生データ（JSON Lines + gzip）
- Bulk: Bulk APIファイル（Key名そのまま）
- Resume-safe: 中断後の再実行で既存データをスキップ

## 参照ドキュメント
- `CONTEXT.md`: 実装・運用・参照順序の統合コンテキスト
- `DATA_LAKE_GUIDE.md`: 保存形式、命名規則、データセット対応
- `PLAN.md`: 取得計画、定期実行周期、運用チェック
- `docs/README.md`: 詳細設計資料の索引

## セットアップ
```bash
python -m venv .venv
source .venv/bin/activate
.venv/bin/pip install -r requirements.txt
cp .env.example .env
```

`.env` で最低限 `JQUANTS_API_KEY` を設定してください。

## 主なスクリプト / コマンド
1. 全体実行（推奨）
```bash
run/run_all.sh <FROM_DATE> <TO_DATE> <INCREMENTAL_DATE>
```
例:
```bash
run/run_all.sh 2006-02-02 2026-02-14 2026-02-14
```

2. バックフィルのみ
```bash
.venv/bin/python -m src.main backfill --from 2006-02-02 --to 2026-02-14
```

3. 単日増分のみ
```bash
.venv/bin/python -m src.main incremental --date 2026-02-14
```

4. Bulk同期のみ
```bash
.venv/bin/python -m src.main bulk-sync
```

5. 完了チェック
```bash
sqlite3 run/checkpoints.sqlite "select status,count(*) from checkpoints group by status;"
sqlite3 run/checkpoints.sqlite "select dataset,scope from checkpoints where status!='done';"
```

## 定期実行の目安（JST）
1. 毎営業日 12:10: 当日分の取得（`incremental`）
2. 毎営業日 20:00-23:00: 本処理（`incremental`）
3. 毎営業日 夜: `bulk-sync`
4. 毎営業日 夜: checkpoint監視

詳細は `PLAN.md` の `2.1 推奨スケジュール（JST）` を参照。

## 保存先（概要）
```text
DATA_LAKE_ROOT/
  bronze/
  bulk_raw/
  metadata/
```
