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

## Driveバックアップからの再開手順
このリポジトリを再クローンした後でも、Driveに退避したアーカイブを展開すれば
データと進捗（checkpoint）を引き継いで再開できます。

1. リポジトリをクローン
```bash
git clone <YOUR_REPO_URL>
cd J-Quants
```

2. Driveからアーカイブを配置して展開（リポジトリ直下で実行）
```bash
tar -xzf /path/to/jquants_backup_YYYYMMDD_HHMMSS.tar.gz
```

3. Python環境を作成
```bash
python -m venv .venv
source .venv/bin/activate
.venv/bin/pip install -r requirements.txt
```

4. `.env` を作成して API キーを設定
```bash
cp .env.example .env
```
`JQUANTS_API_KEY` を設定してください。

5. 進捗引き継ぎの確認
```bash
sqlite3 run/checkpoints.sqlite "select status,count(*) from checkpoints group by status;"
sqlite3 run/checkpoints.sqlite "select dataset,scope from checkpoints where status!='done';"
```

6. そのまま再開
```bash
.venv/bin/python -m src.main incremental --date $(date +%F)
.venv/bin/python -m src.main bulk-sync
```

補足:
- アーカイブには `data_lake/` と `run/checkpoints.sqlite` が含まれていれば十分です。
- 同じ期間の `backfill` を再実行しても、既存データは自動スキップされます。
