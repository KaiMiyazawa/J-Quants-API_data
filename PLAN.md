# PLAN: J-Quants Premium Data Lake

この計画は「Premiumで取れるデータを漏れなく取得する」ことを主目的とし、
取得 → 保存 → 検証 → 運用までの全体像を整理したものです。

---

## 0. 参照
- `CONTEXT.md`: 全体コンテキスト
- `DATA_LAKE_GUIDE.md`: 保存形式・命名規則

---

## 1. 取得計画（完了）

- Premium までの全データセット取得
- バックフィル（過去全期間）
- 週次・イベント系データの取得
- Bulk API 同期

**現状**: 取得完了（checkpointは `done` のみを維持）

---

## 2. 運用計画（継続）

- 日次増分: 営業日ごとに `incremental`
- 週次更新: `eq_investor_types` の from/to ウィンドウで取得
- Bulk更新: 定期的に `bulk-sync`

### 2.1 推奨スケジュール（JST）

1. 毎営業日 12:10
`eq_bars_daily_am` の当日取得（当日限定データのため）。

```bash
.venv/bin/python -m src.main incremental --date $(date +%F)
```

2. 毎営業日 20:00-23:00
日次増分の本処理（通常の `incremental`）。

```bash
.venv/bin/python -m src.main incremental --date $(date +%F)
```

3. 毎営業日 夜（incremental 後）
Bulkの差分取り込み。

```bash
.venv/bin/python -m src.main bulk-sync
```

4. 毎営業日 夜（ジョブ終了後）
checkpoint監視（未完了がないことを確認）。

```bash
sqlite3 run/checkpoints.sqlite "select status,count(*) from checkpoints group by status;"
sqlite3 run/checkpoints.sqlite "select dataset,scope from checkpoints where status!='done';"
```

---

## 3. 検証・品質チェック（推奨）

- 欠損検知（営業日 × データセット）
- サンプル突合（date取得 vs code取得）
- 価格系の簡易整合性チェック

---

## 4. 今後の拡張

- Silver（Parquet）生成
- API別の取得可能期間メタデータ管理
- 監視・通知の導入
